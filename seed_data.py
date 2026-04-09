from app import app, db, User, DetectionRecord, CountingRecord, Notification, NAIC_BARANGAY_COORDS, check_infestation_threshold
import random
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

import json

def ph_time_now():
    return datetime.utcnow() + timedelta(hours=8)

def seed_data():
    with app.app_context():
        print("Seeding 20 dummy accounts using Naic barangays...")
        
        # New 11 pest families
        INSECTS = [
            "Planthopper", "Leafhopper", "Weevil", "Tube-tailed Thrips", 
            "Gall Midge", "Frit Fly", "Shore Fly", "Common Thrips",
            "Snout Moth / Stem Borer", "Armyworm / Owlet Moth", "Skipper Butterfly"
        ]
        
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
                # Past days (1-7 days ago) so they don't trigger today's FCM alerts
                days_ago = random.randint(1, 7)
                hours_ago = random.randint(0, 12)
                record_time = ph_time_now() - timedelta(days=days_ago, hours=hours_ago)

                record = DetectionRecord(
                    user_id=user.id,
                    insect_name=insect,
                    confidence=random.uniform(0.7, 0.99),
                    image_file="placeholder.jpg",
                    timestamp=record_time
                )
                db.session.add(record)
                
            # If we still need more pests for the scenario, add them as a Group Count
            if pests_to_add > 0:
                breakdown = {random.choice(INSECTS): pests_to_add}
                days_ago = random.randint(1, 7)
                hours_ago = random.randint(0, 12)
                record_time = ph_time_now() - timedelta(days=days_ago, hours=hours_ago)
                
                c_record = CountingRecord(
                    user_id=user.id,
                    total_count=pests_to_add,
                    image_file="placeholder_count.jpg",
                    breakdown=json.dumps(breakdown),
                    timestamp=record_time
                )
                db.session.add(c_record)


            # Commit all records for this user
            db.session.commit()

            # Create a past notification for non-Safe scenarios (no FCM push, just DB record)
            if scenario != 'Safe':
                total_pests = msg_pests + (pests_to_add if pests_to_add > 0 else 0)
                if scenario == 'High':
                    notif_msg = f"CRITICAL: High Pest Activity ({total_pests} pests detected) in {user.street_barangay}, {user.municipality}. Immediate check recommended."
                elif scenario == 'Medium':
                    notif_msg = f"WARNING: Elevated Pest Activity ({total_pests} pests detected) in {user.street_barangay}, {user.municipality}."
                else:
                    notif_msg = f"INFO: Minor Pest Activity ({total_pests} pests detected) in {user.street_barangay}, {user.municipality}. Monitor situation."
                
                notif_time = ph_time_now() - timedelta(days=random.randint(1, 7), hours=random.randint(0, 12))
                
                # Send to all farmers in the same municipality as a past broadcast
                all_farmers = User.query.filter_by(municipality=user.municipality, role='farmer').all()
                for farmer in all_farmers:
                    n = Notification(
                        user_id=farmer.id,
                        from_user_id=user.id,
                        message=notif_msg,
                        level=scenario,
                        timestamp=notif_time
                    )
                    db.session.add(n)
                db.session.commit()
            
            print(f"Created {user.full_name} with random data.")
            
        # ---- 3 Guaranteed Alert Farmers (Low, Medium, High) ----
        # These always produce recent data that triggers the infestation threshold
        alert_scenarios = [
            {'label': 'Low',    'pest_count': 3,  'barangay': 'Bancaan'},
            {'label': 'Medium', 'pest_count': 10, 'barangay': 'Kanluran'},
            {'label': 'High',   'pest_count': 20, 'barangay': 'Santulan'},
        ]
        
        for idx, scenario in enumerate(alert_scenarios, start=1):
            username = f"alert_test_{scenario['label'].lower()}"
            barangay = scenario['barangay']
            base_lat, base_lng = NAIC_BARANGAY_COORDS.get(barangay, (14.3, 120.8))
            
            if User.query.filter_by(username=username).first():
                user = User.query.filter_by(username=username).first()
            else:
                user = User(
                    username=username,
                    full_name=f"Alert Farmer ({scenario['label']} - {barangay})",
                    password_hash=generate_password_hash("password123"),
                    municipality="Naic",
                    street_barangay=barangay,
                    role="farmer",
                    latitude=base_lat + random.uniform(-0.001, 0.001),
                    longitude=base_lng + random.uniform(-0.001, 0.001)
                )
                db.session.add(user)
                db.session.commit()
            
            # Add pest records dated NOW so they count toward today's threshold
            for j in range(scenario['pest_count']):
                insect = random.choice(INSECTS)
                record = DetectionRecord(
                    user_id=user.id,
                    insect_name=insect,
                    confidence=random.uniform(0.75, 0.98),
                    image_file="placeholder.jpg",
                    timestamp=ph_time_now() - timedelta(minutes=random.randint(0, 60))
                )
                db.session.add(record)
            
            db.session.commit()
            
            # Trigger threshold check — this will fire the corresponding alert level
            check_infestation_threshold(user.id, user.municipality, is_test=False)
            print(f"  [ALERT SEED] {scenario['label']} alert farmer created: {user.full_name} ({scenario['pest_count']} pests)")

        print("Seeding complete!")

if __name__ == "__main__":
    seed_data()
