"""Public, read-only endpoints: catalogue, scholarship detail with evidence/history, change feed, metadata."""
from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api import serializers as ser
from app.core.config import get_settings, load_config_file
from app.database import get_db
from app.models import (
    ChangeEvent,
    FieldEvidence,
    Scholarship,
    ScholarshipSource,
    ScholarshipVersion,
    Source,
    utcnow,
)
from app.services import trust
from app.services.crawl import scheduler
from app.services.extraction import llm
from app.services.normalize import vocab

router = APIRouter(prefix="/api", tags=["Public"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "ok", "scheduler": scheduler.state, "demo_mode": get_settings().demo_mode}


@router.get("/meta/vocabulary")
def vocabulary():
    v = vocab()
    return {k: v[k] for k in ("education_levels", "disciplines", "categories", "genders", "states",
                              "special_circumstances")} | {
        "trust_statuses": trust.STATUS_LABELS, "freshness_policy": load_config_file("policies.json")["freshness"]}


@router.get("/stats/public")
def public_stats(db: Session = Depends(get_db)):
    published = db.scalar(select(func.count()).select_from(Scholarship).where(Scholarship.is_published.is_(True)))
    by_status = dict(db.execute(select(Scholarship.verification_status, func.count())
                                .where(Scholarship.is_published.is_(True)).group_by(Scholarship.verification_status)).all())
    sources = list(db.scalars(select(Source).where(Source.enabled.is_(True))))
    last_success = max((s.last_success_at for s in sources if s.last_success_at), default=None)
    week = utcnow() - timedelta(days=7)
    changes = db.scalar(select(func.count()).select_from(ChangeEvent).where(
        ChangeEvent.detected_at >= week, ChangeEvent.materiality == "material",
        ChangeEvent.review_status.in_(("auto_accepted", "accepted"))))
    return {"published_scholarships": published, "by_verification_status": by_status,
            "enabled_sources": len(sources), "last_successful_check": ser.iso(last_success),
            "material_changes_last_7_days": changes, "llm": llm.status(), "demo_mode": get_settings().demo_mode}


@router.get("/scholarships")
def list_scholarships(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(default=None, max_length=100),
    education_level: Optional[str] = None,
    provider_type: Optional[str] = None,
    availability: Optional[Literal["open", "closed", "upcoming", "unknown"]] = None,
    verification_status: Optional[str] = None,
    state: Optional[str] = None,
    sort: Literal["deadline", "name", "amount", "recent"] = "deadline",
):
    stmt = select(Scholarship).where(Scholarship.is_published.is_(True))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Scholarship.name).like(like), func.lower(Scholarship.provider).like(like),
                              func.lower(Scholarship.description).like(like)))
    if provider_type:
        stmt = stmt.where(Scholarship.provider_type == provider_type)
    if verification_status:
        stmt = stmt.where(Scholarship.verification_status == verification_status)
    items = list(db.scalars(stmt))
    if education_level:
        items = [s for s in items if education_level in (s.education_levels or [])]
    if state:
        items = [s for s in items if not s.eligible_states or state in s.eligible_states]
    rows = [{**ser.scholarship_full(s)} for s in items]
    if availability:
        rows = [r for r in rows if r["availability"]["state"] == availability]
    keyf = {
        "deadline": lambda r: (r["availability"]["state"] == "closed", r["deadline"] or "9999"),
        "name": lambda r: r["name"].lower(),
        "amount": lambda r: -(r["amount_max_inr"] or 0),
        "recent": lambda r: r["updated_at"] or "",
    }[sort]
    rows.sort(key=keyf, reverse=(sort == "recent"))
    return {"total": len(rows), "items": rows}


