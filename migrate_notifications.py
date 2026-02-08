"""
Migration script to add from_user_id column to Notification table
Run this ONCE to update your existing database
"""
from app import app, db

def migrate_notification_table():
    with app.app_context():
        try:
            # Check if column already exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('notification')]
            
            if 'from_user_id' in columns:
                print("✓ Column 'from_user_id' already exists. No migration needed.")
                return
            
            print("Adding 'from_user_id' column to notification table...")
            
            # Add the column
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE notification ADD COLUMN from_user_id INTEGER'))
                conn.commit()
            
            print("✓ Migration complete! Column 'from_user_id' added successfully.")
            print("  Note: Existing notifications will have from_user_id = NULL (manual/legacy alerts)")
            
        except Exception as e:
            print(f"✗ Migration failed: {e}")
            print("  If you get 'duplicate column' error, the migration already ran.")

if __name__ == "__main__":
    migrate_notification_table()
