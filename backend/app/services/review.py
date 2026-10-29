"""Human review: candidates (new/updated records) and pending change events."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candidate, ChangeEvent, Scholarship, ScholarshipSource, Source, SourceDocument, User, utcnow
from app.services import audit, trust
from app.services.connectors.base import read_document_bytes
from app.services.extraction import extractor, llm
from app.services.extraction.text import extract
from app.services.normalize import normalize_name
from app.services.records import (
    CONTENT_FIELDS,
    ObservationContext,
    add_evidence,
    coerce_field_value,
    commit_version,
    observe_field,
)
from app.services.sources.fetcher import FetchError, SafeFetcher

EDITABLE_FIELDS = set(CONTENT_FIELDS)
REQUIRED_FOR_PUBLICATION = ("name", "provider", "official_source_url")


class ReviewError(Exception):
    pass


def _coerce_payload(payload: dict) -> dict:
    out = {}
    for k, v in payload.items():
        if k not in EDITABLE_FIELDS:
            continue
        try:
            out[k] = coerce_field_value(k, v) if v not in ("", None) else None
        except ValueError as exc:
            raise ReviewError(f"Invalid value for {k}: {v!r}") from exc
    return out


def publication_problems(payload: dict, cand: Candidate) -> list[str]:
    problems = [f"Missing required field: {f}" for f in REQUIRED_FOR_PUBLICATION if not payload.get(f)]
    problems += [f"Unresolved validation error: {e}" for e in (cand.validation or {}).get("errors", [])]
    od, dl = payload.get("open_date"), payload.get("deadline")
    if isinstance(od, date) and isinstance(dl, date) and od > dl:
        problems.append("Opening date is after the deadline")
    return problems


def approve_candidate(db: Session, cand: Candidate, actor: User, edited_payload: Optional[dict] = None,
                      note: Optional[str] = None) -> Scholarship:
    if cand.status != "pending":
        raise ReviewError(f"Candidate is already {cand.status}")
    original = _coerce_payload(cand.payload or {})
    payload = _coerce_payload(edited_payload) if edited_payload is not None else dict(original)
    problems = publication_problems(payload, cand)
    if problems:
        raise ReviewError("; ".join(problems))
    src = db.get(Source, cand.source_id) if cand.source_id else None
    doc = db.get(SourceDocument, cand.document_id) if cand.document_id else None
    now = utcnow()
    snippets = {f: (e.get("snippet"), e.get("location")) for f, e in (cand.evidence or {}).items()}
    src_ctx = ObservationContext(
        source_key=src.key if src else "manual", classification=src.classification if src else "manual",
        method=cand.extraction_method if cand.extraction_method not in ("llm_failed",) else "manual",
        source_id=src.id if src else None, source_url=doc.url if doc else payload.get("official_source_url"),
        retrieved_at=doc.fetched_at if doc else now, document_id=doc.id if doc else None, snippets=snippets)
    admin_ctx = ObservationContext(source_key=f"admin:{actor.email}", classification="manual", method="manual",
                                   source_url=None, retrieved_at=now, verification_status="admin_entered")
    edited = {k for k in payload if k not in original or original.get(k) != payload.get(k)}

    if cand.kind == "new":
        payload.setdefault("normalized_name", normalize_name(payload["name"]))
        s = Scholarship(**{k: v for k, v in payload.items() if k in EDITABLE_FIELDS},
                        normalized_name=normalize_name(payload["name"]), origin="crawler",
                        first_discovered_at=cand.created_at, last_checked_at=doc.fetched_at if doc else None)
        db.add(s)
        db.flush()
        for f, v in payload.items():
            if f in EDITABLE_FIELDS and v not in (None, [], ""):
                add_evidence(db, s, f, v, admin_ctx if f in edited else src_ctx)
        if src and cand.external_key:
            db.add(ScholarshipSource(scholarship_id=s.id, source_id=src.id, external_key=cand.external_key,
                                     match_method="admin", last_seen_at=doc.fetched_at if doc else now))
        if s.deadline and "deadline" not in edited and src and src.classification in ("official", "fixture"):
            s.last_verified_at = doc.fetched_at if doc else now
        commit_version(db, s, "Published from reviewed candidate", actor.id)
    else:
        s = db.get(Scholarship, cand.matched_scholarship_id)
        if s is None:
            raise ReviewError("Update candidate has no target record")
        events = []
        for f, v in payload.items():
            if f not in EDITABLE_FIELDS or v in (None, [], ""):
                continue
            ev = observe_field(db, s, f, v, admin_ctx if f in edited else src_ctx)
            if ev:
                setattr(s, f, v)
                ev.review_status, ev.reviewed_by, ev.reviewed_at = "accepted", actor.id, now
                ev.review_note = f"Accepted with candidate {cand.id}"
                events.append(ev)
        commit_version(db, s, "Reviewed update candidate", actor.id, events)

    cand.status, cand.reviewed_by, cand.reviewed_at, cand.review_note = "approved", actor.id, now, note
    cand.matched_scholarship_id = s.id
    trust.refresh_status(db, s)
    audit.record(db, actor, "candidate.approve", "candidate", cand.id,
                 {"scholarship_id": s.id, "kind": cand.kind, "edited_fields": sorted(edited)})
    db.commit()
    return s


def link_candidate(db: Session, cand: Candidate, scholarship_id: str, actor: User) -> Scholarship:
    """Admin confirms that a 'new' candidate is actually an existing record (resolves a possible duplicate)."""
    if cand.status != "pending":
        raise ReviewError(f"Candidate is already {cand.status}")
    s = db.get(Scholarship, scholarship_id)
    src = db.get(Source, cand.source_id) if cand.source_id else None
    if s is None or src is None or not cand.external_key:
        raise ReviewError("Candidate cannot be linked")
    doc = db.get(SourceDocument, cand.document_id) if cand.document_id else None
    db.add(ScholarshipSource(scholarship_id=s.id, source_id=src.id, external_key=cand.external_key,
                             match_method="admin", last_seen_at=doc.fetched_at if doc else utcnow()))
    ctx = ObservationContext(
        source_key=src.key, classification=src.classification, method=cand.extraction_method, source_id=src.id,
        source_url=doc.url if doc else None, retrieved_at=doc.fetched_at if doc else utcnow(),
        document_id=doc.id if doc else None,
        snippets={f: (e.get("snippet"), e.get("location")) for f, e in (cand.evidence or {}).items()})
    events = []
    for f in ("deadline", "open_date", "renewal_type"):
        v = (cand.payload or {}).get(f)
        if v not in (None, "", "unknown"):
            ev = observe_field(db, s, f, coerce_field_value(f, v), ctx)
            if ev:
                events.append(ev)
    if doc:
        s.last_checked_at = doc.fetched_at
        if s.deadline and str(s.deadline) == (cand.payload or {}).get("deadline"):
            s.last_verified_at = doc.fetched_at
    commit_version(db, s, f"Linked to {src.name}", actor.id, events)
    cand.status, cand.reviewed_by, cand.reviewed_at = "approved", actor.id, utcnow()
    cand.matched_scholarship_id, cand.review_note = s.id, "Linked to existing record"
    trust.refresh_status(db, s)
    audit.record(db, actor, "candidate.link", "candidate", cand.id, {"scholarship_id": s.id})
    db.commit()
    return s


def reject_candidate(db: Session, cand: Candidate, actor: User, note: Optional[str]) -> None:
    if cand.status != "pending":
        raise ReviewError(f"Candidate is already {cand.status}")
    cand.status, cand.reviewed_by, cand.reviewed_at, cand.review_note = "rejected", actor.id, utcnow(), note
    audit.record(db, actor, "candidate.reject", "candidate", cand.id, {"note": note})
    db.commit()


def decide_change(db: Session, ev: ChangeEvent, actor: User, accept: bool, note: Optional[str]) -> None:
    if ev.review_status != "pending":
        raise ReviewError(f"Change is already {ev.review_status}")
    s = db.get(Scholarship, ev.scholarship_id) if ev.scholarship_id else None
    if accept:
        if s is not None and ev.field in EDITABLE_FIELDS:
            setattr(s, ev.field, coerce_field_value(ev.field, ev.new_value))
            ev.review_status = "accepted"
            commit_version(db, s, f"Accepted change to {ev.field}", actor.id, [ev])
        else:
            ev.review_status = "accepted"  # acknowledgement (e.g. page content or listing presence)
    else:
        ev.review_status = "rejected"
    ev.reviewed_by, ev.reviewed_at, ev.review_note = actor.id, utcnow(), note
    if s is not None:
        trust.refresh_status(db, s)
    audit.record(db, actor, "change.accept" if accept else "change.reject", "change_event", ev.id,
                 {"field": ev.field, "scholarship_id": ev.scholarship_id, "note": note})
    db.commit()


def run_candidate_extraction(db: Session, cand: Candidate, actor: User, fetcher: Optional[SafeFetcher] = None) -> Candidate:
    """Run LLM extraction for a candidate, using its stored document or (for listing candidates) its guideline."""
    src = db.get(Source, cand.source_id) if cand.source_id else None
    doc = db.get(SourceDocument, cand.document_id) if cand.document_id else None
    text, url = None, None
    guideline = (cand.payload or {}).get("official_source_url")
    if doc and doc.content_type and ("pdf" in doc.content_type or "html" in doc.content_type) and \
            cand.extraction_method != "nsp_listing_parser":
        data = read_document_bytes(doc)
        text, url = (extract(data, doc.content_type, doc.url).text if data else None), doc.url
    elif guideline and src:
        own = fetcher is None
        fetcher = fetcher or SafeFetcher()
        try:
            res = fetcher.fetch(guideline, src.allowed_url_patterns)
        except FetchError as err:
            cand.extraction_status, cand.extraction_error = "failed", f"Could not fetch guideline ({err.kind}): {err}"
            db.commit()
            return cand
        finally:
            if own:
                fetcher.close()
        ex = extract(res.content, res.content_type, guideline)
        if ex.quality in ("empty", "needs_ocr"):
            cand.extraction_status, cand.extraction_error = "failed", f"Guideline text unusable: {ex.note}"
            db.commit()
            return cand
        text, url = ex.text, guideline
    if not text:
        cand.extraction_status, cand.extraction_error = "failed", "No document text available for extraction"
        db.commit()
        return cand
    try:
        result = extractor.run_extraction(text, url)
    except llm.LLMError as err:
        cand.extraction_status, cand.extraction_error = "failed", f"{err.kind}: {err}"
        audit.record(db, actor, "candidate.extract_failed", "candidate", cand.id, {"kind": err.kind})
        db.commit()
        return cand
    merged = dict(cand.payload or {})
    evidence = dict(cand.evidence or {})
    for k, v in result.payload.items():
        # Listing-observed dates stay authoritative; extraction fills gaps and adds eligibility fields.
        if k in ("deadline", "open_date") and merged.get(k):
            if merged[k] != v:
                result.validation["warnings"].append(f"{k}: guideline says {v}, listing says {merged[k]} (listing kept)")
            continue
        merged[k] = v
        if k in result.evidence:
            evidence[k] = {**result.evidence[k], "document": url}
    cand.payload, cand.evidence = merged, evidence
    prior = cand.validation or {}
    cand.validation = {**result.validation, "warnings": prior.get("warnings", [])[:0] + result.validation["warnings"]}
    cand.extraction_status, cand.extraction_error = "succeeded", None
    cand.llm_provider, cand.llm_model = result.provider, result.model
    audit.record(db, actor, "candidate.extract", "candidate", cand.id,
                 {"fields": sorted(result.payload), "unsupported": len(result.validation["unsupported"])})
    db.commit()
    return cand
