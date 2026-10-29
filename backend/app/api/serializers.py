from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.models import Candidate, ChangeEvent, CrawlJob, FieldEvidence, Scholarship, Source, StudentProfile
from app.services import trust
from app.services.records import CONTENT_FIELDS


def iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def scholarship_full(s: Scholarship) -> dict:
    d = {f: iso(getattr(s, f)) for f in CONTENT_FIELDS}
    d.update({
        "id": s.id, "external_id": s.external_id, "origin": s.origin, "version": s.version,
        "is_published": s.is_published, "verification_status": s.verification_status,
        "verification_label": trust.STATUS_LABELS.get(s.verification_status, s.verification_status),
        "verification_flags": s.verification_flags, "first_discovered_at": iso(s.first_discovered_at),
        "last_checked_at": iso(s.last_checked_at), "last_verified_at": iso(s.last_verified_at),
        "updated_at": iso(s.updated_at), "availability": trust.availability(s),
    })
    return d


def evidence(e: FieldEvidence) -> dict:
    return {
        "id": e.id, "field": e.field, "value": e.value, "source_key": e.source_key, "source_url": e.source_url,
        "classification": e.source_classification, "snippet": e.snippet, "location": e.location,
        "retrieved_at": iso(e.retrieved_at), "method": e.extraction_method,
        "verification_status": e.verification_status, "record_version": e.record_version,
        "is_current": e.is_current, "document_id": e.document_id,
    }


def change(e: ChangeEvent, name: str | None = None) -> dict:
    return {
        "id": e.id, "scholarship_id": e.scholarship_id, "scholarship_name": name, "source_id": e.source_id,
        "job_id": e.job_id, "document_id": e.document_id, "field": e.field, "change_kind": e.change_kind,
        "old_value": e.old_value, "new_value": e.new_value, "materiality": e.materiality,
        "detected_at": iso(e.detected_at), "source_url": e.source_url, "evidence_snippet": e.evidence_snippet,
        "method": e.method, "review_status": e.review_status, "reviewed_at": iso(e.reviewed_at),
        "review_note": e.review_note, "applied_version": e.applied_version,
    }


def source(s: Source) -> dict:
    return {
        "id": s.id, "key": s.key, "name": s.name, "organization": s.organization, "classification": s.classification,
        "base_url": s.base_url, "target_urls": s.target_urls, "allowed_url_patterns": s.allowed_url_patterns,
        "connector": s.connector, "connector_config": s.connector_config, "parser_version": s.parser_version,
        "crawl_frequency_minutes": s.crawl_frequency_minutes, "enabled": s.enabled, "priority": s.priority,
        "trust_policy": s.trust_policy, "access_notes": s.access_notes,
        "linked_scholarship_id": s.linked_scholarship_id, "last_attempt_at": iso(s.last_attempt_at),
        "last_success_at": iso(s.last_success_at), "last_change_at": iso(s.last_change_at),
        "last_http_status": s.last_http_status, "last_error": s.last_error, "health_status": s.health_status,
        "consecutive_failures": s.consecutive_failures, "next_check_at": iso(s.next_check_at),
        "paused_reason": s.paused_reason, "is_fixture": s.classification == "fixture" or
        any(u.startswith("fixture://") for u in s.target_urls or []),
    }


def job(j: CrawlJob, with_log: bool = False) -> dict:
    d = {
        "id": j.id, "source_id": j.source_id, "source_key": j.source.key if j.source else None,
        "source_name": j.source.name if j.source else None, "trigger": j.trigger, "status": j.status,
        "queued_at": iso(j.queued_at), "started_at": iso(j.started_at), "finished_at": iso(j.finished_at),
        "pages_fetched": j.pages_fetched, "pages_unchanged": j.pages_unchanged, "records_seen": j.records_seen,
        "records_matched": j.records_matched, "candidates_created": j.candidates_created,
        "changes_detected": j.changes_detected, "error_type": j.error_type, "error_message": j.error_message,
        "retry_of": j.retry_of,
        "duration_ms": int((j.finished_at - j.started_at).total_seconds() * 1000) if j.finished_at and j.started_at else None,
    }
    if with_log:
        d["log"] = j.log
    return d


def candidate(c: Candidate) -> dict:
    return {
        "id": c.id, "kind": c.kind, "status": c.status, "source_id": c.source_id, "job_id": c.job_id,
        "document_id": c.document_id, "external_key": c.external_key, "title": c.title, "payload": c.payload,
        "evidence": c.evidence, "validation": c.validation, "possible_matches": c.possible_matches,
        "matched_scholarship_id": c.matched_scholarship_id, "extraction_method": c.extraction_method,
        "extraction_status": c.extraction_status, "extraction_error": c.extraction_error,
        "llm_provider": c.llm_provider, "llm_model": c.llm_model, "created_at": iso(c.created_at),
        "updated_at": iso(c.updated_at), "reviewed_at": iso(c.reviewed_at), "review_note": c.review_note,
    }


PROFILE_FIELDS = [
    "display_name", "education_level", "current_class", "year_of_study", "course_name", "discipline",
    "qualifying_exam_percentage", "cgpa", "cgpa_scale", "annual_family_income", "state", "gender", "category",
    "has_disability", "disability_percent", "is_indian_citizen", "special_circumstances",
    "special_circumstances_none",
]


def profile(p: StudentProfile) -> dict:
    d = {f: getattr(p, f) for f in PROFILE_FIELDS}
    d.update({"id": p.id, "updated_at": iso(p.updated_at)})
    return d
