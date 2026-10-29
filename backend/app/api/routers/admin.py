"""Admin/operations endpoints. Every route requires the admin role (enforced server-side)."""
import json
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import serializers as ser
from app.api.deps import require_admin
from app.core.config import BACKEND_DIR, get_settings
from app.core.ratelimit import rate_limit
from app.database import get_db
from app.models import (
    AuditLog,
    Candidate,
    ChangeEvent,
    CrawlJob,
    DatasetVersion,
    Scholarship,
    Source,
    SourceDocument,
    User,
    utcnow,
)
from app.schemas import ApproveIn, DecisionIn, LinkIn, SourceIn, SourceUpdate
from app.services import audit, review, trust
from app.services.connectors.nsp_listing import parse_nsp_listing
from app.services.crawl import orchestrator, scheduler
from app.services.extraction import llm
from app.services.extraction.text import extract, find_closure_statements, find_deadline_statements
from app.services.ingestion.csv_import import ImportError_, import_dataset
from app.services.matching import find_duplicate_pairs
from app.services.sources.fetcher import FetchError, SafeFetcher

router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


def _get(db: Session, model, id_: str):
    obj = db.get(model, id_)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj


# ------------------------------------------------------------------ overview

@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    now = utcnow()
    day, week = now - timedelta(days=1), now - timedelta(days=7)
    count = lambda stmt: db.scalar(select(func.count()).select_from(stmt.subquery()))  # noqa: E731
    sources = list(db.scalars(select(Source).order_by(Source.priority.desc())))
    published = list(db.scalars(select(Scholarship).where(Scholarship.is_published.is_(True))))
    by_status: dict[str, int] = {}
    stale = []
    for s in published:
        by_status[s.verification_status] = by_status.get(s.verification_status, 0) + 1
        if "stale_observation" in (s.verification_flags or []):
            stale.append({"id": s.id, "name": s.name, "last_checked_at": ser.iso(s.last_checked_at)})
    jobs_24h = dict(db.execute(select(CrawlJob.status, func.count()).where(CrawlJob.queued_at >= day)
                               .group_by(CrawlJob.status)).all())
    jobs_all = dict(db.execute(select(CrawlJob.status, func.count()).group_by(CrawlJob.status)).all())
    finished = jobs_all.get("succeeded", 0) + jobs_all.get("failed", 0)
    recent_failures = list(db.scalars(select(CrawlJob).where(CrawlJob.status == "failed")
                                      .order_by(CrawlJob.queued_at.desc()).limit(10)))
    recent_changes = db.execute(
        select(ChangeEvent, Scholarship.name).join(Scholarship, Scholarship.id == ChangeEvent.scholarship_id)
        .where(ChangeEvent.materiality == "material").order_by(ChangeEvent.detected_at.desc()).limit(10)).all()
    return {
        "generated_at": now.isoformat(),
        "scholarships": {"published": len(published), "by_verification_status": by_status, "stale": stale,
                         "unpublished": count(select(Scholarship.id).where(Scholarship.is_published.is_(False)))},
        "sources": [ser.source(s) for s in sources],
        "jobs": {"last_24h": jobs_24h, "all_time": jobs_all,
                 "success_rate": round(jobs_all.get("succeeded", 0) / finished, 3) if finished else None,
                 "running": count(select(CrawlJob.id).where(CrawlJob.status.in_(("queued", "running")))),
                 "recent_failures": [ser.job(j) for j in recent_failures]},
        "review": {
            "pending_candidates": count(select(Candidate.id).where(Candidate.status == "pending")),
            "pending_changes": count(select(ChangeEvent.id).where(ChangeEvent.review_status == "pending")),
            "extraction_failures": count(select(Candidate.id).where(Candidate.extraction_status == "failed",
                                                                     Candidate.status == "pending")),
        },
        "changes_last_7_days": {
            "material": count(select(ChangeEvent.id).where(ChangeEvent.detected_at >= week,
                                                           ChangeEvent.materiality == "material")),
            "cosmetic": count(select(ChangeEvent.id).where(ChangeEvent.detected_at >= week,
                                                           ChangeEvent.materiality == "cosmetic")),
            "auto_accepted": count(select(ChangeEvent.id).where(ChangeEvent.detected_at >= week,
                                                                ChangeEvent.review_status == "auto_accepted")),
        },
        "recent_changes": [ser.change(ev, name) for ev, name in recent_changes],
        "datasets": [{"version": d.version, "imported_at": ser.iso(d.imported_at), "rows": d.num_rows,
                      "created": d.num_created, "updated": d.num_updated, "rejected": d.num_rejected}
                     for d in db.scalars(select(DatasetVersion).order_by(DatasetVersion.imported_at.desc()))],
        "scheduler": scheduler.state | {"enabled": get_settings().scheduler_enabled},
        "llm": llm.status(),
    }


