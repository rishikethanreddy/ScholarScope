import os
import json
from app.schemas import ScholarshipCreate

import google.generativeai as genai

def extract_scholarship_from_text(text: str) -> ScholarshipCreate:
    api_key = os.environ.get("AI_API_KEY")
    if not api_key:
        print("WARNING: AI_API_KEY environment variable is not set. Returning MOCK data.")
        return get_mock_scholarship_data()
        
    try:
        genai.configure(api_key=api_key)
        # Using gemini-3.6-flash as recommended by the API
        model = genai.GenerativeModel('gemini-3.6-flash', generation_config={"response_mime_type": "application/json"})
        
        prompt = f"""
        Extract the following scholarship details into JSON exactly matching this schema.
        If a detail is not explicitly mentioned, guess reasonably or use 'Not specified' for strings, or null/0 for numbers.
        
        Schema details expected (all strings unless noted):
        - name
        - provider
        - provider_type
        - scholarship_type
        - education_level
        - eligible_courses
        - eligible_fields
        - year_of_study
        - minimum_cgpa (float)
        - minimum_percentage (float)
        - maximum_family_income (float)
        - gender_requirement (e.g. 'All', 'Female')
        - category_requirement
        - disability_requirement
        - special_background_requirement
        - eligible_states
        - domicile_requirement
        - scholarship_amount
        - amount_frequency
        - application_start_date (YYYY-MM-DD string or null)
        - application_deadline (YYYY-MM-DD string or null)
        - application_status
        - application_method
        - application_url
        - official_source_url
        - short_description
        - required_documents
        
        Raw Text:
        {text}
        """
        response = model.generate_content(prompt)
        parsed_data = json.loads(response.text)
        
        # Ensure dates are properly parsed if they exist
        if parsed_data.get('application_start_date') == "null" or not parsed_data.get('application_start_date'):
            parsed_data['application_start_date'] = None
        if parsed_data.get('application_deadline') == "null" or not parsed_data.get('application_deadline'):
            parsed_data['application_deadline'] = None
            
        # Ensure status is set
        parsed_data['status'] = 'DRAFT'
            
        return ScholarshipCreate(**parsed_data)
        
    except Exception as e:
        with open("ai_error.log", "a") as f:
            f.write(f"AI Extraction failed: {str(e)}\n")
        print(f"AI Extraction failed: {e}. Falling back to MOCK data.")
        return get_mock_scholarship_data()


def get_mock_scholarship_data() -> ScholarshipCreate:
    return ScholarshipCreate(
        name="AI Extracted Tech Scholarship (Mock)",
        provider="Tech Foundation",
        provider_type="Corporate",
        scholarship_type="Merit-Based",
        education_level="Undergraduate",
        eligible_courses="B.Tech, B.E.",
        eligible_fields="Computer Science, IT",
        year_of_study="1st Year, 2nd Year",
        minimum_cgpa=8.0,
        minimum_percentage=75.0,
        maximum_family_income=500000.0,
        gender_requirement="All",
        category_requirement="All",
        disability_requirement="No",
        special_background_requirement="None",
        eligible_states="All India",
        domicile_requirement="Indian",
        scholarship_amount="50,000",
        amount_frequency="Annual",
        application_status="Open",
        application_method="Online",
        application_url="https://example.com/apply",
        official_source_url="https://example.com/scholarship",
        short_description="This is a mock extracted scholarship since no API key was provided.",
        required_documents="10th Marksheet, 12th Marksheet, Aadhar Card, Income Certificate",
        status="DRAFT"
    )
