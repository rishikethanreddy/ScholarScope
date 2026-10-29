from app.models import Student, Scholarship
from app.services.recommendation.eligibility import check_eligibility
import json
import os

def load_scoring_config():
    # Load scoring weights from config file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    config_path = os.path.join(base_dir, 'config', 'scoring_config.json')
    
    default_weights = {
        "academic_fit": 0.30,
        "financial_fit": 0.25,
        "course_fit": 0.20,
        "category_fit": 0.10,
        "location_fit": 0.10,
        "other_factors": 0.05
    }
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            try:
                config = json.load(f)
                return config.get('weights', default_weights)
            except Exception:
                pass
                
    return default_weights

def calculate_match_score(student: Student, scholarship: Scholarship) -> float:
    """
    Calculates a match score for a given student and scholarship based on configurable weights.
    Returns a score between 0.0 and 100.0
    """
    weights = load_scoring_config()
    score = 0.0
    
    # 1. Academic Fit (up to 100 points * weight)
    academic_score = 0
    if scholarship.minimum_cgpa and student.cgpa:
        # If student CGPA is higher, they get a better score (up to 100)
        margin = student.cgpa - scholarship.minimum_cgpa
        if margin >= 0:
            academic_score = min(100, 80 + (margin * 10))
    elif student.cgpa:
         academic_score = student.cgpa * 10 # Estimate
    else:
        academic_score = 50 # Default middle ground if no req
        
    score += academic_score * weights.get("academic_fit", 0.3)
    
    # 2. Financial Fit
    financial_score = 0
    if scholarship.maximum_family_income and student.family_income:
        if student.family_income <= scholarship.maximum_family_income:
            # Lower income relative to max gets a slightly better score
            ratio = student.family_income / scholarship.maximum_family_income
            financial_score = 100 - (ratio * 30) # 70 to 100 range
    else:
        financial_score = 50
        
    score += financial_score * weights.get("financial_fit", 0.25)
    
    # 3. Course Fit
    course_score = 0
    if scholarship.eligible_courses and scholarship.eligible_courses.upper() != "ANY" and str(scholarship.eligible_courses) != "nan":
        if student.course and student.course.upper() in scholarship.eligible_courses.upper():
            course_score = 100
        else:
            course_score = 20 # Might still be related
    else:
        course_score = 80 # Open to many courses
        
    score += course_score * weights.get("course_fit", 0.2)
    
    # Simple base scores for the rest
    score += 80 * weights.get("category_fit", 0.1)
    
    # State match
    if scholarship.eligible_states and student.state:
        if "ALL INDIA" in scholarship.eligible_states.upper() or student.state.upper() in scholarship.eligible_states.upper():
            score += 100 * weights.get("location_fit", 0.1)
        else:
             score += 0
    else:
        score += 50 * weights.get("location_fit", 0.1)
        
    score += 50 * weights.get("other_factors", 0.05)
    
    return round(score, 2)

def generate_recommendations(student: Student, scholarships: list[Scholarship]) -> list:
    """
    Returns a list of recommendations, ranked by score.
    """
    results = []
    
    for scholarship in scholarships:
        eligibility = check_eligibility(student, scholarship)
        
        score = 0.0
        if eligibility['is_eligible']:
            score = calculate_match_score(student, scholarship)
            
        results.append({
            "scholarship_id": scholarship.id,
            "scholarship": scholarship,
            "is_eligible": eligibility['is_eligible'],
            "score": score,
            "reasons": eligibility['reasons'],
            "failures": eligibility['failures'],
            "missing_info": eligibility['missing_info']
        })
        
    # Sort: Eligible first, then by score descending
    results.sort(key=lambda x: (x['is_eligible'], x['score']), reverse=True)
    return results