@router.get("/scholarships/{scholarship_id}")
def scholarship_detail(scholarship_id: str, db: Session = Depends(get_db)):
    s = db.get(Scholarship, scholarship_id)
    if s is None or not s.is_published:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    primary, flags, details = trust.compute_status(db, s)
    evidence = list(db.scalars(select(FieldEvidence).where(FieldEvidence.scholarship_id == s.id)
                               .order_by(FieldEvidence.retrieved_at.desc())))
    links = list(db.scalars(select(ScholarshipSource).where(ScholarshipSource.scholarship_id == s.id)))
    linked_sources = {l.source_id: l for l in links}
    monitors = list(db.scalars(select(Source).where(or_(Source.id.in_(linked_sources.keys()),
                                                       Source.linked_scholarship_id == s.id))))
    changes = list(db.scalars(select(ChangeEvent).where(ChangeEvent.scholarship_id == s.id)
                              .order_by(ChangeEvent.detected_at.desc())))
    versions = list(db.scalars(select(ScholarshipVersion).where(ScholarshipVersion.scholarship_id == s.id)
                               .order_by(ScholarshipVersion.version.desc())))
    return {
        "scholarship": ser.scholarship_full(s),
        "trust": {"primary": primary, "label": trust.STATUS_LABELS.get(primary), "flags": flags,
                  "flag_labels": {f: trust.STATUS_LABELS[f] for f in flags}, "details": details,
                  "max_age_hours": trust.max_age_hours(s)},
        "evidence": {
            "current": [ser.evidence(e) for e in evidence if e.is_current],
            "history": [ser.evidence(e) for e in evidence if not e.is_current][:100],
        },
        "sources": [{
            **{k: v for k, v in ser.source(src).items() if k in (
                "id", "key", "name", "organization", "classification", "health_status", "last_success_at",
                "last_attempt_at", "last_error", "target_urls", "is_fixture", "enabled", "paused_reason")},
            "currently_listed": linked_sources[src.id].currently_listed if src.id in linked_sources else None,
            "last_seen_at": ser.iso(linked_sources[src.id].last_seen_at) if src.id in linked_sources else None,
            "match_method": linked_sources[src.id].match_method if src.id in linked_sources else "configured",
        } for src in monitors],
        "changes": [ser.change(c) for c in changes if c.materiality != "cosmetic"],
        "versions": [{"version": v.version, "reason": v.reason, "created_at": ser.iso(v.created_at),
                      "deadline": v.snapshot.get("deadline"), "open_date": v.snapshot.get("open_date")}
                     for v in versions],
    }


@router.get("/scholarships/{scholarship_id}/versions/{version}")
def scholarship_version(scholarship_id: str, version: int, db: Session = Depends(get_db)):
    v = db.scalar(select(ScholarshipVersion).where(ScholarshipVersion.scholarship_id == scholarship_id,
                                                   ScholarshipVersion.version == version))
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"version": v.version, "reason": v.reason, "created_at": ser.iso(v.created_at), "snapshot": v.snapshot}


@router.get("/feed/changes")
def change_feed(db: Session = Depends(get_db), days: int = Query(default=30, ge=1, le=365),
                include_pending: bool = False):
    since = utcnow() - timedelta(days=days)
    statuses = ["auto_accepted", "accepted"] + (["pending"] if include_pending else [])
    rows = db.execute(
        select(ChangeEvent, Scholarship.name)
        .join(Scholarship, Scholarship.id == ChangeEvent.scholarship_id)
        .where(ChangeEvent.detected_at >= since, ChangeEvent.materiality == "material",
               ChangeEvent.review_status.in_(statuses), Scholarship.is_published.is_(True))
        .order_by(ChangeEvent.detected_at.desc()).limit(200)).all()
    new_records = list(db.scalars(select(Scholarship).where(
        Scholarship.is_published.is_(True), Scholarship.origin == "crawler",
        Scholarship.first_discovered_at >= since).order_by(Scholarship.first_discovered_at.desc())))
    return {
        "since": since.isoformat(),
        "changes": [ser.change(ev, name) for ev, name in rows],
        "new_scholarships": [{"id": s.id, "name": s.name, "provider": s.provider,
                              "first_discovered_at": ser.iso(s.first_discovered_at),
                              "deadline": ser.iso(s.deadline)} for s in new_records],
    }
