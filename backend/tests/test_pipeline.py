"""Integration tests: crawl -> parse -> match -> change detection -> versioning -> candidates, on local fixtures."""
from datetime import date

import httpx
import pytest
from sqlalchemy import func, select

from app.models import (
    Candidate,
    ChangeEvent,
    CrawlJob,
    FieldEvidence,
    Scholarship,
    ScholarshipSource,
    ScholarshipVersion,
    Source,
)
from app.services import trust
from app.services.crawl import orchestrator
from app.services.sources.fetcher import SafeFetcher
from tests.conftest import FIXTURES, copy_fixture, make_source, put_fixture

REAL = (FIXTURES / "nsp_listing_real_2026-10-18.html").read_text(encoding="utf-8")


def run(db, session_factory, settings, src, fetcher=None) -> CrawlJob:
    job = orchestrator.enqueue(db, src, "manual")
    orchestrator.run_job(job.id, session_factory, fetcher or SafeFetcher(settings, sleep=lambda s: None))
    db.expire_all()
    return db.get(CrawlJob, job.id)


def by_ext(db, ext) -> Scholarship:
    return db.scalar(select(Scholarship).where(Scholarship.external_id == ext))


def test_listing_check_detects_real_deadline_extensions(db, session_factory, settings, imported):
    copy_fixture(settings, "nsp_listing_real_2026-10-18.html", "nsp.html")
    src = make_source(db, settings)
    job = run(db, session_factory, settings, src)
    assert job.status == "succeeded", job.error_message
    assert job.records_seen == 31 and job.records_matched == 27 and job.candidates_created == 4

    deadline_events = db.scalars(select(ChangeEvent).where(ChangeEvent.field == "deadline")).all()
    assert len(deadline_events) == 5
    assert all(e.review_status == "auto_accepted" and e.old_value == "2026-09-30" and e.new_value == "2026-10-31"
               for e in deadline_events)

    s = by_ext(db, "IND-NSP-014")
    assert s.deadline == date(2026, 10, 31) and s.renewal_type == "renewal" and s.version == 2
    versions = db.scalars(select(ScholarshipVersion).where(ScholarshipVersion.scholarship_id == s.id)
                          .order_by(ScholarshipVersion.version)).all()
    assert [v.snapshot["deadline"] for v in versions] == ["2026-09-30", "2026-10-31"]  # history preserved
    ev = db.scalar(select(FieldEvidence).where(FieldEvidence.scholarship_id == s.id, FieldEvidence.field == "deadline",
                                               FieldEvidence.source_key == src.key, FieldEvidence.is_current.is_(True)))
    assert "31-10-2026" in ev.snippet and ev.extraction_method == "nsp_listing_parser" and ev.document_id
    assert s.verification_status == "official_source_confirmed" and s.last_verified_at is not None

    # Different-but-similar names are never auto-merged
    st = db.scalar(select(Candidate).where(Candidate.title.like("National Fellowship%")))
    assert st.possible_matches[0]["decision"] == "possible"
    assert by_ext(db, "IND-NSP-021").verification_status == "deadline_not_verified"

    src_row = db.get(Source, src.id)
    assert src_row.health_status == "healthy" and src_row.last_success_at and src_row.next_check_at


def test_second_identical_check_is_idempotent(db, session_factory, settings, imported):
    copy_fixture(settings, "nsp_listing_real_2026-10-18.html", "nsp.html")
    src = make_source(db, settings)
    run(db, session_factory, settings, src)
    n_events = db.scalar(select(func.count()).select_from(ChangeEvent))
    n_cands = db.scalar(select(func.count()).select_from(Candidate))
    job2 = run(db, session_factory, settings, src)
    assert job2.status == "succeeded" and job2.pages_unchanged == 1 and job2.changes_detected == 0
    assert db.scalar(select(func.count()).select_from(ChangeEvent)) == n_events
    assert db.scalar(select(func.count()).select_from(Candidate)) == n_cands


