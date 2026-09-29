from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User, UserRole, Teacher


USERS = [
    {
        "username": "meifaadmin",
        "email": "devmeifa@gmail.com",
        "password": "MeiFaDev@123",
        "full_name": "Administrator",
        "role": UserRole.ADMIN,
    },
    {
        "username": "gurumeifa",
        "email": "gurumeifa@testing.com",
        "password": "Password@123",
        "full_name": "Guru Demo",
        "role": UserRole.GURU,
    },
]


def seed_users():
    db = SessionLocal()

    try:
        for data in USERS:
            existing_user = db.scalar(
                select(User).where(
                    User.username == data["username"]
                )
            )

            if existing_user:
                print(
                    f"User '{data['username']}' "
                    "already exists."
                )
                continue

            user = User(
                username=data["username"],
                email=data["email"],
                password_hash=hash_password(
                    data["password"]
                ),
                full_name=data["full_name"],
                role=data["role"],
                is_active=True,
            )

            db.add(user)

            db.flush()

            if user.role == UserRole.GURU:
                teacher = Teacher(user_id=user.id)
                db.add(teacher)

            print(
                f"Created user: {data['username']}"
            )

        db.commit()

    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
