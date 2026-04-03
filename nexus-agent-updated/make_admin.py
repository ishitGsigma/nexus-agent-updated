"""
Run this once to create or promote a user to admin.
Usage:
    python make_admin.py                        # creates admin@nexus.ai / admin123
    python make_admin.py your@email.com         # promotes existing user to admin
    python make_admin.py your@email.com mypass  # creates new admin with custom password
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from app import app
from database import db, User

def make_admin(email=None, password=None):
    with app.app_context():
        db.create_all()

        email = email or "admin@nexus.ai"
        password = password or "admin123"

        user = User.query.filter_by(email=email).first()

        if user:
            # Promote existing user
            user.is_admin = True
            user.plan = 'enterprise'
            db.session.commit()
            print(f"✅ Promoted existing user '{user.username}' ({email}) to ADMIN")
        else:
            # Create brand new admin user
            username = email.split('@')[0].replace('.', '_')
            # Make sure username is unique
            base = username
            i = 1
            while User.query.filter_by(username=username).first():
                username = f"{base}{i}"
                i += 1

            user = User(
                email=email,
                username=username,
                is_admin=True,
                plan='enterprise'
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            print(f"✅ Created new ADMIN account:")
            print(f"   Email    : {email}")
            print(f"   Username : {username}")
            print(f"   Password : {password}")

        print(f"   is_admin : {user.is_admin}")
        print(f"   Daily limit: UNLIMITED ∞")

if __name__ == '__main__':
    args = sys.argv[1:]
    make_admin(
        email=args[0] if len(args) > 0 else None,
        password=args[1] if len(args) > 1 else None
    )
