from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

from app.models.base import (
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.teacher import Teacher
    from app.models.user_session import UserSession


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    GURU = "GURU"


class User(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
        ),
        nullable=False,
        default=UserRole.GURU,
        server_default="GURU",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    teacher: Mapped["Teacher | None"] = relationship(
        "Teacher",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
    )