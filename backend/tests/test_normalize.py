from datetime import date

import pytest

from app.services import normalize as N


@pytest.mark.parametrize("raw,expected", [
    ("2026-10-31", date(2026, 10, 31)),
    ("31-10-2026", date(2026, 10, 31)),
    ("31/10/2026", date(2026, 10, 31)),
    ("5th October 2026", date(2026, 10, 5)),
    ("5 Oct 2026", date(2026, 10, 5)),
    ("October 5, 2026", date(2026, 10, 5)),
    ("UNKNOWN", None),
    ("", None),
    ("31-02-2026", None),  # impossible date is rejected, not coerced
    ("next Friday", None),
    ("1899-01-01", None),
])
def test_parse_date(raw, expected):
    assert N.parse_date(raw) == expected


def test_percentile_is_not_a_percentage():
    r = N.map_academic("80", "Above 80th percentile in Class XII board stream")
    assert r["academic_rule"] == "percentile"
    assert r["min_percentage"] is None


def test_academic_interpretation():
    assert N.map_academic("60", "Class 12 minimum 60%")["min_percentage"] == 60
    cg = N.map_academic("7.5", "UG CGPA >=7.5 OR GATE 2026 score 550-1000")
    assert cg["academic_rule"] == "cgpa" and cg["min_cgpa"] == 7.5 and cg["academic_has_alternative"]
    assert N.map_academic("UNKNOWN", "No fixed minimum percentage stated")["academic_rule"] == "none"
    assert N.map_academic("UNKNOWN", "Scheme-specific academic conditions")["academic_rule"] == "unknown"


def test_income_conflict_between_number_and_text_is_flagged():
    r = N.map_income("2500000", "Household annual income < ₹2.5 lakh")
    assert r["income_rule"] == "unknown" and r["income_note"].startswith("CONFLICT")
    ok = N.map_income("800000", "Family income from all sources <= ₹800,000 per annum")
    assert ok == {"income_rule": "limit", "income_limit": 800000.0, "income_note": ok["income_note"]}
    assert N.map_income("NO INCOME CEILING STATED", "")["income_rule"] == "none"
    assert N.map_income("UNKNOWN", "")["income_rule"] == "unknown"


def test_education_and_discipline_vocab():
    assert N.map_education("UG/PG")[:2] == ("levels", ["UG", "PG"])
    assert N.map_education("Coaching")[0] == "unknown"
    assert N.map_education("Something new")[0] == "unknown"
    assert N.map_disciplines("Technical education")[:2] == ("strict", ["ENGINEERING_TECHNOLOGY"])
    assert N.map_disciplines("All eligible fields")[0] == "any"
    assert N.map_disciplines("Underwater basket weaving")[0] == "unknown"


def test_class_range_and_years():
    assert N.parse_class_range("Class I-X") == [1, 10]
    assert N.parse_class_range("IX-X") == [9, 10]
    assert N.parse_class_range("Standard VIII through graduation") == [8, 12]
    assert N.parse_allowed_years("1st-4th year") == [1, 2, 3, 4]
    assert N.parse_allowed_years("1st year or 2nd year through lateral entry") == [1, 2]
    assert N.parse_allowed_years("As per course") is None


def test_conditions_or_within_group_and_questions():
    conds = N.map_conditions("Orphan; parent(s) died due to COVID-19; ward of Armed Forces/Central Paramilitary "
                             "Forces martyred in action")
    assert len(conds) == 1 and conds[0]["kind"] == "profile_tags"
    assert set(conds[0]["tags"]) == {"ORPHAN", "COVID_BEREAVED", "ARMED_FORCES_MARTYR_WARD"}
    q = N.map_conditions("Girl student; maximum two girls per family")
    assert [c["kind"] for c in q] == ["question"] and "two girls" in q[0]["text"]
    cit = N.map_conditions("Indian national; UDID/Aadhaar required")
    assert [c["kind"] for c in cit] == ["citizenship"]
    # stable keys so stored student answers survive re-imports
    assert N.condition_key("Admission to a notified institution") == N.condition_key("admission to a notified institution!")


def test_categories():
    assert N.map_categories("OBC/EBC/DNT")[0] == ["OBC", "EBC", "DNT"]
    cats, alt, _ = N.map_categories("SC/OBC/PM CARES Children")
    assert cats == ["SC", "OBC"] and alt == ["PM_CARES_CHILD"]
    assert N.map_categories("Government reservation norms")[0] == []


def test_normalize_name_keeps_discriminators():
    assert N.normalize_name("AICTE - Pragati Scholarship ( Technical Degree) (Merit Based Scheme)") == \
        "aicte pragati scholarship technical degree"
