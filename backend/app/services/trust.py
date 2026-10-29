"""Verification status and freshness.

Statuses are derived from stored evidence, change events and source health — never from a model guess.
Definitions (also shown in the UI and docs/TRUST_MODEL.md):

  official_source_confirmed  The latest successful check of an official source re-observed the current deadline.
  official_source_checked    An official source describing this record was checked successfully, but the
                             current deadline was not re-observed there.
  aggregator_only            Only aggregator/curated-dataset evidence exists; no official source has been checked.
  needs_review               A material change or candidate for this record awaits admin review.
  conflicting_sources        Two current official observations disagree on a material field.
  stale_observation          The last successful official check is older than the freshness policy allows.
  source_unavailable         The official source(s) linked to this record are currently failing or paused.
  deadline_not_verified      The deadline has never been observed by this system (it comes only from the dataset).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import load_config_file
from app.models import ChangeEvent, FieldEvidence, Scholarship, ScholarshipSource, Source, utcnow
from app.services.records import same_value

PRIMARY_ORDER = [
    "conflicting_sources",
    "source_unavailable",
    "needs_review",
    "stale_observation",
    "deadline_not_verified",
    "official_source_confirmed",
    "official_source_checked",
    "aggregator_only",
]
OFFICIAL = {"official", "fixture"}

STATUS_LABELS = {
    "official_source_confirmed": "Official source confirmed",
    "official_source_checked": "Official source checked",
    "aggregator_only": "Aggregator / dataset only",
    "needs_review": "Needs review",
    "conflicting_sources": "Conflicting sources",
    "stale_observation": "Stale observation",
    "source_unavailable": "Source unavailable",
    "deadline_not_verified": "Deadline not verified",
}


def _freshness() -> dict:
    return load_config_file("policies.json")["freshness"]


def availability(s: Scholarship, today: Optional[date] = None) -> dict:
    """Application window status computed from dates (not from the stored status text)."""
    today = today or date.today()
    days_left = (s.deadline - today).days if s.deadline else None
    if s.status_reported and "closed" in s.status_reported.lower():
        state = "closed"
    elif s.deadline is None:
        state = "unknown"
    elif today > s.deadline:
        state = "closed"
    elif s.open_date and today < s.open_date:
        state = "upcoming"
    else:
        state = "open"
    approaching = state == "open" and days_left is not None and days_left <= _freshness()["deadline_approaching_days"]
    return {"state": state, "days_left": days_left, "deadline_approaching": approaching}


def max_age_hours(s: Scholarship, today: Optional[date] = None) -> int:
    f = _freshness()
    av = availability(s, today)
    if av["deadline_approaching"]:
        return f["max_age_hours_deadline_approaching"]
    if av["state"] in ("open", "upcoming"):
        return f["max_age_hours_open"]
    return f["max_age_hours_closed_or_unknown"]


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def compute_status(db: Session, s: Scholarship, now: Optional[datetime] = None) -> tuple[str, list[str], dict]:
    now = now or utcnow()
    flags: set[str] = set()
    details: dict = {}
    db.flush()  # sessions do not autoflush; pending evidence/change rows must be visible to the queries below

    evidence = list(db.scalars(select(FieldEvidence).where(
        FieldEvidence.scholarship_id == s.id, FieldEvidence.is_current.is_(True))))
    official_ev = [e for e in evidence if e.source_classification in OFFICIAL]
    deadline_official = [e for e in official_ev if e.field == "deadline"]

    links = list(db.scalars(select(ScholarshipSource).where(ScholarshipSource.scholarship_id == s.id)))
    source_ids = {l.source_id for l in links}
    sources = list(db.scalars(select(Source).where(Source.id.in_(source_ids)))) if source_ids else []
    official_sources = [src for src in sources if src.classification in OFFICIAL]

    if not official_ev and not official_sources:
        flags.add("aggregator_only")

    if not deadline_official:
        flags.add("deadline_not_verified")
    else:
        latest = max(deadline_official, key=lambda e: _aware(e.retrieved_at) or now)
        if same_value(latest.value, s.deadline):
            flags.add("official_source_confirmed")
        else:
            flags.add("official_source_checked")
    if official_sources and "official_source_confirmed" not in flags:
        flags.add("official_source_checked")

    # Conflicts: current official observations from different sources disagreeing on the same field.
    by_field: dict[str, list[FieldEvidence]] = {}
    for e in official_ev:
        by_field.setdefault(e.field, []).append(e)
    conflicts = []
    for fname, evs in by_field.items():
        distinct = {str(e.value) for e in evs}
        if len({e.source_key for e in evs}) > 1 and len(distinct) > 1:
            conflicts.append({"field": fname, "values": [{"source": e.source_key, "value": e.value} for e in evs]})
    if conflicts:
        flags.add("conflicting_sources")
        details["conflicts"] = conflicts

    pending = db.scalar(select(func.count()).select_from(ChangeEvent).where(
        ChangeEvent.scholarship_id == s.id, ChangeEvent.review_status == "pending",
        ChangeEvent.materiality == "material"))
    if pending:
        flags.add("needs_review")
        details["pending_changes"] = pending

    if official_sources:
        unhealthy = [src.key for src in official_sources if src.health_status in ("failing", "paused") or not src.enabled]
        if unhealthy and len(unhealthy) == len(official_sources):
            flags.add("source_unavailable")
            details["unavailable_sources"] = unhealthy

    last_checked = _aware(s.last_checked_at)
    if last_checked is not None:
        age_h = (now - last_checked).total_seconds() / 3600
        details["hours_since_check"] = round(age_h, 1)
        if age_h > max_age_hours(s, now.date()):
            flags.add("stale_observation")
    elif official_sources:
        flags.add("stale_observation")

    primary = next(st for st in PRIMARY_ORDER if st in flags) if flags else "aggregator_only"
    return primary, [st for st in PRIMARY_ORDER if st in flags], details


def refresh_status(db: Session, s: Scholarship) -> None:
    primary, flags, _ = compute_status(db, s)
    s.verification_status = primary
    s.verification_flags = flags


def refresh_all(db: Session) -> int:
    count = 0
    for s in db.scalars(select(Scholarship)):
        refresh_status(db, s)
        count += 1
    return count


def recently_changed(db: Session, s: Scholarship, now: Optional[datetime] = None) -> bool:
    now = now or utcnow()
    since = now - timedelta(days=_freshness()["recently_changed_days"])
    return bool(db.scalar(select(func.count()).select_from(ChangeEvent).where(
        ChangeEvent.scholarship_id == s.id, ChangeEvent.detected_at >= since,
        ChangeEvent.materiality == "material")))
