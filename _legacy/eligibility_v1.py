from app.models import Student, Scholarship

def check_eligibility(student: Student, scholarship: Scholarship) -> dict:
    """
    Deterministically checks if a student is eligible for a scholarship.
    Returns a dict with:
    - is_eligible (bool)
    - reasons (list of match explanations)
    - failures (list of mismatch explanations)
    - missing_info (list of missing data fields)
    """
    is_eligible = True
    reasons = []
    failures = []
    missing_info = []

    # 1. CGPA / Percentage
    if scholarship.minimum_cgpa:
        if student.cgpa is None:
            missing_info.append("CGPA")
        elif student.cgpa >= scholarship.minimum_cgpa:
            reasons.append(f"✓ CGPA requirement met (Required: {scholarship.minimum_cgpa}, Yours: {student.cgpa})")
        else:
            is_eligible = False
            failures.append(f"❌ CGPA too low (Required: {scholarship.minimum_cgpa}, Yours: {student.cgpa})")

    # 2. Family Income
    if scholarship.maximum_family_income:
        if student.family_income is None:
            missing_info.append("Family Income")
        elif student.family_income <= scholarship.maximum_family_income:
            reasons.append(f"✓ Income requirement met (Max: ₹{scholarship.maximum_family_income:,.0f}, Yours: ₹{student.family_income:,.0f})")
        else:
            is_eligible = False
            failures.append(f"❌ Family income exceeds limit (Max: ₹{scholarship.maximum_family_income:,.0f}, Yours: ₹{student.family_income:,.0f})")

    # 3. Gender
    if scholarship.gender_requirement and scholarship.gender_requirement.upper() != "ANY":
        if not student.gender:
            missing_info.append("Gender")
        elif scholarship.gender_requirement.upper() == student.gender.upper():
            reasons.append(f"✓ Gender requirement met ({scholarship.gender_requirement})")
        else:
            is_eligible = False
            failures.append(f"❌ Gender mismatch (Required: {scholarship.gender_requirement})")

    # 4. Education Level
    if scholarship.education_level and scholarship.education_level.upper() != "ANY":
        if not student.education_level:
            missing_info.append("Education Level")
        elif scholarship.education_level.upper() in student.education_level.upper():
            reasons.append(f"✓ Education level matched ({scholarship.education_level})")
        # Skipping hard fail for education level as it can be ambiguous (e.g. "Degree" vs "B.Tech") - better handled in scoring for now unless exact mismatch

    # 5. Course/Fields (Basic substring check for now)
    if scholarship.eligible_courses and scholarship.eligible_courses.upper() != "ANY" and str(scholarship.eligible_courses) != "nan":
        if not student.course:
            missing_info.append("Course")
        elif student.course.upper() in scholarship.eligible_courses.upper():
            reasons.append(f"✓ Course matched ({student.course})")

    # Additional requirements can be added here (category, disability, states)
    if scholarship.category_requirement and scholarship.category_requirement.upper() != "ANY":
        if scholarship.category_requirement.upper() in ["SC", "ST", "OBC", "GENERAL"]:
             if not student.category:
                 missing_info.append("Category")
             elif student.category.upper() == scholarship.category_requirement.upper():
                 reasons.append(f"✓ Category matched ({student.category})")
             # Not failing hard as many categories are complex "Government reservation norms" etc.
        
    return {
        "is_eligible": is_eligible,
        "reasons": reasons,
        "failures": failures,
        "missing_info": missing_info
    }
