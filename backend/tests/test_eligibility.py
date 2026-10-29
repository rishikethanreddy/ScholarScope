from types import SimpleNamespace

from app.services.recommendation import eligibility as E
from app.services.recommendation import scoring
from tests.conftest import student


def sch(**kw):
    base = dict(education_rule="levels", education_levels=["UG"], class_range=None, allowed_years=None,
                courses_text=None, fields_text=None, year_of_study_text=None, discipline_rule="any", disciplines=[],
                academic_rule="none", min_percentage=None, min_cgpa=None, cgpa_scale=10.0,
                academic_has_alternative=False, academic_note=None, income_rule="none", income_limit=None,
                income_note=None, genders=[], categories=[], category_alt_tags=[], category_note=None,
                disability_rule="none", min_disability_percent=None, eligible_states=[], conditions=[],
                amount_max_inr=None)
    base.update(kw)
    return SimpleNamespace(**base)


def crit(results, key):
    return next(c for c in results if c["key"] == key)


def test_income_boundary_is_inclusive():
    s = sch(income_rule="limit", income_limit=800000)
    at = E.evaluate(student(education_level="UG", annual_family_income=800000), s)
    above = E.evaluate(student(education_level="UG", annual_family_income=800001), s)
    assert crit(at, "income")["status"] == E.SATISFIED
    assert crit(above, "income")["status"] == E.NOT_SATISFIED
    assert E.outcome(above) == "not_eligible"


def test_unknown_student_value_is_never_satisfied():
    s = sch(income_rule="limit", income_limit=800000)
    r = E.evaluate(student(education_level="UG"), s)
    c = crit(r, "income")
    assert c["status"] == E.UNKNOWN and c["unknown_reason"] == "student_missing"
    assert c["resolve"] == {"profile_field": "annual_family_income"}
    assert E.outcome(r) == "potential_match"


def test_scholarship_side_unknown_needs_verification():
    s = sch(income_rule="unknown", income_note="Scheme-specific")
    r = E.evaluate(student(education_level="UG", annual_family_income=100000), s)
    assert crit(r, "income")["unknown_reason"] == "scholarship_unresolved"
    assert E.outcome(r) == "eligible_pending_verification"


def test_fully_satisfied_is_eligible_and_not_satisfied_wins():
    s = sch(income_rule="limit", income_limit=500000, genders=["FEMALE"])
    ok = E.evaluate(student(education_level="UG", annual_family_income=1, gender="FEMALE"), s)
    assert E.outcome(ok) == "eligible"
    mixed = E.evaluate(student(education_level="UG", gender="MALE"), s)  # income unknown + gender fails
    assert E.outcome(mixed) == "not_eligible"


def test_percentage_boundary_and_no_cgpa_conversion():
    s = sch(academic_rule="percentage", min_percentage=60)
    assert crit(E.evaluate(student(education_level="UG", qualifying_exam_percentage=60), s), "academic")["status"] == E.SATISFIED
    assert crit(E.evaluate(student(education_level="UG", qualifying_exam_percentage=59.99), s), "academic")["status"] == E.NOT_SATISFIED
    only_cgpa = crit(E.evaluate(student(education_level="UG", cgpa=9.5), s), "academic")
    assert only_cgpa["status"] == E.UNKNOWN  # CGPA is not silently converted to a percentage


def test_cgpa_alternative_route_and_scale():
    s = sch(academic_rule="cgpa", min_cgpa=7.5, academic_has_alternative=True, academic_note="CGPA>=7.5 OR GATE")
    low = crit(E.evaluate(student(education_level="UG", cgpa=7.0), s), "academic")
    assert low["status"] == E.UNKNOWN and low["unknown_reason"] == "needs_confirmation"
    confirmed = crit(E.evaluate(student(education_level="UG", cgpa=7.0), s, {"academic:alt": "yes"}), "academic")
    assert confirmed["status"] == E.SATISFIED
    other_scale = crit(E.evaluate(student(education_level="UG", cgpa=3.5, cgpa_scale=4.0), s), "academic")
    assert other_scale["status"] == E.UNKNOWN


def test_strict_vs_open_discipline():
    strict = sch(discipline_rule="strict", disciplines=["AGRICULTURE"], fields_text="Agriculture")
    open_ = sch(discipline_rule="open", disciplines=["ENGINEERING_TECHNOLOGY"], fields_text="Engineering and other")
    st = student(education_level="UG", discipline="ARTS_HUMANITIES")
    assert crit(E.evaluate(st, strict), "discipline")["status"] == E.NOT_SATISFIED
    assert crit(E.evaluate(st, open_), "discipline")["status"] == E.UNKNOWN


def test_education_level_and_school_class():
    s = sch(education_levels=["PRE_MATRIC"], class_range=[9, 10])
    assert E.outcome(E.evaluate(student(education_level="PG"), s)) == "not_eligible"
    assert crit(E.evaluate(student(education_level="PRE_MATRIC", current_class=8), s), "class")["status"] == E.NOT_SATISFIED
    assert crit(E.evaluate(student(education_level="PRE_MATRIC", current_class=10), s), "class")["status"] == E.SATISFIED
    assert crit(E.evaluate(student(education_level="PRE_MATRIC"), s), "class")["status"] == E.UNKNOWN


