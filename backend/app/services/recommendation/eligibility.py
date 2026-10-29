"""Deterministic, three-valued eligibility evaluation.

Each criterion evaluates to SATISFIED, NOT_SATISFIED, UNKNOWN or NOT_APPLICABLE. UNKNOWN is never treated as
satisfied. UNKNOWN carries a reason so the UI can tell the student what would resolve it:

  student_missing        the profile lacks a value the rule needs (resolvable by editing the profile)
  needs_confirmation     a scholarship-specific condition the student can answer yes/no
  scholarship_unresolved the scholarship's own rule is not recorded in structured form (needs source verification)

The function is pure: it takes plain attribute objects and returns dictionaries, so it is easy to test.
"""
from __future__ import annotations

from typing import Any, Optional

from app.services.normalize import vocab

SATISFIED, NOT_SATISFIED, UNKNOWN, NA = "satisfied", "not_satisfied", "unknown", "not_applicable"
SCHOOL_LEVELS = {"PRE_MATRIC", "POST_MATRIC_SCHOOL"}

OUTCOME_LABELS = {
    "eligible": "Eligible based on recorded criteria",
    "eligible_pending_verification": "Meets recorded criteria; some rules need source verification",
    "potential_match": "Potential match; more information needed",
    "not_eligible": "Not eligible based on recorded criteria",
}

# Which scholarship field holds the evidence for each criterion.
CRITERION_EVIDENCE_FIELD = {
    "education": "education_levels", "class": "education_levels", "year": "education_levels",
    "discipline": "disciplines", "academic": "academic_rule", "income": "income_limit", "gender": "genders",
    "category": "categories", "disability": "disability_rule", "state": "eligible_states",
}


def _labels(kind: str) -> dict[str, str]:
    return {x["code"]: x["label"] for x in vocab()[kind]}


def _fmt_inr(v: Optional[float]) -> str:
    return "not provided" if v is None else f"₹{v:,.0f}"


def _crit(key: str, label: str, status: str, rule: str, student_value: Any, explanation: str,
          unknown_reason: Optional[str] = None, resolve: Optional[dict] = None) -> dict:
    return {
        "key": key, "label": label, "status": status, "rule": rule, "student_value": student_value,
        "explanation": explanation, "unknown_reason": unknown_reason if status == UNKNOWN else None,
        "resolve": resolve if status == UNKNOWN else None,
    }


def _missing(key, label, rule, field, what) -> dict:
    return _crit(key, label, UNKNOWN, rule, None, f"Add your {what} to check this rule.", "student_missing",
                 {"profile_field": field})


def _question(key, label, rule, text, explanation, question_key=None) -> dict:
    return _crit(key, label, UNKNOWN, rule, None, explanation, "needs_confirmation",
                 {"question": {"key": question_key or key, "text": text}})


