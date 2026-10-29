from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import app.schemas as schemas
import app.models as models
from app.database import get_db
from app.services.ingestion.controller import import_dataset, activate_dataset_version
import os
import shutil

router = APIRouter(
    prefix="/api/datasets",
    tags=["Datasets"]
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
IMPORTS_DIR = os.path.join(BASE_DIR, 'data', 'imports')

@router.post("/import", response_model=schemas.DatasetVersion)
def upload_and_import_dataset(
    version_name: str,
    dataset_name: str,
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
    os.makedirs(IMPORTS_DIR, exist_ok=True)
    file_path = os.path.join(IMPORTS_DIR, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        version = import_dataset(db, file_path, version_name, dataset_name)
        return version
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{version_id}/activate")
def activate_dataset(version_id: str, db: Session = Depends(get_db)):
    success = activate_dataset_version(db, version_id)
    if not success:
        raise HTTPException(status_code=404, detail="Dataset version not found")
    return {"message": "Dataset version activated successfully"}

@router.get("/", response_model=List[schemas.DatasetVersion])
def get_dataset_versions(db: Session = Depends(get_db)):
    return db.query(models.DatasetVersion).order_by(models.DatasetVersion.import_date.desc()).all()
