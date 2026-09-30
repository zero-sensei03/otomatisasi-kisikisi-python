from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
)
from app.core.security import hash_password
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user_management import (
    UserCreateSchema,
    UserPasswordUpdateSchema,
    UserUpdateSchema,
)
from app.services.audit_service import AuditService


class UserManagementService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    def list_users(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        return self.users.paginate(
            page=page,
            per_page=per_page,
            search=search,
            role=role,
            is_active=is_active,
        )

    def get_user(
        self,
        user_id: uuid.UUID,
    ) -> User:
        user = self.users.get(user_id)

        if not user:
            raise NotFoundException(
                "User tidak ditemukan."
            )

        return user

    def create_user(
        self,
        *,
        data: UserCreateSchema,
        admin_user: User,
        ip_address: str | None,
        user_agent: str | None,
        device: str | None,
    ) -> User:
        email = str(data.email).lower().strip()

        if self.users.exists_email(email):
            raise ValueError(
                "Email sudah digunakan."
            )

        user = User(
            email=email,
            full_name=data.full_name,
            password_hash=hash_password(
                data.password
            ),
            role=data.role,
            is_active=data.is_active,
        )

        self.users.create(user)

        if data.role == UserRole.GURU:
            teacher = Teacher(
                user_id=user.id,
                nip=data.nip,
            )

            self.db.add(teacher)
            self.db.flush()

        self.audit.log(
            user_id=admin_user.id,
            action="CREATE_USER",
            feature="USER_MANAGEMENT",
            resource="USER",
            resource_id=str(user.id),
            description=(
                f"Membuat user {user.email} "
                f"dengan role {user.role.value}."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
            device=device,
        )

        self.db.commit()

        return self.users.get(user.id)

    def update_user(
        self,
        *,
        user_id: uuid.UUID,
        data: UserUpdateSchema,
        admin_user: User,
        ip_address: str | None,
        user_agent: str | None,
        device: str | None,
    ) -> User:
        user = self.get_user(user_id)

        if user.id == admin_user.id:
            if not data.is_active:
                raise ForbiddenException(
                    "Admin tidak dapat menonaktifkan akun sendiri."
                )

            if data.role != UserRole.ADMIN:
                raise ForbiddenException(
                    "Admin tidak dapat mengubah role akun sendiri."
                )

        email = str(data.email).lower().strip()

        if self.users.exists_email(
            email,
            exclude_user_id=user.id,
        ):
            raise ValueError(
                "Email sudah digunakan oleh user lain."
            )

        old_role = user.role

        self.users.update(
            user,
            {
                "email": email,
                "full_name": data.full_name,
                "role": data.role,
                "is_active": data.is_active,
            },
        )

        if data.role == UserRole.GURU:
            if user.teacher:
                user.teacher.nip = data.nip
            else:
                teacher = Teacher(
                    user_id=user.id,
                    nip=data.nip,
                )
                self.db.add(teacher)

        elif user.teacher:
            self.db.delete(user.teacher)

        self.db.flush()

        self.audit.log(
            user_id=admin_user.id,
            action="UPDATE_USER",
            feature="USER_MANAGEMENT",
            resource="USER",
            resource_id=str(user.id),
            description=(
                f"Mengubah user {user.email}. "
                f"Role sebelumnya: {old_role.value}, "
                f"role sekarang: {user.role.value}."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
            device=device,
        )

        self.db.commit()

        return self.users.get(user.id)

    def update_password(
        self,
        *,
        user_id: uuid.UUID,
        data: UserPasswordUpdateSchema,
        admin_user: User,
        ip_address: str | None,
        user_agent: str | None,
        device: str | None,
    ) -> User:
        user = self.get_user(user_id)

        user.password_hash = hash_password(
            data.password
        )

        self.db.flush()

        self.audit.log(
            user_id=admin_user.id,
            action="RESET_USER_PASSWORD",
            feature="USER_MANAGEMENT",
            resource="USER",
            resource_id=str(user.id),
            description=(
                f"Password user {user.email} "
                "diubah oleh administrator."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
            device=device,
        )

        self.db.commit()

        return self.users.get(user.id)

    def set_status(
        self,
        *,
        user_id: uuid.UUID,
        is_active: bool,
        admin_user: User,
        ip_address: str | None,
        user_agent: str | None,
        device: str | None,
    ) -> User:
        user = self.get_user(user_id)

        if user.id == admin_user.id and not is_active:
            raise ForbiddenException(
                "Admin tidak dapat menonaktifkan akun sendiri."
            )

        if is_active:
            self.users.activate(user)
            action = "ACTIVATE_USER"
            description = (
                f"Mengaktifkan user {user.email}."
            )
        else:
            self.users.deactivate(user)
            action = "DEACTIVATE_USER"
            description = (
                f"Menonaktifkan user {user.email}."
            )

        self.audit.log(
            user_id=admin_user.id,
            action=action,
            feature="USER_MANAGEMENT",
            resource="USER",
            resource_id=str(user.id),
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            device=device,
        )

        self.db.commit()

        return self.users.get(user.id)

    def delete_user(
        self,
        *,
        user_id: uuid.UUID,
        admin_user: User,
        ip_address: str | None,
        user_agent: str | None,
        device: str | None,
    ) -> None:
        user = self.get_user(user_id)

        if user.id == admin_user.id:
            raise ForbiddenException(
                "Admin tidak dapat menghapus akun sendiri."
            )

        email = user.email

        self.audit.log(
            user_id=admin_user.id,
            action="DELETE_USER",
            feature="USER_MANAGEMENT",
            resource="USER",
            resource_id=str(user.id),
            description=(
                f"Menghapus user {email}."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
            device=device,
        )

        self.users.delete(user)
        self.db.commit()