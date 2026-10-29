"""Baseline: the project's original (v1) CSV mapping and eligibility logic, copied from _legacy/ with only the
model imports replaced by plain objects. Kept verbatim in behaviour, including its known defects, so the
comparison is fair to what existed before."""
from types import SimpleNamespace


def _parse_float(val):
    if val in (None, "", "UNKNOWN", "ANY", "Scheme/norm dependent"):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def legacy_scholarship(row: dict) -> SimpleNamespace:
    """v1 csv_parser mapping (note: minimum_cgpa_or_percentage feeds BOTH cgpa and percentage)."""
    return SimpleNamespace(
        minimum_cgpa=_parse_float(row.get("minimum_cgpa_or_percentage")),
        minimum_percentage=_parse_float(row.get("minimum_cgpa_or_percentage")),
        maximum_family_income=_parse_float(row.get("maximum_family_income")),
        gender_requirement=row.get("gender", "ANY"),
        education_level=row.get("education_level", ""),
        eligible_courses=row.get("eligible_courses", ""),
        category_requirement=row.get("category", "ANY"),
    )


def check_eligibility(student, scholarship) -> dict:
    """Verbatim logic of _legacy/eligibility_v1.check_eligibility."""
    is_eligible = True
    reasons, failures, missing_info = [], [], []
    if scholarship.minimum_cgpa:
        if student.cgpa is None:
            missing_info.append("CGPA")
        elif student.cgpa >= scholarship.minimum_cgpa:
            reasons.append("cgpa")
        else:
            is_eligible = False
            failures.append("cgpa")
    if scholarship.maximum_family_income:
        if student.family_income is None:
            missing_info.append("Family Income")
        elif student.family_income <= scholarship.maximum_family_income:
            reasons.append("income")
        else:
            is_eligible = False
            failures.append("income")
    if scholarship.gender_requirement and scholarship.gender_requirement.upper() != "ANY":
        if not student.gender:
            missing_info.append("Gender")
        elif scholarship.gender_requirement.upper() == student.gender.upper():
            reasons.append("gender")
        else:
            is_eligible = False
            failures.append("gender")
    if scholarship.education_level and scholarship.education_level.upper() != "ANY":
        if not student.education_level:
            missing_info.append("Education Level")
        elif scholarship.education_level.upper() in student.education_level.upper():
            reasons.append("education")
    if scholarship.eligible_courses and scholarship.eligible_courses.upper() != "ANY" and str(scholarship.eligible_courses) != "nan":
        if not student.course:
            missing_info.append("Course")
        elif student.course.upper() in scholarship.eligible_courses.upper():
            reasons.append("course")
    return {"is_eligible": is_eligible, "reasons": reasons, "failures": failures, "missing_info": missing_info}


LEVEL_TEXT = {"UG": "Degree", "PG": "Postgraduate", "DIPLOMA": "Diploma", "PRE_MATRIC": "School",
              "POST_MATRIC_SCHOOL": "School", "RESEARCH": "Research"}
COURSE_TEXT = {"ENGINEERING_TECHNOLOGY": "B.Tech", "AGRICULTURE": "M.Sc Agriculture", "SCIENCE": "B.Sc",
               "SCHOOL_GENERAL": "School"}


def legacy_student(p: dict) -> SimpleNamespace:
    """Map a persona to the v1 student schema (v1 form fields: gender text, income, CGPA, level, course)."""
    return SimpleNamespace(
        gender={"FEMALE": "Female", "MALE": "Male"}.get(p.get("gender"), p.get("gender")),
        family_income=p.get("annual_family_income"),
        cgpa=p.get("cgpa"),
        education_level=LEVEL_TEXT.get(p.get("education_level"), ""),
        course=COURSE_TEXT.get(p.get("discipline"), ""),
        category=p.get("category"),
    )