def test_lateral_entry_year_requires_confirmation():
    s = sch(allowed_years=[1, 2], year_of_study_text="1st year or 2nd year through lateral entry")
    assert crit(E.evaluate(student(education_level="UG", year_of_study=1), s), "year")["status"] == E.SATISFIED
    y2 = crit(E.evaluate(student(education_level="UG", year_of_study=2), s), "year")
    assert y2["status"] == E.UNKNOWN and y2["resolve"]["question"]["key"] == "year:lateral"
    assert crit(E.evaluate(student(education_level="UG", year_of_study=3), s), "year")["status"] == E.NOT_SATISFIED


def test_category_with_alternative_beneficiary_tag():
    s = sch(categories=["SC", "OBC"], category_alt_tags=["PM_CARES_CHILD"])
    assert crit(E.evaluate(student(education_level="UG", category="SC"), s), "category")["status"] == E.SATISFIED
    general_unanswered = crit(E.evaluate(student(education_level="UG", category="GENERAL"), s), "category")
    assert general_unanswered["status"] == E.UNKNOWN  # could still be a PM CARES beneficiary
    general_none = E.evaluate(student(education_level="UG", category="GENERAL", special_circumstances_none=True), s)
    assert crit(general_none, "category")["status"] == E.NOT_SATISFIED
    pm = E.evaluate(student(education_level="UG", category="GENERAL", special_circumstances=["PM_CARES_CHILD"]), s)
    assert crit(pm, "category")["status"] == E.SATISFIED


def test_disability_threshold():
    s = sch(disability_rule="required", min_disability_percent=40)
    assert crit(E.evaluate(student(education_level="UG", has_disability=False), s), "disability")["status"] == E.NOT_SATISFIED
    assert crit(E.evaluate(student(education_level="UG", has_disability=True), s), "disability")["status"] == E.UNKNOWN
    assert crit(E.evaluate(student(education_level="UG", has_disability=True, disability_percent=40), s), "disability")["status"] == E.SATISFIED
    assert crit(E.evaluate(student(education_level="UG", has_disability=True, disability_percent=39), s), "disability")["status"] == E.NOT_SATISFIED


def test_questions_and_profile_tags():
    q = {"key": "q:abc", "kind": "question", "text": "Admission to a notified institution"}
    tags = {"key": "tags:beneficiary", "kind": "profile_tags", "tags": ["ORPHAN"], "text": "Orphan"}
    s = sch(conditions=[q, tags])
    base = student(education_level="UG")
    r = E.evaluate(base, s)
    assert crit(r, "q:abc")["unknown_reason"] == "needs_confirmation"
    assert crit(r, "tags:beneficiary")["unknown_reason"] == "student_missing"
    r2 = E.evaluate(student(education_level="UG", special_circumstances=["ORPHAN"]), s, {"q:abc": "yes"})
    assert E.outcome(r2) == "eligible"
    r3 = E.evaluate(student(education_level="UG", special_circumstances_none=True), s, {"q:abc": "yes"})
    assert E.outcome(r3) == "not_eligible"
    r4 = E.evaluate(student(education_level="UG", special_circumstances=["ORPHAN"]), s, {"q:abc": "unsure"})
    assert E.outcome(r4) == "potential_match"


def test_state_restriction():
    s = sch(eligible_states=["Assam", "Sikkim"])
    assert crit(E.evaluate(student(education_level="UG", state="Assam"), s), "state")["status"] == E.SATISFIED
    assert crit(E.evaluate(student(education_level="UG", state="Kerala"), s), "state")["status"] == E.NOT_SATISFIED


def test_every_criterion_has_explanation():
    s = sch(income_rule="limit", income_limit=1, academic_rule="percentage", min_percentage=50,
            genders=["FEMALE"], eligible_states=["Goa"])
    for c in E.evaluate(student(education_level="UG", annual_family_income=5, gender="MALE", state="Goa"), s):
        assert c["explanation"] and c["rule"] is not None and c["status"] in (E.SATISFIED, E.NOT_SATISFIED, E.UNKNOWN, E.NA)


def test_score_is_separate_bounded_and_explained():
    s = sch(income_rule="limit", income_limit=800000, amount_max_inr=50000)
    st = student(education_level="UG", annual_family_income=200000)
    crits = E.evaluate(st, s)
    sc = scoring.score(st, s, crits)
    assert 0 <= sc["score"] <= 100
    assert abs(sum(f["contribution"] for f in sc["factors"].values()) - sc["score"]) < 0.2
    assert all("detail" in f and "weight" in f for f in sc["factors"].values())
    poorer = scoring.score(student(education_level="UG", annual_family_income=10000), s, crits)
    assert poorer["factors"]["financial_need_fit"]["value"] > sc["factors"]["financial_need_fit"]["value"]