def test_recheck_keeps_extracted_fields_on_pending_candidates(db, session_factory, settings, imported):
    copy_fixture(settings, "nsp_listing_real_2026-10-18.html", "nsp.html")
    src = make_source(db, settings)
    run(db, session_factory, settings, src)
    cand = db.scalar(select(Candidate).where(Candidate.title.like("National Means%")))
    cand.payload = {**cand.payload, "income_limit": 350000, "income_rule": "limit"}
    cand.evidence = {**cand.evidence, "income_limit": {"snippet": "income not more than 3,50,000", "location": "page 4"}}
    cand.extraction_status = "succeeded"
    db.commit()
    run(db, session_factory, settings, src)
    db.expire_all()
    cand = db.get(Candidate, cand.id)
    assert cand.payload["income_limit"] == 350000 and cand.evidence["income_limit"]["location"] == "page 4"
    assert cand.payload["deadline"] == "2026-10-31"


def test_later_revision_records_previous_and_new_values(db, session_factory, settings, imported):
    copy_fixture(settings, "nsp_listing_real_2026-10-18.html", "nsp.html")
    src = make_source(db, settings)
    run(db, session_factory, settings, src)
    pragati = by_ext(db, "IND-NSP-003")
    v_before = pragati.version
    # Synthetic revision: one deadline extended, one scheme removed from the page.
    row_marker = '<div class="row mb-4 border-1 border-bottom">'

    def row_bounds(html: str, title: str) -> tuple[int, int]:
        at = html.index(title)
        return html.rindex(row_marker, 0, at), html.index(row_marker, at)

    a, b = row_bounds(REAL, "AICTE - Pragati Scholarship Scheme For Girl Students ( Technical Degree)")
    revised = REAL[:a] + REAL[a:b].replace("31-10-2026", "15-11-2026") + REAL[b:]
    a, b = row_bounds(revised, "National Renewable Energy Fellowship Scheme")
    revised = revised[:a] + revised[b:]
    put_fixture(settings, "nsp.html", revised)

    job = run(db, session_factory, settings, src)
    assert job.status == "succeeded"
    db.expire_all()
    pragati = by_ext(db, "IND-NSP-003")
    ev = db.scalar(select(ChangeEvent).where(ChangeEvent.scholarship_id == pragati.id, ChangeEvent.field == "deadline"))
    assert ev.old_value == "2026-10-31" and ev.new_value == "2026-11-15" and ev.materiality == "material"
    assert pragati.deadline == date(2026, 11, 15) and pragati.version == v_before + 1

    mnre = by_ext(db, "IND-NSP-016")
    gone = db.scalar(select(ChangeEvent).where(ChangeEvent.scholarship_id == mnre.id,
                                              ChangeEvent.field == "listing_presence"))
    assert gone.review_status == "pending" and gone.new_value == "not listed"
    assert mnre.verification_status == "needs_review"
    link = db.scalar(select(ScholarshipSource).where(ScholarshipSource.scholarship_id == mnre.id))
    assert link.currently_listed is False


def test_parser_anomaly_fails_without_side_effects(db, session_factory, settings, imported):
    put_fixture(settings, "nsp.html", "<html><body>Site under maintenance</body></html>")
    src = make_source(db, settings)
    job = run(db, session_factory, settings, src)
    assert job.status == "failed" and job.error_type == "parser_anomaly"
    assert db.scalar(select(func.count()).select_from(ChangeEvent)) == 0
    assert by_ext(db, "IND-NSP-014").deadline == date(2026, 9, 30)  # nothing invented or changed
    src_row = db.get(Source, src.id)
    assert src_row.health_status == "degraded" and src_row.consecutive_failures == 1 and src_row.last_success_at is None


def test_partial_page_is_refused(db, session_factory, settings, imported):
    copy_fixture(settings, "nsp_listing_real_2026-10-18.html", "nsp.html")
    src = make_source(db, settings)
    run(db, session_factory, settings, src)
    first_row = REAL.index('<div class="row mb-4 border-1 border-bottom">', REAL.index("collapseOne1"))
    put_fixture(settings, "nsp.html", REAL[:first_row] + "</div></div></body></html>")
    job = run(db, session_factory, settings, src)
    assert job.status == "failed" and job.error_type == "parser_anomaly" and "refusing partial update" in job.error_message


