from __future__ import annotations

import datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    detect_device,
    generate_csrf_token,
    generate_token,
    hash_csrf_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.models.user_session import UserSession
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginSchema,
    PasswordChangeSchema,
    RegisterSchema,
    UserUpdateSchema,
)
from app.services.audit_service import AuditService


class AuthService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.settings = get_settings()
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    def register(
        self,
        data: RegisterSchema,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        email = data.email.lower().strip()

        if self.users.exists_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email sudah terdaftar.",
            )

        if (
            data.password
            != data.password_confirmation
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Konfirmasi password tidak cocok.",
            )

        user = User(
            email=email,
            full_name=data.full_name.strip(),
            password_hash=hash_password(
                data.password
            ),
            role=UserRole.GURU,
            is_active=True,
        )

        self.users.create(user)

        teacher = Teacher(
            user_id=user.id,
            nip=(
                data.nip.strip()
                if data.nip
                else None
            ),
        )

        self.db.add(teacher)

        self.audit.log(
            action="REGISTER",
            feature="AUTHENTICATION",
            user_id=user.id,
            resource="USER",
            resource_id=str(user.id),
            description=(
                "Guru membuat akun baru."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.commit()
        self.db.refresh(user)

        return user

    def login(
        self,
        data: LoginSchema,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        email = data.email.lower().strip()

        user = self.users.get_by_email(email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email atau password salah.",
            )

        if not verify_password(
            data.password,
            user.password_hash,
        ):
            self.audit.log(
                action="LOGIN_FAILED",
                feature="AUTHENTICATION",
                resource="USER",
                resource_id=str(user.id),
                description=(
                    "Login gagal karena "
                    "password tidak valid."
                ),
                ip_address=ip_address,
                user_agent=user_agent,
            )

            self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email atau password salah.",
            )

        if not user.is_active:
            self.audit.log(
                action="LOGIN_FAILED",
                feature="AUTHENTICATION",
                user_id=user.id,
                resource="USER",
                resource_id=str(user.id),
                description=(
                    "Login ditolak karena "
                    "akun tidak aktif."
                ),
                ip_address=ip_address,
                user_agent=user_agent,
            )

            self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun tidak aktif.",
            )

        session_token = generate_token()
        csrf_token = generate_csrf_token()

        expires_at = (
            datetime.datetime.now(
                datetime.timezone.utc
            )
            + datetime.timedelta(
                seconds=self.settings.session_max_age
            )
        )

        session = UserSession(
            user_id=user.id,
            token_hash=hash_token(
                session_token
            ),
            csrf_token_hash=hash_csrf_token(
                csrf_token
            ),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            device=detect_device(
                user_agent
            ),
        )

        self.db.add(session)

        self.audit.log(
            action="LOGIN",
            feature="AUTHENTICATION",
            user_id=user.id,
            resource="USER_SESSION",
            resource_id=str(session.id),
            description=(
                "User berhasil login."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
            device=detect_device(
                user_agent
            ),
        )

        self.db.commit()

        return (
            user,
            session_token,
            csrf_token,
        )

    def logout(
        self,
        session: UserSession,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if session.revoked_at:
            return

        session.revoked_at = (
            datetime.datetime.now(
                datetime.timezone.utc
            )
        )

        self.audit.log(
            action="LOGOUT",
            feature="AUTHENTICATION",
            user_id=session.user_id,
            resource="USER_SESSION",
            resource_id=str(session.id),
            description=(
                "User melakukan logout."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
            device=detect_device(
                user_agent
            ),
        )

        self.db.commit()

    def get_valid_session(
        self,
        session_token: str,
    ) -> UserSession | None:
        session = self.db.scalar(
            select(UserSession)
            .where(
                UserSession.token_hash
                == hash_token(session_token)
            )
        )

        if not session:
            return None

        now = (
            datetime.datetime.now(
                datetime.timezone.utc
            )
        )

        if session.revoked_at:
            return None

        if session.expires_at <= now:
            return None

        if not session.user:
            return None

        return session

    def me(
        self,
        user: User,
    ) -> User:
        return user

    def update_profile(
        self,
        user: User,
        data: UserUpdateSchema,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        values = data.model_dump(
            exclude_unset=True
        )

        email = values.get("email")

        if email:
            email = email.lower().strip()

            if self.users.exists_email(
                email,
                exclude_user_id=user.id,
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Email sudah digunakan.",
                )

            values["email"] = email

        self.users.update(
            user,
            values,
        )

        self.audit.log(
            action="UPDATE_PROFILE",
            feature="AUTHENTICATION",
            user_id=user.id,
            resource="USER",
            resource_id=str(user.id),
            description=(
                "User memperbarui profil."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.commit()
        self.db.refresh(user)

        return user

    def change_password(
        self,
        user: User,
        data: PasswordChangeSchema,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if not verify_password(
            data.current_password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=422,
                detail="Password lama salah.",
            )

        if (
            data.new_password
            != data.new_password_confirmation
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Konfirmasi password baru "
                    "tidak cocok."
                ),
            )

        user.password_hash = hash_password(
            data.new_password
        )

        self.db.query(UserSession).filter(
            UserSession.user_id == user.id
        ).update(
            {
                UserSession.revoked_at: (
                    datetime.datetime.now(
                        datetime.timezone.utc
                    )
                )
            },
            synchronize_session=False,
        )

        self.audit.log(
            action="CHANGE_PASSWORD",
            feature="AUTHENTICATION",
            user_id=user.id,
            resource="USER",
            resource_id=str(user.id),
            description=(
                "User mengganti password."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.commit()

    def revoke_all_sessions(
        self,
        user: User,
    ) -> None:
        self.db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        ).update(
            {
                UserSession.revoked_at: (
                    datetime.datetime.now(
                        datetime.timezone.utc
                    )
                )
            },
            synchronize_session=False,
        )

        self.db.commit()