# ------------------------------------------------------------------ sources

@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    return [ser.source(s) for s in db.scalars(select(Source).order_by(Source.priority.desc(), Source.name))]


@router.post("/sources")
def create_source(body: SourceIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Source).where(Source.key == body.key)):
        raise HTTPException(status_code=409, detail="Source key already exists")
    for u in body.target_urls:
        from app.services.sources.fetcher import url_allowed
        if not url_allowed(u, body.allowed_url_patterns):
            raise HTTPException(status_code=422, detail=f"Target URL not covered by allowed patterns: {u}")
    src = Source(**body.model_dump())
    db.add(src)
    db.flush()
    audit.record(db, admin, "source.create", "source", src.id, {"key": src.key})
    db.commit()
    return ser.source(src)


@router.patch("/sources/{source_id}")
def update_source(source_id: str, body: SourceUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    src = _get(db, Source, source_id)
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(src, k, v)
    audit.record(db, admin, "source.update", "source", src.id, {"fields": sorted(changes)})
    db.commit()
    return ser.source(src)


@router.post("/sources/{source_id}/check", dependencies=[Depends(rate_limit("manual_check", 30, 600))])
def check_source(source_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    src = _get(db, Source, source_id)
    if not src.enabled:
        raise HTTPException(status_code=409, detail="Source is disabled; enable it first")
    try:
        job = orchestrator.enqueue(db, src, "manual", admin.id)
    except orchestrator.JobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.record(db, admin, "source.check", "source", src.id, {"job_id": job.id})
    db.commit()
    orchestrator.submit(job.id)
    return ser.job(job)


@router.post("/sources/{source_id}/pause")
def pause_source(source_id: str, body: DecisionIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    src = _get(db, Source, source_id)
    src.health_status, src.paused_reason = "paused", body.note or "Paused by admin"
    audit.record(db, admin, "source.pause", "source", src.id, {"note": body.note})
    db.commit()
    for sid in orchestrator._linked_ids(db, src):
        s = db.get(Scholarship, sid)
        if s:
            trust.refresh_status(db, s)
    db.commit()
    return ser.source(src)


@router.post("/sources/{source_id}/resume")
def resume_source(source_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    src = _get(db, Source, source_id)
    src.health_status, src.paused_reason, src.next_check_at = "unknown", None, utcnow()
    src.consecutive_failures = 0
    audit.record(db, admin, "source.resume", "source", src.id, {})
    db.commit()
    return ser.source(src)


@router.post("/sources/{source_id}/test", dependencies=[Depends(rate_limit("source_test", 20, 600))])
def test_source(source_id: str, db: Session = Depends(get_db)):
    """Dry run: fetch and parse the first target without storing anything."""
    src = _get(db, Source, source_id)
    url = (src.target_urls or [src.base_url])[0]
    fetcher = SafeFetcher()
    try:
        res = fetcher.fetch(url, src.allowed_url_patterns)
    except FetchError as err:
        return {"ok": False, "url": url, "error_type": err.kind, "error": str(err), "http_status": err.status}
    finally:
        fetcher.close()
    out = {"ok": True, "url": url, "final_url": res.final_url, "http_status": res.status, "bytes": len(res.content),
           "content_type": res.content_type, "is_fixture": res.is_fixture, "etag": res.etag,
           "last_modified": res.last_modified, "log": res.log}
    if src.connector == "nsp_listing":
        schemes = parse_nsp_listing(res.content.decode("utf-8", errors="replace"))
        out["parsed"] = {"schemes": len(schemes), "sample": [s.as_dict() for s in schemes[:5]]}
    else:
        ex = extract(res.content, res.content_type, url)
        out["parsed"] = {"quality": ex.quality, "note": ex.note, "chars": len(ex.text), "excerpt": ex.text[:800],
                         "deadline_statements": find_deadline_statements(ex.text)[:5],
                         "closure_statements": find_closure_statements(ex.text)[:5]}
    return out


# ------------------------------------------------------------------ jobs

@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db), status: Optional[str] = None, source_id: Optional[str] = None,
              limit: int = Query(default=50, le=200)):
    stmt = select(CrawlJob).order_by(CrawlJob.queued_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(CrawlJob.status == status)
    if source_id:
        stmt = stmt.where(CrawlJob.source_id == source_id)
    return [ser.job(j) for j in db.scalars(stmt)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    j = _get(db, CrawlJob, job_id)
    docs = list(db.scalars(select(SourceDocument).where(SourceDocument.job_id == j.id)))
    return ser.job(j, with_log=True) | {"documents": [
        {"id": d.id, "url": d.url, "http_status": d.http_status, "content_sha256": d.content_sha256,
         "bytes": d.byte_size, "quality": d.extraction_quality, "not_modified": d.not_modified,
         "fetched_at": ser.iso(d.fetched_at)} for d in docs]}


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    j = _get(db, CrawlJob, job_id)
    if j.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")
    src = db.get(Source, j.source_id)
    if src.health_status == "paused":
        raise HTTPException(status_code=409, detail=f"Source is paused: {src.paused_reason}. Resume it first.")
    try:
        new = orchestrator.enqueue(db, src, "retry", admin.id, retry_of=j.id)
    except orchestrator.JobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.record(db, admin, "job.retry", "crawl_job", new.id, {"retry_of": j.id})
    db.commit()
    orchestrator.submit(new.id)
    return ser.job(new)


@router.get("/documents/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)):
    d = _get(db, SourceDocument, document_id)
    return {"id": d.id, "url": d.url, "final_url": d.final_url, "fetched_at": ser.iso(d.fetched_at),
            "http_status": d.http_status, "content_type": d.content_type, "content_sha256": d.content_sha256,
            "text_sha256": d.text_sha256, "bytes": d.byte_size, "etag": d.etag, "last_modified": d.last_modified,
            "quality": d.extraction_quality, "text_excerpt": d.text_excerpt, "not_modified": d.not_modified}


# ------------------------------------------------------------------ review

@router.get("/candidates")
def list_candidates(db: Session = Depends(get_db), status: str = "pending"):
    rows = db.scalars(select(Candidate).where(Candidate.status == status).order_by(Candidate.created_at.desc()))
    return [ser.candidate(c) for c in rows]


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: str, db: Session = Depends(get_db)):
    c = _get(db, Candidate, candidate_id)
    out = ser.candidate(c)
    if c.matched_scholarship_id:
        s = db.get(Scholarship, c.matched_scholarship_id)
        out["target"] = ser.scholarship_full(s) if s else None
    if c.document_id:
        d = db.get(SourceDocument, c.document_id)
        out["document"] = {"id": d.id, "url": d.url, "fetched_at": ser.iso(d.fetched_at),
                           "quality": d.extraction_quality} if d else None
    return out


@router.post("/candidates/{candidate_id}/approve")
def approve(candidate_id: str, body: ApproveIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = _get(db, Candidate, candidate_id)
    try:
        s = review.approve_candidate(db, c, admin, body.payload, body.note)
    except review.ReviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"scholarship_id": s.id, "version": s.version}


@router.post("/candidates/{candidate_id}/reject")
def reject(candidate_id: str, body: DecisionIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        review.reject_candidate(db, _get(db, Candidate, candidate_id), admin, body.note)
    except review.ReviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/candidates/{candidate_id}/link")
def link(candidate_id: str, body: LinkIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        s = review.link_candidate(db, _get(db, Candidate, candidate_id), body.scholarship_id, admin)
    except review.ReviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"scholarship_id": s.id, "version": s.version}


@router.post("/candidates/{candidate_id}/extract", dependencies=[Depends(rate_limit("extract", 20, 3600))])
def run_extraction(candidate_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = review.run_candidate_extraction(db, _get(db, Candidate, candidate_id), admin)
    return ser.candidate(c)


@router.get("/changes")
def list_changes(db: Session = Depends(get_db), status: str = "pending", limit: int = Query(default=100, le=500)):
    stmt = (select(ChangeEvent, Scholarship.name).outerjoin(Scholarship, Scholarship.id == ChangeEvent.scholarship_id)
            .order_by(ChangeEvent.detected_at.desc()).limit(limit))
    if status != "all":
        stmt = stmt.where(ChangeEvent.review_status == status)
    return [ser.change(ev, name) for ev, name in db.execute(stmt).all()]


@router.post("/changes/{change_id}/accept")
def accept_change(change_id: str, body: DecisionIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        review.decide_change(db, _get(db, ChangeEvent, change_id), admin, True, body.note)
    except review.ReviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/changes/{change_id}/reject")
def reject_change(change_id: str, body: DecisionIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        review.decide_change(db, _get(db, ChangeEvent, change_id), admin, False, body.note)
    except review.ReviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True}


# ------------------------------------------------------------------ data quality and datasets

@router.get("/quality")
def quality(db: Session = Depends(get_db)):
    published = list(db.scalars(select(Scholarship).where(Scholarship.is_published.is_(True))))
    unresolved = {}
    for f in ("education_rule", "academic_rule", "income_rule", "discipline_rule"):
        unresolved[f] = sum(1 for s in published if getattr(s, f) == "unknown")
    unresolved["deadline"] = sum(1 for s in published if s.deadline is None)
    return {
        "duplicate_candidates": find_duplicate_pairs(published),
        "unresolved_fields": unresolved,
        "stale": [{"id": s.id, "name": s.name, "last_checked_at": ser.iso(s.last_checked_at)}
                  for s in published if "stale_observation" in (s.verification_flags or [])],
        "never_checked": [{"id": s.id, "name": s.name} for s in published if s.last_checked_at is None],
        "conflicts": [{"id": s.id, "name": s.name} for s in published
                      if "conflicting_sources" in (s.verification_flags or [])],
    }


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)):
    return [{"id": d.id, "version": d.version, "dataset_name": d.dataset_name, "file_name": d.file_name,
             "file_sha256": d.file_sha256, "imported_at": ser.iso(d.imported_at), "rows": d.num_rows,
             "created": d.num_created, "updated": d.num_updated, "unchanged": d.num_unchanged,
             "rejected": d.num_rejected, "report": d.report}
            for d in db.scalars(select(DatasetVersion).order_by(DatasetVersion.imported_at.desc()))]


@router.post("/datasets/import")
async def upload_dataset(file: UploadFile = File(...), version: str = Form(..., max_length=64),
                         dataset_name: str = Form(..., max_length=200), mode: str = Form("review"),
                         admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    limit = get_settings().max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="File too large")
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Only .csv files are accepted")
    try:
        dv = import_dataset(db, data, file_name=file.filename, version=version, dataset_name=dataset_name,
                            mode=mode, actor_id=admin.id)
    except ImportError_ as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit.record(db, admin, "dataset.import", "dataset_version", dv.id, {"version": version, "mode": mode})
    db.commit()
    return {"id": dv.id, "created": dv.num_created, "updated": dv.num_updated, "rejected": dv.num_rejected}


@router.post("/scholarships/{scholarship_id}/publish")
def set_published(scholarship_id: str, published: bool = True, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    s = _get(db, Scholarship, scholarship_id)
    s.is_published = published
    audit.record(db, admin, "scholarship.publish" if published else "scholarship.unpublish", "scholarship", s.id, {})
    db.commit()
    return {"ok": True}


@router.get("/audit")
def audit_log(db: Session = Depends(get_db), limit: int = Query(default=100, le=500)):
    return [{"id": a.id, "actor_email": a.actor_email, "action": a.action, "entity_type": a.entity_type,
             "entity_id": a.entity_id, "details": a.details, "created_at": ser.iso(a.created_at)}
            for a in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))]


@router.get("/evaluation")
def evaluation_results():
    path = BACKEND_DIR.parent / "evaluation" / "results" / "latest.json"
    if not path.exists():
        return {"available": False, "message": "No evaluation has been run yet (python -m evaluation.run)."}
    return {"available": True, **json.loads(path.read_text(encoding="utf-8"))}
