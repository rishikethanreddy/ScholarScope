from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import app.schemas as schemas
import app.models as models
from app.database import get_db

router = APIRouter(
    prefix="/api/scholarships",
    tags=["Scholarships"]
)

@router.get("/", response_model=List[schemas.Scholarship])
def get_scholarships(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    # Get active dataset
    active_version = db.query(models.DatasetVersion).filter(models.DatasetVersion.is_active == True).first()
    
    if not active_version:
        return []
        
    scholarships = db.query(models.Scholarship).filter(
        models.Scholarship.dataset_version_id == active_version.id
    ).offset(skip).limit(limit).all()
    
    return scholarships

@router.get("/{scholarship_id}", response_model=schemas.Scholarship)
def get_scholarship(scholarship_id: str, db: Session = Depends(get_db)):
    scholarship = db.query(models.Scholarship).filter(models.Scholarship.id == scholarship_id).first()
    if not scholarship:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    return scholarship
