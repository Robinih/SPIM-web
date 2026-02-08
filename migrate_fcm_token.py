"""
Migration script to add fcm_token field to User table for Firebase Cloud Messaging
Run this script once to update your database schema.
"""
from app import app, db
from models import User

with app.app_context():
    # Add fcm_token column to existing User table
    with db.engine.connect() as conn:
        try:
            # Check if column already exists
            result = conn.execute(db.text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result]
            
            if 'fcm_token' not in columns:
                conn.execute(db.text("ALTER TABLE user ADD COLUMN fcm_token VARCHAR(255)"))
                conn.commit()
                print("[OK] Successfully added fcm_token column to user table")
            else:
                print("[OK] fcm_token column already exists")
        except Exception as e:
            print(f"Error during migration: {e}")
            print("If you see 'duplicate column name', the migration was already run.")
