from app import app, db, User

def fix_dev_name():
    with app.app_context():
        # Find the user 'dev'
        user = User.query.filter_by(username='dev').first()
        
        if user:
            print(f"Found user: {user.username} (Current Name: {user.full_name})")
            user.full_name = "Developer"
            db.session.commit()
            print("Successfully updated full_name to 'Developer'.")
        else:
            print("User 'dev' not found. Please edit this script if your username is different.")

if __name__ == "__main__":
    fix_dev_name()
