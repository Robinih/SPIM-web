import sys
from app import app, db, User
from werkzeug.security import generate_password_hash

def create_admin(username, password, full_name="Admin User", role="admin"):
    with app.app_context():
        # Check if exists
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"User '{username}' already exists.")
            if user.role != role:
                confirm = input(f"User exists as '{user.role}'. Promote to {role}? (y/n): ")
                if confirm.lower() == 'y':
                    user.role = role
                    db.session.commit()
                    print(f"User '{username}' promoted to {role}.")
            else:
                print(f"User is already a {role}.")
            return

        # Create new
        hashed_pw = generate_password_hash(password)
        new_admin = User(
            username=username,
            full_name=full_name,
            password_hash=hashed_pw,
            municipality='HEADQUARTERS',
            street_barangay='N/A',
            role=role
        )
        db.session.add(new_admin)
        db.session.commit()
        print(f"{role.capitalize()} user '{username}' created successfully.")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        role = "admin"
        if len(sys.argv) == 4:
            role = sys.argv[3]
        create_admin(sys.argv[1], sys.argv[2], role=role)
    else:
        print("Usage: python create_admin.py <username> <password> [role]")
        print("Interactive Mode:")
        u = input("Username: ")
        p = input("Password: ")
        r = input("Role (admin/developer) [default: admin]: ") or "admin"
        create_admin(u, p, role=r)
