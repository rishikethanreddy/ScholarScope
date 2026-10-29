import pandas as pd
import math
from datetime import datetime
from typing import List, Dict, Any
from app.schemas import ScholarshipCreate

def parse_date(date_str: str):
    if pd.isna(date_str) or date_str == 'UNKNOWN':
        return None
    try:
        # Expected format YYYY-MM-DD
        return datetime.strptime(str(date_str), '%Y-%m-%d').date()
    except Exception:
        return None

def parse_float(val: Any):
    if pd.isna(val) or val == 'UNKNOWN' or val == 'ANY' or val == 'Scheme/norm dependent':
        return None
    try:
        return float(val)
    except Exception:
        return None

def load_scholarships_from_csv(file_path: str) -> List[ScholarshipCreate]:
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise Exception(f"Failed to read CSV: {e}")
        
    scholarships = []
    
    for _, row in df.iterrows():
        scholarship_data = {
            "scholarship_id": str(row.get('scholarship_id', '')),
            "name": str(row.get('scholarship_name', '')),
            "provider": str(row.get('provider', '')),
            "provider_type": str(row.get('provider_type', '')),
            "scholarship_type": str(row.get('scholarship_type', '')),
            "education_level": str(row.get('education_level', '')),
            "eligible_courses": str(row.get('eligible_courses', '')),
            "eligible_fields": str(row.get('eligible_fields', '')),
            "year_of_study": str(row.get('year_of_study', '')),
            "minimum_cgpa": parse_float(row.get('minimum_cgpa_or_percentage')), # Simplified mapping for now
            "minimum_percentage": parse_float(row.get('minimum_cgpa_or_percentage')), # Same field used
            "maximum_family_income": parse_float(row.get('maximum_family_income')),
            "gender_requirement": str(row.get('gender', 'ANY')),
            "category_requirement": str(row.get('category', 'ANY')),
            "disability_requirement": str(row.get('disability_requirement', 'ANY')),
            "special_background_requirement": str(row.get('special_background_requirement', 'ANY')),
            "eligible_states": str(row.get('eligible_states', 'All India')),
            "domicile_requirement": str(row.get('domicile_requirement', 'UNKNOWN')),
            "scholarship_amount": str(row.get('scholarship_amount', 'UNKNOWN')),
            "amount_frequency": str(row.get('amount_frequency', 'UNKNOWN')),
            "application_start_date": parse_date(row.get('application_start_date')),
            "application_deadline": parse_date(row.get('application_deadline')),
            "application_status": str(row.get('application_status', 'UNKNOWN')),
            "application_method": str(row.get('application_method', 'UNKNOWN')),
            "application_url": str(row.get('official_application_url', '')),
            "official_source_url": str(row.get('official_source_url', '')),
            "short_description": str(row.get('short_description', '')),
            "required_documents": str(row.get('required_documents', '')),
            "status": "APPROVED" # Default for CSV imports
        }
        
        # Replace 'nan' string with empty string for cleaner data
        for key, value in scholarship_data.items():
            if value == 'nan':
                scholarship_data[key] = ''
                
        scholarships.append(ScholarshipCreate(**scholarship_data))
        
    return scholarships
