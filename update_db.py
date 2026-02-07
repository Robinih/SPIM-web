from app import app, db, User, NAIC_BARANGAY_COORDS, MUNICIPALITY_COORDS
from sqlalchemy import text
import random
from datetime import datetime

def migrate_and_fix():
    with app.app_context():
        # 1. Add created_at column
        try:
            # Check if column exists (simple check by trying to query it, or catching error on add)
            # SQLite doesn't support IF NOT EXISTS in ADD COLUMN well in all versions, 
            # but we can try-catch the alter statement.
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN created_at DATETIME"))
                conn.commit()
                print("Added created_at column.")
        except Exception as e:
            print(f"Column created_at might already exist or error: {e}")

        # 2. Update existing users with default created_at (now)
        # We can't easily know the real creation date, so we use now.
        users = User.query.all()
        now = datetime.utcnow() # Store as UTC naive, app handles +8
        
        for u in users:
            if u.created_at is None:
                u.created_at = now
            
            # 3. Fix Missing Coordinates
            if u.latitude is None or u.longitude is None:
                print(f"Fixing coordinates for user: {u.username} ({u.municipality}, {u.street_barangay})")
                
                final_lat = None
                final_lng = None
                
                # 1. Try Specific Barangay
                if u.municipality == "Naic" and u.street_barangay in NAIC_BARANGAY_COORDS:
                    base_lat, base_lng = NAIC_BARANGAY_COORDS[u.street_barangay]
                    final_lat = base_lat + random.uniform(-0.001, 0.001)
                    final_lng = base_lng + random.uniform(-0.001, 0.001)
                # 2. Key Municipality
                elif u.municipality in MUNICIPALITY_COORDS:
                    base_lat, base_lng = MUNICIPALITY_COORDS[u.municipality]
                    final_lat = base_lat + random.uniform(-0.005, 0.005)
                    final_lng = base_lng + random.uniform(-0.005, 0.005)
                
                if final_lat and final_lng:
                    u.latitude = final_lat
                    u.longitude = final_lng
                    print(f" -> Assigned: {final_lat}, {final_lng}")
                else:
                    print(" -> Could not determine coordinates.")

        db.session.commit()
        print("Migration and Fix Completed.")

if __name__ == "__main__":
    migrate_and_fix()
