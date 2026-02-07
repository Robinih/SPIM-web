from app import app, db

def init_db():
    print("Creating database tables...")
    with app.app_context():
        db.create_all()
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db()
