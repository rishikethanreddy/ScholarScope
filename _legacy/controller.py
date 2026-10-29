from sqlalchemy.orm import Session
from app.models import DatasetVersion, Scholarship
from app.services.ingestion.csv_parser import load_scholarships_from_csv
import os
import shutil

def import_dataset(db: Session, file_path: str, version_name: str, dataset_name: str = "scholarships_dataset"):
    # Parse the CSV
    scholarships_data = load_scholarships_from_csv(file_path)
    
    # Calculate stats
    num_records = len(scholarships_data)
    num_valid = len([s for s in scholarships_data if s]) # Simplified for now
    num_rejected = num_records - num_valid
    
    # Create new DatasetVersion
    new_version = DatasetVersion(
        dataset_name=dataset_name,
        version=version_name,
        num_records=num_records,
        num_valid=num_valid,
        num_rejected=num_rejected,
        is_active=False
    )
    
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    
    # Insert scholarships
    for s_data in scholarships_data:
        db_scholarship = Scholarship(
            dataset_version_id=new_version.id,
            **s_data.model_dump(exclude={'dataset_version_id'})
        )
        db.add(db_scholarship)
        
    db.commit()
    
    return new_version

def activate_dataset_version(db: Session, version_id: str):
    # Deactivate all
    db.query(DatasetVersion).update({DatasetVersion.is_active: False})
    
    # Activate selected
    target_version = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
    if target_version:
        target_version.is_active = True
        db.commit()
        return True
    return False
