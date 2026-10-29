"""Field-level provenance, change events and record versioning.

Every write to a published scholarship goes through this module so that:
  * each observed value is stored as FieldEvidence (who said what, where, when, how),
  * differences become ChangeEvents classified by materiality,
  * only policy-approved changes are applied automatically; others wait for review,
  * each content change produces a new ScholarshipVersion (history is never overwritten).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import load_config_file
from app.models import ChangeEvent, FieldEvidence, Scholarship, ScholarshipVersion, utcnow

CONTENT_FIELDS = [
    "name", "provider", "provider_type", "scholarship_type", "education_rule", "education_levels",
    "class_range", "allowed_years", "courses_text", "fields_text", "year_of_study_text", "discipline_rule",
    "disciplines", "academic_rule", "min_percentage", "min_cgpa", "cgpa_scale", "academic_has_alternative",
    "academic_note", "income_rule", "income_limit", "income_currency", "income_note", "genders", "categories",
    "category_alt_tags", "category_note", "disability_rule", "min_disability_percent", "eligible_states",
    "domicile_note", "conditions", "special_note", "age_note", "exclusions", "amount_text", "amount_max_inr",
    "amount_frequency", "required_documents", "open_date", "deadline", "renewal_type", "status_reported",
    "application_method", "application_url", "official_source_url", "description", "eligibility_summary",
    "selection_process", "academic_year",
]

# Fields for which an evidence row is written on import (the ones eligibility and deadlines depend on).
EVIDENCED_FIELDS = [
    "deadline", "open_date", "renewal_type", "education_levels", "disciplines", "academic_rule", "min_percentage",
    "min_cgpa", "income_rule", "income_limit", "genders", "categories", "disability_rule", "eligible_states",
    "conditions", "amount_text", "required_documents", "application_url", "official_source_url",
]

EMPTY = (None, "", [], {}, "unknown")


def jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    return value


def snapshot(s: Scholarship) -> dict:
    return {f: jsonable(getattr(s, f)) for f in CONTENT_FIELDS}


def content_hash(snap: dict) -> str:
    return hashlib.sha256(json.dumps(snap, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def same_value(a: Any, b: Any) -> bool:
    a, b = jsonable(a), jsonable(b)
    if isinstance(a, list) and isinstance(b, list):
        try:
            return sorted(map(str, a)) == sorted(map(str, b))
        except TypeError:
            return a == b
    if isinstance(a, float) or isinstance(b, float):
        try:
            return a is not None and b is not None and abs(float(a) - float(b)) < 1e-6
        except (TypeError, ValueError):
            return False
    return a == b


def policies() -> dict:
    return load_config_file("policies.json")


def materiality(field_name: str) -> str:
    cp = policies()["change_policy"]
    if field_name in cp["material_fields"]:
        return "material"
    if field_name in cp["cosmetic_fields"]:
        return "cosmetic"
    return "minor"


def auto_acceptable(field_name: str, classification: str, method: str) -> bool:
    cp = policies()["change_policy"]
    return (
        classification in cp["auto_accept_classifications"]
        and method in cp["auto_accept_methods"]
        and field_name in cp["auto_accept_fields"]
    )


@dataclass
class ObservationContext:
    """Where an observation came from. Shared by all fields observed in one retrieval."""

    source_key: str
    classification: str
    method: str
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    document_id: Optional[str] = None
    job_id: Optional[str] = None
    verification_status: str = "source_checked"
    snippets: dict[str, tuple[str, Optional[str]]] = field(default_factory=dict)  # field -> (snippet, location)


def add_evidence(db: Session, s: Scholarship, field_name: str, value: Any, ctx: ObservationContext,
                 verification_status: Optional[str] = None) -> FieldEvidence:
    db.execute(
        update(FieldEvidence)
        .where(
            FieldEvidence.scholarship_id == s.id,
            FieldEvidence.field == field_name,
            FieldEvidence.source_key == ctx.source_key,
            FieldEvidence.is_current.is_(True),
        )
        .values(is_current=False)
    )
    snippet, location = ctx.snippets.get(field_name, (None, None))
    ev = FieldEvidence(
        scholarship_id=s.id,
        field=field_name,
        value=jsonable(value),
        source_id=ctx.source_id,
        source_key=ctx.source_key,
        source_url=ctx.source_url,
        source_classification=ctx.classification,
        snippet=snippet,
        location=location,
        retrieved_at=ctx.retrieved_at or utcnow(),
        extraction_method=ctx.method,
        verification_status=verification_status or ctx.verification_status,
        document_id=ctx.document_id,
        record_version=s.version,
        is_current=True,
    )
    db.add(ev)
    return ev


def observe_field(db: Session, s: Scholarship, field_name: str, new_value: Any, ctx: ObservationContext
                  ) -> Optional[ChangeEvent]:
    """Record an observation; create a change event if it differs from the published value.

    Returns the ChangeEvent (auto-accepted and applied, or pending) or None when the value is unchanged.
    """
    old_value = getattr(s, field_name)
    if same_value(old_value, new_value):
        add_evidence(db, s, field_name, new_value, ctx, verification_status="confirmed")
        return None

    add_evidence(db, s, field_name, new_value, ctx)
    if new_value in EMPTY and old_value not in EMPTY:
        kind = "removed"
    elif old_value in EMPTY:
        kind = "added"
    else:
        kind = "changed"
    # A source that stops stating a value is not evidence that the value no longer applies.
    auto = kind != "removed" and auto_acceptable(field_name, ctx.classification, ctx.method)
    snippet, _loc = ctx.snippets.get(field_name, (None, None))
    event = ChangeEvent(
        scholarship_id=s.id,
        source_id=ctx.source_id,
        job_id=ctx.job_id,
        document_id=ctx.document_id,
        field=field_name,
        change_kind=kind,
        old_value=jsonable(old_value),
        new_value=jsonable(new_value),
        materiality=materiality(field_name),
        source_url=ctx.source_url,
        evidence_snippet=snippet,
        method=ctx.method,
        review_status="auto_accepted" if auto else "pending",
    )
    db.add(event)
    if auto:
        setattr(s, field_name, new_value)
    return event


def commit_version(db: Session, s: Scholarship, reason: str, actor_id: Optional[str] = None,
                   events: Optional[list[ChangeEvent]] = None) -> bool:
    """Write a new version if the record content changed. Returns True when a version was created."""
    snap = snapshot(s)
    digest = content_hash(snap)
    if digest == s.content_hash:
        return False
    first = not s.content_hash
    if not first:
        s.version += 1
    s.content_hash = digest
    db.flush()
    db.add(ScholarshipVersion(
        scholarship_id=s.id, version=s.version, snapshot=snap, content_hash=digest, reason=reason, created_by=actor_id
    ))
    for ev in events or []:
        if ev.review_status in ("auto_accepted", "accepted"):
            ev.applied_version = s.version
    return True


def coerce_field_value(field_name: str, value: Any) -> Any:
    """Convert JSON values (from change events / candidates) back to model types."""
    if field_name in ("deadline", "open_date", "source_published_at") and isinstance(value, str):
        return date.fromisoformat(value)
    return value


def apply_reviewed_change(db: Session, event: ChangeEvent, s: Scholarship, actor_id: str) -> None:
    setattr(s, event.field, coerce_field_value(event.field, event.new_value))
    event.review_status = "accepted"
    event.reviewed_by = actor_id
    event.reviewed_at = utcnow()
    commit_version(db, s, f"Accepted change to {event.field}", actor_id, [event])


def current_evidence(db: Session, scholarship_id: str) -> list[FieldEvidence]:
    return list(
        db.scalars(
            select(FieldEvidence)
            .where(FieldEvidence.scholarship_id == scholarship_id, FieldEvidence.is_current.is_(True))
            .order_by(FieldEvidence.field, FieldEvidence.retrieved_at.desc())
        )
    )
