from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import app.schemas as schemas
import app.models as models
from app.database import get_db

router = APIRouter(
    prefix="/api/students",
    tags=["Students"]
)

@router.post("/", response_model=schemas.Student)
def create_student(student: schemas.StudentCreate, db: Session = Depends(get_db)):
    db_student = models.Student(**student.model_dump())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student

@router.get("/", response_model=List[schemas.Student])
def get_students(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Student).offset(skip).limit(limit).all()

@router.get("/{student_id}", response_model=schemas.Student)
def read_student(student_id: str, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@router.put("/{student_id}", response_model=schemas.Student)
def update_student(student_id: str, student: schemas.StudentUpdate, db: Session = Depends(get_db)):
    db_student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if db_student is None:
        raise HTTPException(status_code=404, detail="Student not found")
        
    for var, value in vars(student).items():
        setattr(db_student, var, value) if value is not None else None
        
    db.commit()
    db.refresh(db_student)
    return db_student
