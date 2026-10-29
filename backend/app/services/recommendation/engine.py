"""Recommendation pipeline: hard eligibility -> unresolved info -> soft score -> availability -> explanation."""
from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import load_config_file
from app.models import FieldEvidence, RecommendationSnapshot, Scholarship, StudentAnswer, StudentProfile, utcnow
from app.services import trust
from app.services.recommendation import eligibility, scoring

OUTCOME_RANK = {"eligible": 0, "eligible_pending_verification": 1, "potential_match": 2, "not_eligible": 3}
AVAIL_RANK = {"open": 0, "upcoming": 1, "unknown": 2, "closed": 3}


def best_evidence(db: Session, scholarship_ids: list[str]) -> dict[str, dict[str, dict]]:
    """Highest-precedence current evidence per (scholarship, field)."""
    prec = load_config_file("policies.json")["source_precedence"]
    out: dict[str, dict[str, dict]] = {}
    rows = db.scalars(select(FieldEvidence).where(
        FieldEvidence.scholarship_id.in_(scholarship_ids), FieldEvidence.is_current.is_(True)))
    for e in rows:
        cur = out.setdefault(e.scholarship_id, {}).get(e.field)
        rank = (prec.get(e.source_classification, 0), e.retrieved_at.isoformat() if e.retrieved_at else "")
        if cur is None or rank > cur["_rank"]:
            out[e.scholarship_id][e.field] = {
                "_rank": rank, "source_url": e.source_url, "source_key": e.source_key, "snippet": e.snippet,
                "location": e.location, "method": e.extraction_method, "verification_status": e.verification_status,
                "classification": e.source_classification,
                "retrieved_at": e.retrieved_at.isoformat() if e.retrieved_at else None,
            }
    for fields in out.values():
        for v in fields.values():
            v.pop("_rank", None)
    return out


def headline(outcome: str, avail: dict, status: str) -> str:
    if outcome == "not_eligible":
        return eligibility.OUTCOME_LABELS[outcome]
    if avail["state"] == "closed":
        return "Matches your profile but applications are closed" if outcome == "eligible" else \
            eligibility.OUTCOME_LABELS[outcome] + " · applications closed"
    if avail["deadline_approaching"]:
        return eligibility.OUTCOME_LABELS[outcome] + f" · deadline in {avail['days_left']} days"
    return eligibility.OUTCOME_LABELS[outcome]


def evaluate_one(student: Any, s: Scholarship, answers: dict[str, str], evidence: dict[str, dict],
                 today: Optional[date] = None) -> dict:
    criteria = eligibility.evaluate(student, s, answers)
    for c in criteria:
        field = eligibility.CRITERION_EVIDENCE_FIELD.get(c["key"]) or ("conditions" if ":" in c["key"] or c["key"] == "citizenship" else None)
        c["evidence"] = evidence.get(field) if field else None
    outcome = eligibility.outcome(criteria)
    avail = trust.availability(s, today)
    result = {
        "scholarship_id": s.id,
        "outcome": outcome,
        "outcome_label": eligibility.OUTCOME_LABELS[outcome],
        "headline": headline(outcome, avail, s.verification_status),
        "availability": avail,
        "verification_status": s.verification_status,
        "verification_label": trust.STATUS_LABELS.get(s.verification_status, s.verification_status),
        "requires_verification": s.verification_status not in ("official_source_confirmed",),
        "criteria": criteria,
        "deadline_evidence": evidence.get("deadline"),
        "relevance": None,
    }
    if outcome != "not_eligible":
        result["relevance"] = scoring.score(student, s, criteria)
    return result


