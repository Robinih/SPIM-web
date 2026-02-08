from app import app, db, User, DetectionRecord, CountingRecord, NAIC_BARANGAY_COORDS, check_infestation_threshold
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
            
            # Determine scenario for this user to ensure we see all alert types
            scenario = random.choice(['High', 'Medium', 'Low', 'Safe'])
            
            pests_to_add = 0
            if scenario == 'High':
                pests_to_add = random.randint(16, 25)
            elif scenario == 'Medium':
                pests_to_add = random.randint(6, 15)
            elif scenario == 'Low':
                pests_to_add = random.randint(1, 5)
            else: # Safe
                pests_to_add = 0
                
            print(f"  -> Scenario: {scenario} ({pests_to_add} pests)")
            
            # Add Detection Records (Individual pests)
            msg_pests = min(pests_to_add, 5) # Add up to 5 individual records
            pests_to_add -= msg_pests
            
            for _ in range(msg_pests):
                insect = random.choice(INSECTS)
                # TODAY with random hours
                hours_ago = random.randint(0, 12)
                record_time = ph_time_now() - timedelta(hours=hours_ago)

                record = DetectionRecord(
                    user_id=user.id,
                    insect_name=insect,
                    confidence=random.uniform(0.7, 0.99),
                    image_file="placeholder.jpg",
                    is_beneficial=False,
                    timestamp=record_time
                )
                db.session.add(record)
                
            # If we still need more pests for the scenario, add them as a Group Count
            if pests_to_add > 0:
                breakdown = {random.choice(INSECTS): pests_to_add}
                hours_ago = random.randint(0, 12)
                record_time = ph_time_now() - timedelta(hours=hours_ago)
                
                c_record = CountingRecord(
                    user_id=user.id,
                    total_count=pests_to_add,
                    image_file="placeholder_count.jpg",
                    breakdown=json.dumps(breakdown),
                    timestamp=record_time
                )
                db.session.add(c_record)

            # Add some beneficials too (just for realism)
            for _ in range(random.randint(0, 3)):
                insect = random.choice(BENEFICIALS)
                hours_ago = random.randint(0, 24)
                record_time = ph_time_now() - timedelta(hours=hours_ago)
                
                record = DetectionRecord(
                    user_id=user.id,
                    insect_name=insect,
                    confidence=random.uniform(0.7, 0.99),
                    image_file="placeholder.jpg",
                    is_beneficial=True,
                    timestamp=record_time
                )
                db.session.add(record)
            
            # Commit all records for this user
            db.session.commit()
            
            # Trigger alert check for this user (only if they have current data)
            # The function checks counts internally
            check_infestation_threshold(user.id, user.municipality, is_test=False)

            
            print(f"Created {user.full_name} with random data.")
            
        print("Seeding complete!")

if __name__ == "__main__":
    seed_data()
