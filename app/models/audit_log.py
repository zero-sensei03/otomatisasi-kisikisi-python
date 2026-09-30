from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

from app.models.base import (
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    feature: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    resource: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    device: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="audit_logs",
    )