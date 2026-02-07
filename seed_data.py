from app import app, db, User, DetectionRecord, CountingRecord, NAIC_BARANGAY_COORDS
import random
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

import json

def ph_time_now():
    return datetime.utcnow() + timedelta(hours=8)

def seed_data():
    with app.app_context():
        print("Seeding 20 dummy accounts using Naic barangays...")
        
        # Pests list
        INSECTS = ["aphids", "leafbeetle", "slantfacedgrasshopper"]
        BENEFICIALS = ["pygmygrasshopper"]
        
        barangays = list(NAIC_BARANGAY_COORDS.keys())
        
        for i in range(1, 21):
            username = f"farmer_test_{i}"
            
            # Check if exists
            if User.query.filter_by(username=username).first():
                # Just skip creation, but we can add new data to them if we want
                # For this task, let's assume we want fresh data for everyone or just new users
                # To be safe and compliant with "rework dummy data", let's continue to add records to existing users too?
                # Actually, the user said "modify it... rework the dummy data". 
                # Simplest is to just use the user object found or created.
                user = User.query.filter_by(username=username).first()
            else:
                barangay = random.choice(barangays)
                base_lat, base_lng = NAIC_BARANGAY_COORDS[barangay]
                
                # Random jitter for realistic spread
                lat = base_lat + random.uniform(-0.002, 0.002)
                lng = base_lng + random.uniform(-0.002, 0.002)
                
                user = User(
                    username=username,
                    full_name=f"Test Farmer {i} ({barangay})",
                    password_hash=generate_password_hash("password123"),
                    municipality="Naic",
                    street_barangay=barangay,
                    role="farmer",
                    latitude=lat,
                    longitude=lng
                )
                db.session.add(user)
                db.session.commit() # Commit to get ID
            
            # Add random pest data
            # 1-5 Detection Records
            for _ in range(random.randint(1, 5)):
                is_pest = random.choice([True, True, False]) # 2/3 chance pest
                insect = random.choice(INSECTS) if is_pest else random.choice(BENEFICIALS)
                
                # Random date within 30 days
                days_ago = random.randint(0, 30)
                record_time = ph_time_now() - timedelta(days=days_ago)

                record = DetectionRecord(
                    user_id=user.id,
                    insect_name=insect,
                    confidence=random.uniform(0.7, 0.99),
                    image_file="placeholder.jpg",
                    is_beneficial=not is_pest,
                    timestamp=record_time
                )
                db.session.add(record)
                
            # 0-3 Counting Records (Groups)
            for _ in range(random.randint(0, 3)):
                count_val = random.randint(5, 50)
                # Create a breakdown
                breakdown = {}
                pest_type = random.choice(INSECTS) if random.random() > 0.3 else random.choice(BENEFICIALS)
                breakdown[pest_type] = count_val
                
                # Random date within 30 days
                days_ago = random.randint(0, 30)
                record_time = ph_time_now() - timedelta(days=days_ago)

                c_record = CountingRecord(
                    user_id=user.id,
                    total_count=count_val,
                    image_file="placeholder_count.jpg",
                    breakdown=json.dumps(breakdown),
                    timestamp=record_time
                )
                db.session.add(c_record)
            
            print(f"Created {user.full_name} with random data.")
            
        db.session.commit()
        print("Seeding complete!")

if __name__ == "__main__":
    seed_data()
