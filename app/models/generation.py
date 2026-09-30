from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class MaterialType(str, enum.Enum):
    TEXT = "TEXT"
    FILE = "FILE"

class GenerationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class GenerationQuestionType(str, enum.Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    SHORT_ANSWER = "SHORT_ANSWER"
    ESSAY = "ESSAY"

class Generation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generations"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(150), nullable=False)
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    type_materi: Mapped[MaterialType] = mapped_column(Enum(MaterialType, name="generation_material_type"), nullable=False)
    material_text: Mapped[str] = mapped_column(Text, nullable=False)
    material_file_name: Mapped[str | None] = mapped_column(String(255))
    material_file_path: Mapped[str | None] = mapped_column(String(512))
    material_file_mime_type: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[GenerationStatus] = mapped_column(Enum(GenerationStatus, name="generation_status"), default=GenerationStatus.PENDING, nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    total_multiple_choice: Mapped[int] = mapped_column(Integer, nullable=False)
    total_short_answer: Mapped[int] = mapped_column(Integer, nullable=False)
    total_essay: Mapped[int] = mapped_column(Integer, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_provider: Mapped[str | None] = mapped_column(String(50))
    ai_model: Mapped[str | None] = mapped_column(String(150))
    generation_cost: Mapped[float] = mapped_column(Numeric(12, 4), default=0, nullable=False)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    questions: Mapped[list[GenerationQuestion]] = relationship(back_populates="generation", cascade="all, delete-orphan", order_by="GenerationQuestion.number")
    references: Mapped[list[GenerationReference]] = relationship(back_populates="generation", cascade="all, delete-orphan")
    blueprints: Mapped[list[GenerationBlueprint]] = relationship(back_populates="generation", cascade="all, delete-orphan")

class GenerationReference(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "generation_references"
    generation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    extracted_content: Mapped[str | None] = mapped_column(Text)
    extraction_status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    generation: Mapped[Generation] = relationship(back_populates="references")

class GenerationQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_questions"
    __table_args__ = (UniqueConstraint("generation_id", "number", name="uq_generation_question_number"),)
    generation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[GenerationQuestionType] = mapped_column(Enum(GenerationQuestionType, name="generation_question_type"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    generation: Mapped[Generation] = relationship(back_populates="questions")
    options: Mapped[list[GenerationQuestionOption]] = relationship(back_populates="question_record", cascade="all, delete-orphan", order_by="GenerationQuestionOption.label")

class GenerationQuestionOption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "generation_question_options"
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(1), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    question_record: Mapped[GenerationQuestion] = relationship(back_populates="options")

class GenerationBlueprint(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "generation_blueprints"
    __table_args__ = (UniqueConstraint("generation_id", "number", name="uq_generation_blueprint_number"),)
    generation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_questions.id", ondelete="CASCADE"), nullable=False, unique=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_topic: Mapped[str] = mapped_column(Text, nullable=False)
    learning_objective: Mapped[str] = mapped_column(Text, nullable=False)
    indicator: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[GenerationQuestionType] = mapped_column(Enum(GenerationQuestionType, name="generation_question_type"), nullable=False)
    cognitive_level: Mapped[str] = mapped_column(String(2), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False)
    generation: Mapped[Generation] = relationship(back_populates="blueprints")

class GenerationUsage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "generation_usage"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, unique=True)
    free_generation_used: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cost: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class GenerationSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_settings"
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
