from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.user import User, UserRole


class UserRepository:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        user_id: uuid.UUID,
    ) -> User | None:
        return self.db.scalar(
            select(User)
            .options(
                selectinload(User.teacher)
            )
            .where(
                User.id == user_id
            )
        )

    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        return self.db.scalar(
            select(User)
            .options(
                selectinload(User.teacher)
            )
            .where(
                User.email == email.lower().strip()
            )
        )

    def find(
        self,
        *,
        user_id: uuid.UUID | None = None,
        email: str | None = None,
    ) -> User | None:
        query = (
            select(User)
            .options(
                selectinload(User.teacher)
            )
        )

        if user_id:
            query = query.where(
                User.id == user_id
            )

        if email:
            query = query.where(
                User.email == email.lower().strip()
            )

        return self.db.scalar(query)

    def query(
        self,
        *,
        search: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> Select:
        query = (
            select(User)
            .options(
                selectinload(User.teacher)
            )
        )

        if search:
            search_value = (
                f"%{search.strip().lower()}%"
            )

            query = query.where(
                (
                    func.lower(User.full_name).like(
                        search_value
                    )
                )
                | (
                    func.lower(User.email).like(
                        search_value
                    )
                )
            )

        if role:
            query = query.where(
                User.role == role
            )

        if is_active is not None:
            query = query.where(
                User.is_active == is_active
            )

        return query

    def get_by_filter(
        self,
        *,
        search: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> list[User]:
        query = (
            self.query(
                search=search,
                role=role,
                is_active=is_active,
            )
            .order_by(
                User.created_at.desc()
            )
        )

        return list(
            self.db.scalars(query).all()
        )

    def paginate(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        page = max(page, 1)
        per_page = min(
            max(per_page, 1),
            100,
        )

        base_query = self.query(
            search=search,
            role=role,
            is_active=is_active,
        )

        total = self.db.scalar(
            select(
                func.count()
            ).select_from(
                base_query.subquery()
            )
        ) or 0

        query = (
            base_query
            .order_by(
                User.created_at.desc()
            )
            .offset(
                (page - 1) * per_page
            )
            .limit(per_page)
        )

        users = list(
            self.db.scalars(query).all()
        )

        return users, total

    def create(
        self,
        user: User,
    ) -> User:
        self.db.add(user)
        self.db.flush()

        return user

    def update(
        self,
        user: User,
        values: dict[str, Any],
    ) -> User:
        for key, value in values.items():
            setattr(user, key, value)

        self.db.flush()

        return user

    def delete(
        self,
        user: User,
    ) -> None:
        self.db.delete(user)
        self.db.flush()

    def activate(
        self,
        user: User,
    ) -> User:
        user.is_active = True
        self.db.flush()

        return user

    def deactivate(
        self,
        user: User,
    ) -> User:
        user.is_active = False
        self.db.flush()

        return user

    def exists_email(
        self,
        email: str,
        *,
        exclude_user_id: uuid.UUID | None = None,
    ) -> bool:
        query = select(User.id).where(
            User.email == email.lower().strip()
        )

        if exclude_user_id:
            query = query.where(
                User.id != exclude_user_id
            )

        return (
            self.db.scalar(query)
            is not None
        )