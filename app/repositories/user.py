from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models import User, UserRole


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        search: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
    ) -> list[User]:
        statement = select(User)

        # 1. Filter Pencarian Teks (Cari berdasarkan nama, email, atau username)
        if search:
            search_fmt = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    User.full_name.ilike(search_fmt),
                    User.email.ilike(search_fmt),
                    User.username.ilike(search_fmt),
                )
            )

        # 2. Filter Berdasarkan Role (ADMIN / GURU)
        if role is not None:
            statement = statement.where(User.role == role)

        # 3. Filter Berdasarkan Status Aktif (is_active: True / False)
        if is_active is not None:
            statement = statement.where(User.is_active == is_active)

        # Urutkan dari ID terbaru
        statement = statement.order_by(User.id.desc())

        return list(self.db.scalars(statement).all())

    def get_by_id(
        self,
        user_id: int,
    ) -> User | None:
        return self.db.get(
            User,
            user_id,
        )

    def get_by_username(
        self,
        username: str,
    ) -> User | None:
        statement = select(User).where(
            User.username == username
        )

        return self.db.scalar(statement)

    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        statement = select(User).where(
            User.email == email
        )

        return self.db.scalar(statement)

    def create(
        self,
        user: User,
    ) -> User:
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)

        return user

    def delete(
        self,
        user: User,
    ) -> None:
        self.db.delete(user)
