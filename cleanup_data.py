from app import app, db, DetectionRecord, CountingRecord
from utils import INSECT_TYPES
import json

def cleanup():
    with app.app_context():
        print("Starting cleanup...")
        allowed_insects = list(INSECT_TYPES.keys())
        
        # 1. Cleanup DetectionRecords
        all_detections = DetectionRecord.query.all()
        deleted_det = 0
        for d in all_detections:
            # Case insensitive check
            if d.insect_name.lower() not in allowed_insects:
                db.session.delete(d)
                deleted_det += 1
        
        # 2. Cleanup CountingRecords
        # Strategy: If a breakdown exists, filter it. If total count is all invalid insects, delete record.
        # But for simplicity in this task, if the main 'desc' or inferred type isn't allowed, delete.
        # Or more aggressively: Just wipe all and re-seed to ensure purity. 
        # Given the instruction "re-seed data", wiping might be cleaner, but let's try to be selective first as per request "modify it".
        
        all_counts = CountingRecord.query.all()
        deleted_cnt = 0
        for c in all_counts:
            should_delete = True
            if c.breakdown:
                try:
                    data = json.loads(c.breakdown)
                    new_data = {}
                    for insect, count in data.items():
                        if insect.lower() in allowed_insects:
                            new_data[insect] = count
                    
                    if new_data:
                        c.breakdown = json.dumps(new_data)
                        should_delete = False
                        # Recalculate total? Assuming total_count matches breakdown
                        c.total_count = sum(new_data.values())
                    else:
                        should_delete = True
                except:
                    should_delete = True
            
            if should_delete:
                db.session.delete(c)
                deleted_cnt += 1

        db.session.commit()
        print(f"Cleanup complete. Deleted {deleted_det} detection records and {deleted_cnt} counting records.")

if __name__ == "__main__":
    cleanup()
