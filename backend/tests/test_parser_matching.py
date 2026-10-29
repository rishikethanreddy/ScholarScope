from datetime import date
from types import SimpleNamespace

from app.services.connectors.nsp_listing import parse_nsp_listing
from app.services.matching import discriminator_conflict, find_duplicate_pairs, rank_matches
from tests.conftest import FIXTURES

REAL = (FIXTURES / "nsp_listing_real_2026-10-18.html").read_text(encoding="utf-8")


def test_parses_real_archived_nsp_listing():
    schemes = parse_nsp_listing(REAL)
    assert len(schemes) == 31  # 32 rows on the page, one featured duplicate removed
    by_title = {s.title: s for s in schemes}
    nmms = by_title["National Means Cum Merit Scholarship"]
    assert nmms.ministry == "Department of School Education & Literacy"
    assert nmms.open_date == date(2026, 6, 1) and nmms.deadline == date(2026, 10, 31)
    assert nmms.guideline_url.endswith("NMMSSGuidelines.pdf") and nmms.scheme_type == "Merit Based"
    csss = next(s for s in schemes if s.title.startswith("PM-USP"))
    assert csss.renewal_only is True
    pmss = next(s for s in schemes if "Martyred" in s.title)
    assert any("Duplicate listing" in w for w in pmss.warnings)  # featured row links a different guideline


def test_parser_returns_nothing_for_unexpected_markup():
    assert parse_nsp_listing("<html><body><h1>Maintenance</h1></body></html>") == []


def test_parser_never_invents_dates():
    html = """<div class="accordion-item"><button class="accordion-button" data-bs-target="#c1">M</button>
    <div id="c1"><div class="row mb-4 border-1 border-bottom"><div class="col-md-10"><h6>Test Scheme (Merit Based Scheme)</h6>
    <span>Scheme Open from : 32-13-2026</span></div></div></div></div>"""
    s = parse_nsp_listing(html)[0]
    assert s.open_date is None and s.deadline is None
    assert any("Unparseable" in w for w in s.warnings) and any("No student application deadline" in w for w in s.warnings)


def rec(id_, name, url=None, provider=None):
    return SimpleNamespace(id=id_, name=name, official_source_url=url, application_url=None, provider=provider)


def test_discriminators_block_unsafe_merges():
    assert discriminator_conflict("AICTE Pragati (Technical Degree)", "AICTE Pragati (Technical Diploma)")
    assert discriminator_conflict("Pre Matric Scholarship for Students with Disabilities",
                                  "Post Matric Scholarship for Students with Disabilities")
    assert discriminator_conflict("PM YASASVI Top Class Education in Schools", "PM YASASVI Top Class Education in College")
    assert discriminator_conflict("ICAR NTS (UG)", "ICAR NTS (PG)")
    assert not discriminator_conflict("Free Coaching for SCs and OBCs", "Free Coaching For Scs OBCs")


def test_rank_matches_auto_and_possible():
    records = [rec("a", "AICTE - Pragati Scholarship Scheme for Girl Students (Technical Degree)"),
               rec("b", "AICTE - Pragati Scholarship Scheme for Girl Students (Technical Diploma)"),
               rec("c", "National Fellowship and Scholarship for Higher Education of ST Students - Scholarship",
                   provider="Ministry of Tribal Affairs")]
    m = rank_matches("AICTE - Pragati Scholarship Scheme For Girl Students ( Technical Degree)", None, None, records)
    assert m[0].record_id == "a" and m[0].decision == "auto"
    assert all(x.decision != "auto" for x in m[1:])
    st = rank_matches("National Fellowship And Scholarship For Higher Education Of ST Students - Scholarship "
                      "(Formally Top Class Education For Schedule Tribe Students)", None, "Ministry of Tribal Affairs",
                      records)
    assert st[0].record_id == "c" and st[0].decision == "possible"  # similar but not certain: human review
    assert rank_matches("National Means Cum Merit Scholarship", None, None, records) == [] or \
        rank_matches("National Means Cum Merit Scholarship", None, None, records)[0].decision == "none"


def test_duplicate_pairs_exclude_discriminated_variants():
    records = [rec("a", "Scholarship X for Women Engineers", "https://x.org/a.pdf"),
               rec("b", "Scholarship X for Women Engineers 2026", "https://x.org/a.pdf"),
               rec("c", "Swanath Scholarship (Technical Degree)"), rec("d", "Swanath Scholarship (Technical Diploma)")]
    pairs = find_duplicate_pairs(records)
    assert [(p["a_id"], p["b_id"]) for p in pairs] == [("a", "b")]
