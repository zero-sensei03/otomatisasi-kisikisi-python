from __future__ import annotations

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole


def main() -> None:
    settings = get_settings()

    db = SessionLocal()

    try:
        email = settings.admin_email.lower().strip()

        existing = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing:
            print(
                f"Admin sudah tersedia: {existing.email}"
            )
            return

        admin = User(
            email=email,
            full_name=settings.admin_name,
            password_hash=hash_password(
                settings.admin_password
            ),
            role=UserRole.ADMIN,
            is_active=True,
        )

        db.add(admin)
        db.commit()

        print(
            f"Admin berhasil dibuat: {email}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()