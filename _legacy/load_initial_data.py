import os
import sys

# Ensure the app module can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.ingestion.controller import import_dataset, activate_dataset_version

def load_data():
    db = SessionLocal()
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(BASE_DIR, 'data', 'imports', 'india_scholarship_dataset_2026_27_researched.csv')
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
        
    print("Importing dataset...")
    version = import_dataset(
        db=db,
        file_path=csv_path,
        version_name="v1.0",
        dataset_name="Initial Scholarship Dataset 2026-27"
    )
    
    print(f"Dataset imported! Version ID: {version.id}")
    print(f"Records: {version.num_records} total, {version.num_valid} valid.")
    
    print("Activating dataset...")
    activate_dataset_version(db, version.id)
    print("Done!")
    
    db.close()

if __name__ == "__main__":
    load_data()
