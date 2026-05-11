import os
from app import app, db
from models import User, SystemConfig
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        # Create all tables if they don't exist
        db.create_all()
        print("Database tables ensured.")

        # Create Admin
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                full_name='System Admin',
                password_hash=generate_password_hash('admin123'),
                role='admin',
                municipality='Naic',
                street_barangay='Poblacion'
            )
            db.session.add(admin)
            print("Admin account created: admin / admin123")

        # Create Developer
        dev = User.query.filter_by(username='dev').first()
        if not dev:
            dev = User(
                username='dev',
                full_name='System Developer',
                password_hash=generate_password_hash('dev123'),
                role='developer',
                municipality='Naic',
                street_barangay='Poblacion'
            )
            db.session.add(dev)
            print("Developer account created: dev / dev123")

        # Initialize default config if empty
        if SystemConfig.query.count() == 0:
            configs = [
                SystemConfig(key='threshold_low', value='1'),
                SystemConfig(key='threshold_medium', value='6'),
                SystemConfig(key='threshold_high', value='16')
            ]
            for c in configs:
                db.session.add(c)
            print("Default system configurations seeded.")

        db.session.commit()
        print("Database initialization complete.")

if __name__ == '__main__':
    print("Running SPIM Management Script...")
    init_db()
