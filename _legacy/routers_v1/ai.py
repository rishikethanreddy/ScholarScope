from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import app.schemas as schemas
import app.models as models
from app.database import get_db
from app.services.ai.extractor import extract_scholarship_from_text
from app.services.recommendation.eligibility import check_eligibility
from app.services.recommendation.scoring import calculate_match_score
import PyPDF2 
import io
from fastapi import Form

router = APIRouter(
    prefix="/api/ai",
    tags=["AI"]
)

@router.post("/extract-scholarship", response_model=schemas.ScholarshipCreate)
def extract_scholarship(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.file.read()))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        # Call the AI service
        extracted_data = extract_scholarship_from_text(text)
        extracted_data.status = "DRAFT" # Must be reviewed
        return extracted_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-eligibility")
def check_scholarship_eligibility(
    student_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.file.read()))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        # Call the AI service
        extracted_schema = extract_scholarship_from_text(text)
        extracted_schema.status = "DRAFT"
        
        # Convert Pydantic schema to SQLAlchemy model (in-memory, not saved)
        temp_scholarship = models.Scholarship(**extracted_schema.model_dump())
        
        # Check eligibility
        eligibility = check_eligibility(student, temp_scholarship)
        
        score = 0.0
        if eligibility['is_eligible']:
            score = calculate_match_score(student, temp_scholarship)
            
        return {
            "scholarship_data": extracted_schema.model_dump(),
            "eligibility": eligibility,
            "score": score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
