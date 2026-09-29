from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import User


def authenticate_user(
    db: Session,
    username_or_email: str,
    password: str,
) -> User | None:
    statement = select(User).where(
        or_(
            User.username == username_or_email,
            User.email == username_or_email,
        )
    )

    user = db.scalar(statement)

    if not user:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    return user