def answers_for(db: Session, profile_id: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for a in db.scalars(select(StudentAnswer).where(StudentAnswer.profile_id == profile_id)):
        out.setdefault(a.scholarship_id, {})[a.criterion_key] = a.answer
    return out


def recommend(db: Session, profile: StudentProfile, today: Optional[date] = None) -> dict:
    schs = list(db.scalars(select(Scholarship).where(Scholarship.is_published.is_(True))))
    ev = best_evidence(db, [s.id for s in schs])
    answers = answers_for(db, profile.id)
    results = []
    for s in schs:
        r = evaluate_one(profile, s, answers.get(s.id, {}), ev.get(s.id, {}), today)
        r["scholarship"] = summary(s)
        results.append(r)
    results.sort(key=lambda r: (
        OUTCOME_RANK[r["outcome"]], AVAIL_RANK[r["availability"]["state"]],
        -(r["relevance"]["score"] if r["relevance"] else 0)))

    missing = Counter()
    labels: dict[str, str] = {}
    for r in results:
        if r["outcome"] == "not_eligible":
            continue
        for c in r["criteria"]:
            if c["unknown_reason"] == "student_missing":
                f = c["resolve"]["profile_field"]
                missing[f] += 1
                labels[f] = c["label"]
    return {
        "computed_at": utcnow().isoformat(),
        "counts": dict(Counter(r["outcome"] for r in results)),
        "missing_profile_fields": [
            {"field": f, "label": labels[f], "affects": n} for f, n in missing.most_common()
        ],
        "results": results,
    }


def summary(s: Scholarship) -> dict:
    return {
        "id": s.id, "external_id": s.external_id, "name": s.name, "provider": s.provider,
        "provider_type": s.provider_type, "scholarship_type": s.scholarship_type, "amount_text": s.amount_text,
        "amount_max_inr": s.amount_max_inr, "amount_frequency": s.amount_frequency,
        "open_date": s.open_date.isoformat() if s.open_date else None,
        "deadline": s.deadline.isoformat() if s.deadline else None, "renewal_type": s.renewal_type,
        "education_levels": s.education_levels, "eligible_states": s.eligible_states,
        "application_url": s.application_url, "official_source_url": s.official_source_url,
        "verification_status": s.verification_status,
        "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
        "last_verified_at": s.last_verified_at.isoformat() if s.last_verified_at else None,
        "version": s.version, "origin": s.origin,
    }


def _compact(rec: dict) -> dict:
    return {
        r["scholarship_id"]: {"outcome": r["outcome"], "availability": r["availability"]["state"],
                              "version": r["scholarship"]["version"], "deadline": r["scholarship"]["deadline"]}
        for r in rec["results"]
    }


def diff_since_acknowledged(db: Session, profile: StudentProfile, rec: dict) -> dict:
    """What changed in this student's results since they last acknowledged updates.

    The first call stores a baseline, so nothing is reported as "new" on a student's first visit.
    """
    current = _compact(rec)
    prev_snap = db.scalar(select(RecommendationSnapshot).where(RecommendationSnapshot.profile_id == profile.id)
                          .order_by(RecommendationSnapshot.computed_at.desc()).limit(1))
    if prev_snap is None:
        db.add(RecommendationSnapshot(profile_id=profile.id, results=current))
        db.commit()
        return {"since": None, "items": []}
    names = {r["scholarship_id"]: r["scholarship"]["name"] for r in rec["results"]}
    diff = []
    for sid, cur in current.items():
        old = prev_snap.results.get(sid)
        if old is None:
            if cur["outcome"] != "not_eligible":
                diff.append({"scholarship_id": sid, "name": names[sid], "kind": "new_opportunity", "now": cur})
            continue
        changes = {k: {"from": old.get(k), "to": v} for k, v in cur.items() if k != "version" and old.get(k) != v}
        if changes and (cur["outcome"] != "not_eligible" or old.get("outcome") != "not_eligible"):
            diff.append({"scholarship_id": sid, "name": names[sid], "kind": "changed", "changes": changes})
    return {"since": prev_snap.computed_at.isoformat(), "items": diff}


def acknowledge(db: Session, profile: StudentProfile, rec: dict) -> None:
    db.add(RecommendationSnapshot(profile_id=profile.id, results=_compact(rec)))
    db.commit()