def test_access_denied_pauses_source(db, session_factory, settings, imported):
    import socket

    src = Source(key="live_like", name="Live-like", classification="official", base_url="https://example.gov.in/",
                 target_urls=["https://example.gov.in/list"], allowed_url_patterns=["https://example.gov.in/*"],
                 connector="nsp_listing")
    db.add(src)
    db.commit()
    transport = httpx.MockTransport(lambda req: httpx.Response(404) if req.url.path == "/robots.txt" else httpx.Response(403))
    f = SafeFetcher(settings, transport=transport, sleep=lambda s: None,
                    resolver=lambda h, p: [(socket.AF_INET, 0, 0, "", ("93.184.216.34", p))])
    job = run(db, session_factory, settings, src, f)
    assert job.status == "failed" and job.error_type == "access_denied"
    src_row = db.get(Source, src.id)
    assert src_row.health_status == "paused" and "never bypassed" in src_row.paused_reason
    from app.services.crawl.scheduler import due_sources

    assert src_row.id not in {s.id for s in due_sources(db)}


def test_one_active_job_per_source(db, settings, imported):
    src = make_source(db, settings)
    orchestrator.enqueue(db, src, "manual")
    with pytest.raises(orchestrator.JobConflict):
        orchestrator.enqueue(db, src, "scheduled")


def test_page_monitor_baseline_cosmetic_and_material(db, session_factory, settings, imported):
    s = by_ext(db, "IND-PRI-003")
    body = "<main><h1>Means Grant</h1><p>{text}</p><p>" + "Eligibility details. " * 20 + "</p></main>"
    put_fixture(settings, "page.html", "<nav>Menu A</nav>" + body.format(text="Applications are open.") +
                "<footer>Last updated: 1 Oct 2026</footer>")
    src = make_source(db, settings, key="page", connector="html_page", file="page.html", classification="official",
                      linked=s.id)
    j1 = run(db, session_factory, settings, src)
    assert j1.status == "succeeded" and any("baseline" in l["msg"] for l in j1.log)

    put_fixture(settings, "page.html", "<nav>Menu B (new design)</nav>" + body.format(text="Applications are open.") +
                "<footer>Last updated: 9 Oct 2026</footer>")
    run(db, session_factory, settings, src)
    cosmetic = db.scalar(select(ChangeEvent).where(ChangeEvent.source_id == src.id))
    assert cosmetic.materiality == "cosmetic" and cosmetic.review_status == "informational"

    put_fixture(settings, "page.html", body.format(text="This scholarship programme stands closed for the year 2026-2027."))
    run(db, session_factory, settings, src)
    events = db.scalars(select(ChangeEvent).where(ChangeEvent.source_id == src.id, ChangeEvent.materiality == "material")).all()
    fields = {e.field: e for e in events}
    assert fields["page_content"].review_status == "pending" and "stands closed" in fields["page_content"].evidence_snippet
    assert fields["status_reported"].review_status == "pending"  # html rules are never auto-applied
    db.expire_all()
    assert by_ext(db, "IND-PRI-003").verification_status == "needs_review"


def test_conflicting_official_sources_are_flagged(db, imported):
    from app.services.records import ObservationContext, add_evidence

    s = by_ext(db, "IND-NSP-001")
    for key, val in (("official_a", "2026-10-31"), ("official_b", "2026-11-30")):
        add_evidence(db, s, "deadline", val, ObservationContext(source_key=key, classification="official", method="x"))
    db.flush()
    primary, flags, details = trust.compute_status(db, s)
    assert primary == "conflicting_sources" and details["conflicts"][0]["field"] == "deadline"


def test_availability_from_dates_not_status_text():
    from types import SimpleNamespace

    mk = lambda **kw: SimpleNamespace(**({"open_date": None, "deadline": None, "status_reported": "ACTIVE"} | kw))  # noqa: E731
    assert trust.availability(mk(deadline=date(2026, 9, 30)), date(2026, 10, 18))["state"] == "closed"
    a = trust.availability(mk(deadline=date(2026, 10, 31)), date(2026, 10, 18))
    assert a["state"] == "open" and a["days_left"] == 13 and a["deadline_approaching"]
    assert trust.availability(mk(open_date=date(2026, 11, 1), deadline=date(2026, 12, 1)), date(2026, 10, 18))["state"] == "upcoming"
    assert trust.availability(mk(), date(2026, 10, 18))["state"] == "unknown"
    assert trust.availability(mk(status_reported="CLOSED (stated by source)"), date(2026, 10, 18))["state"] == "closed"
