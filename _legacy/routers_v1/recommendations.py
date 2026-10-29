from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import app.schemas as schemas
import app.models as models
from app.database import get_db
from app.services.recommendation.scoring import generate_recommendations

router = APIRouter(
    prefix="/api/recommendations",
    tags=["Recommendations"]
)

@router.get("/{student_id}")
def get_student_recommendations(student_id: str, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    active_version = db.query(models.DatasetVersion).filter(models.DatasetVersion.is_active == True).first()
    if not active_version:
        return []
        
    scholarships = db.query(models.Scholarship).filter(
        models.Scholarship.dataset_version_id == active_version.id
    ).all()
    
    recommendations = generate_recommendations(student, scholarships)
    
    return recommendations