def evaluate(student: Any, s: Any, answers: Optional[dict[str, str]] = None) -> list[dict]:
    answers = answers or {}
    out: list[dict] = []
    edu_labels, disc_labels = _labels("education_levels"), _labels("disciplines")
    level = getattr(student, "education_level", None)

    # 1. Education level
    if s.education_rule == "unknown":
        out.append(_crit("education", "Education level", UNKNOWN, s.courses_text or "Not recorded", level,
                         "The scholarship's education level is not recorded in structured form; check the guideline.",
                         "scholarship_unresolved"))
    elif s.education_rule == "levels":
        rule = ", ".join(edu_labels.get(x, x) for x in s.education_levels)
        if not level:
            out.append(_missing("education", "Education level", rule, "education_level", "current education level"))
        elif level in s.education_levels:
            out.append(_crit("education", "Education level", SATISFIED, rule, edu_labels.get(level, level),
                             f"You study at {edu_labels.get(level, level)}, which this scholarship covers."))
        else:
            out.append(_crit("education", "Education level", NOT_SATISFIED, rule, edu_labels.get(level, level),
                             f"This scholarship is for {rule}; your profile says {edu_labels.get(level, level)}."))

    # 2. Class range (school students only)
    if s.class_range and level in SCHOOL_LEVELS:
        lo, hi = s.class_range
        rule = f"Class {lo}–{hi}"
        cls = getattr(student, "current_class", None)
        if cls is None:
            out.append(_missing("class", "Class", rule, "current_class", "current class"))
        elif lo <= cls <= hi:
            out.append(_crit("class", "Class", SATISFIED, rule, cls, f"You are in Class {cls} ({rule})."))
        else:
            out.append(_crit("class", "Class", NOT_SATISFIED, rule, cls, f"Requires {rule}; you are in Class {cls}."))

    # 3. Year of study (post-school)
    if s.allowed_years and level and level not in SCHOOL_LEVELS:
        rule = s.year_of_study_text or ", ".join(f"year {y}" for y in s.allowed_years)
        yr = getattr(student, "year_of_study", None)
        lateral = "lateral" in (s.year_of_study_text or "").lower()
        if yr is None:
            out.append(_missing("year", "Year of study", rule, "year_of_study", "year of study"))
        elif yr not in s.allowed_years:
            out.append(_crit("year", "Year of study", NOT_SATISFIED, rule, yr, f"Requires {rule}; you are in year {yr}."))
        elif lateral and yr > min(s.allowed_years):
            key = "year:lateral"
            if answers.get(key) == "yes":
                out.append(_crit("year", "Year of study", SATISFIED, rule, yr, "You confirmed lateral entry into this year."))
            elif answers.get(key) == "no":
                out.append(_crit("year", "Year of study", NOT_SATISFIED, rule, yr, "Year 2 is only eligible via lateral entry."))
            else:
                out.append(_question("year", "Year of study", rule, f"Did you join year {yr} through lateral entry?",
                                     f"Year {yr} is only eligible through lateral entry ({rule}).", key))
        else:
            out.append(_crit("year", "Year of study", SATISFIED, rule, yr, f"Year {yr} is within {rule}."))

    # 4. Course / discipline
    if s.discipline_rule == "unknown":
        out.append(_crit("discipline", "Course / discipline", UNKNOWN, s.fields_text or "Not recorded",
                         getattr(student, "discipline", None),
                         "Eligible courses are not recorded in structured form.", "scholarship_unresolved"))
    elif s.discipline_rule in ("strict", "open"):
        rule = ", ".join(disc_labels.get(d, d) for d in s.disciplines)
        disc = getattr(student, "discipline", None)
        if not disc:
            out.append(_missing("discipline", "Course / discipline", rule, "discipline", "course discipline"))
        elif disc in s.disciplines:
            out.append(_crit("discipline", "Course / discipline", SATISFIED, rule, disc_labels.get(disc, disc),
                             f"Your discipline ({disc_labels.get(disc, disc)}) is listed: {s.fields_text}."))
        elif s.discipline_rule == "strict":
            out.append(_crit("discipline", "Course / discipline", NOT_SATISFIED, rule, disc_labels.get(disc, disc),
                             f"Limited to {s.fields_text}; your discipline is {disc_labels.get(disc, disc)}."))
        else:
            key = "discipline:confirm"
            ans = answers.get(key)
            if ans in ("yes", "no"):
                out.append(_crit("discipline", "Course / discipline", SATISFIED if ans == "yes" else NOT_SATISFIED,
                                 rule, disc_labels.get(disc, disc), "Based on your answer about your course."))
            else:
                out.append(_question("discipline", "Course / discipline", rule,
                                     f"Is your course one of the eligible courses? ({s.courses_text or s.fields_text})",
                                     f"The list ({s.fields_text}) is open-ended; your discipline is not named.", key))

    # 5. Academic threshold
    note = s.academic_note or ""
    if s.academic_rule == "none":
        out.append(_crit("academic", "Academic merit", NA, note or "No minimum stated", None,
                         f"No fixed minimum is recorded. {note}".strip()))
    elif s.academic_rule == "unknown":
        out.append(_crit("academic", "Academic merit", UNKNOWN, note or "Not recorded", None,
                         f"Academic conditions are not recorded as a number: '{note or 'unknown'}'. Check the guideline.",
                         "scholarship_unresolved"))
    elif s.academic_rule == "percentage":
        rule = f"Minimum {s.min_percentage:g}% ({note})" if note else f"Minimum {s.min_percentage:g}%"
        pct = getattr(student, "qualifying_exam_percentage", None)
        if pct is None:
            out.append(_missing("academic", "Academic merit", rule, "qualifying_exam_percentage",
                                "qualifying-exam percentage (CGPA is not converted automatically)"))
        elif pct >= s.min_percentage:
            out.append(_crit("academic", "Academic merit", SATISFIED, rule, f"{pct:g}%",
                             f"Your {pct:g}% meets the {s.min_percentage:g}% minimum."))
        elif s.academic_has_alternative:
            out.append(_crit("academic", "Academic merit", UNKNOWN, rule, f"{pct:g}%",
                             f"Below {s.min_percentage:g}%, but the rule has an alternative route: {note}",
                             "needs_confirmation", {"question": {"key": "academic:alt", "text": f"Do you qualify via: {note}?"}}))
        else:
            out.append(_crit("academic", "Academic merit", NOT_SATISFIED, rule, f"{pct:g}%",
                             f"Requires at least {s.min_percentage:g}%; you have {pct:g}%."))
    elif s.academic_rule == "cgpa":
        rule = f"Minimum CGPA {s.min_cgpa:g}/{s.cgpa_scale:g}" + (f" ({note})" if note else "")
        cg, scale = getattr(student, "cgpa", None), getattr(student, "cgpa_scale", None) or 10.0
        alt = answers.get("academic:alt")
        if cg is None:
            out.append(_missing("academic", "Academic merit", rule, "cgpa", "CGPA"))
        elif abs(scale - s.cgpa_scale) > 1e-6:
            out.append(_crit("academic", "Academic merit", UNKNOWN, rule, f"{cg:g}/{scale:g}",
                             "Your CGPA uses a different scale; scales are not converted automatically.",
                             "needs_confirmation", {"question": {"key": "academic:alt", "text": f"Do you meet: {rule}?"}}))
        elif cg >= s.min_cgpa or alt == "yes":
            out.append(_crit("academic", "Academic merit", SATISFIED, rule, f"{cg:g}/{scale:g}",
                             f"Your CGPA {cg:g} meets {s.min_cgpa:g}." if cg >= s.min_cgpa else "You confirmed the alternative route."))
        elif s.academic_has_alternative and alt != "no":
            out.append(_crit("academic", "Academic merit", UNKNOWN, rule, f"{cg:g}/{scale:g}",
                             f"CGPA below {s.min_cgpa:g}, but an alternative route exists: {note}", "needs_confirmation",
                             {"question": {"key": "academic:alt", "text": f"Do you qualify via the alternative route? ({note})"}}))
        else:
            out.append(_crit("academic", "Academic merit", NOT_SATISFIED, rule, f"{cg:g}/{scale:g}",
                             f"Requires CGPA {s.min_cgpa:g}; you have {cg:g}."))
    elif s.academic_rule == "percentile":
        out.append(_crit("academic", "Academic merit", NA, note, None,
                         "Threshold is a percentile; it is asked as a separate condition below."))

    # 6. Family income
    income = getattr(student, "annual_family_income", None)
    if s.income_rule == "none":
        out.append(_crit("income", "Family income", NA, "No income ceiling stated", _fmt_inr(income),
                         s.income_note or "The source states no income ceiling."))
    elif s.income_rule == "unknown":
        out.append(_crit("income", "Family income", UNKNOWN, s.income_note or "Not recorded", _fmt_inr(income),
                         f"Income ceiling not recorded reliably. {s.income_note or ''}".strip(), "scholarship_unresolved"))
    else:
        rule = f"Annual family income ≤ {_fmt_inr(s.income_limit)}"
        if income is None:
            out.append(_missing("income", "Family income", rule, "annual_family_income", "annual family income"))
        elif income <= s.income_limit:
            out.append(_crit("income", "Family income", SATISFIED, rule, _fmt_inr(income),
                             f"Your family income {_fmt_inr(income)} is within the {_fmt_inr(s.income_limit)} ceiling."))
        else:
            out.append(_crit("income", "Family income", NOT_SATISFIED, rule, _fmt_inr(income),
                             f"Your family income {_fmt_inr(income)} exceeds the {_fmt_inr(s.income_limit)} ceiling."))

    # 7. Gender
    if s.genders:
        g_labels = _labels("genders")
        rule = " / ".join(g_labels.get(g, g) for g in s.genders)
        gender = getattr(student, "gender", None)
        if not gender:
            out.append(_missing("gender", "Gender", rule, "gender", "gender"))
        elif gender in s.genders:
            out.append(_crit("gender", "Gender", SATISFIED, rule, g_labels.get(gender, gender), f"Open to {rule} students."))
        else:
            out.append(_crit("gender", "Gender", NOT_SATISFIED, rule, g_labels.get(gender, gender), f"Only for {rule} students."))

    # 8. Category (with alternative beneficiary tags, e.g. PM CARES children)
    tags = set(getattr(student, "special_circumstances", None) or [])
    tags_answered = bool(tags) or bool(getattr(student, "special_circumstances_none", False))
    if s.categories or s.category_alt_tags:
        rule = "/".join(s.categories) + (" or " + "/".join(s.category_alt_tags) if s.category_alt_tags else "")
        cat = getattr(student, "category", None)
        if cat and cat in s.categories:
            out.append(_crit("category", "Category", SATISFIED, rule, cat, f"Open to {rule}; you are {cat}."))
        elif tags & set(s.category_alt_tags):
            out.append(_crit("category", "Category", SATISFIED, rule, cat, "You declared an eligible beneficiary status."))
        elif not cat:
            out.append(_missing("category", "Category", rule, "category", "social category"))
        elif s.category_alt_tags and not tags_answered:
            out.append(_missing("category", "Category", rule, "special_circumstances", "special circumstances"))
        else:
            out.append(_crit("category", "Category", NOT_SATISFIED, rule, cat, f"Restricted to {rule}; you are {cat}."))
    elif s.category_note:
        out.append(_crit("category", "Category", NA, s.category_note, getattr(student, "category", None),
                         f"No exclusive category restriction ({s.category_note})."))

    # 9. Disability
    if s.disability_rule == "required":
        rule = "Disability" + (f" ≥ {s.min_disability_percent:g}%" if s.min_disability_percent else "")
        has = getattr(student, "has_disability", None)
        pct = getattr(student, "disability_percent", None)
        if has is None:
            out.append(_missing("disability", "Disability", rule, "has_disability", "disability status"))
        elif not has:
            out.append(_crit("disability", "Disability", NOT_SATISFIED, rule, "No", "This scholarship is for students with disabilities."))
        elif s.min_disability_percent and pct is None:
            out.append(_missing("disability", "Disability", rule, "disability_percent", "certified disability percentage"))
        elif s.min_disability_percent and pct < s.min_disability_percent:
            out.append(_crit("disability", "Disability", NOT_SATISFIED, rule, f"{pct:g}%", f"Requires {rule}; you have {pct:g}%."))
        else:
            out.append(_crit("disability", "Disability", SATISFIED, rule, f"{pct:g}%" if pct else "Yes", f"Meets {rule}."))

    # 10. State / region
    if s.eligible_states:
        rule = ", ".join(s.eligible_states)
        state = getattr(student, "state", None)
        if not state:
            out.append(_missing("state", "State / domicile", rule, "state", "state of domicile"))
        elif state in s.eligible_states:
            out.append(_crit("state", "State / domicile", SATISFIED, rule, state, f"{state} is an eligible state."))
        else:
            out.append(_crit("state", "State / domicile", NOT_SATISFIED, rule, state, f"Only for {rule}; you are from {state}."))

    # 11. Special conditions
    sc_labels = {x["code"]: x["label"] for x in vocab()["special_circumstances"]}
    for cond in s.conditions or []:
        key, text = cond["key"], cond.get("text", "")
        if cond["kind"] == "profile_tags":
            rule = " OR ".join(sc_labels.get(t, t) for t in cond["tags"])
            hit = tags & set(cond["tags"])
            if hit:
                out.append(_crit(key, "Beneficiary group", SATISFIED, rule, ", ".join(sc_labels.get(t, t) for t in hit),
                                 "You declared an eligible beneficiary status."))
            elif not tags_answered:
                out.append(_missing(key, "Beneficiary group", rule, "special_circumstances", "special circumstances"))
            else:
                out.append(_crit(key, "Beneficiary group", NOT_SATISFIED, rule, "None declared",
                                 f"Restricted to: {text}."))
        elif cond["kind"] == "citizenship":
            cit = getattr(student, "is_indian_citizen", None)
            if cit is None:
                out.append(_missing(key, "Citizenship", text, "is_indian_citizen", "citizenship"))
            else:
                out.append(_crit(key, "Citizenship", SATISFIED if cit else NOT_SATISFIED, text, "Yes" if cit else "No",
                                 "Requires Indian nationality/residence."))
        else:
            ans = answers.get(key)
            if ans == "yes":
                out.append(_crit(key, "Scheme condition", SATISFIED, text, "Yes (self-declared)", f"You confirmed: {text}."))
            elif ans == "no":
                out.append(_crit(key, "Scheme condition", NOT_SATISFIED, text, "No (self-declared)", f"You indicated you do not meet: {text}."))
            else:
                out.append(_question(key, "Scheme condition", text, f"Does this apply to you? “{text}”",
                                     "This condition can only be confirmed by you or your institution."))
    return out


def outcome(criteria: list[dict]) -> str:
    statuses = [c["status"] for c in criteria]
    if NOT_SATISFIED in statuses:
        return "not_eligible"
    reasons = {c["unknown_reason"] for c in criteria if c["status"] == UNKNOWN}
    if reasons & {"student_missing", "needs_confirmation"}:
        return "potential_match"
    if "scholarship_unresolved" in reasons:
        return "eligible_pending_verification"
    return "eligible"
