from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

from app.models.base import (
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.models.user import User


class Teacher(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "teachers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    nip: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="teacher",
    )