from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.cognitive_levels import ACTIVE_COGNITIVE_LEVELS
from app.integrations.ai.schemas import AIGenerationRequest, AIGenerationResponse


class GenerationCreateSchema(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    subject: str = Field(min_length=1, max_length=150)
    class_name: str = Field(min_length=1, max_length=100)
    type_materi: Literal["TEXT", "FILE"]
    materi_text: str | None = None
    references: list[str] = Field(default_factory=list)
    cognitive_levels: list[str] = Field(default_factory=lambda: list(ACTIVE_COGNITIVE_LEVELS), min_length=1)
    total_multiple_choice: int = Field(default=0, ge=0)
    total_short_answer: int = Field(default=0, ge=0)
    total_essay: int = Field(default=0, ge=0)

    @field_validator("cognitive_levels")
    @classmethod
    def validate_cognitive_levels(cls, values):
        invalid = sorted(set(values) - set(ACTIVE_COGNITIVE_LEVELS))
        if invalid:
            raise ValueError(f"Level kognitif {', '.join(invalid)} belum tersedia. Pilih C1 sampai C4.")
        return list(dict.fromkeys(values))
    @model_validator(mode="after")
    def validate_material_and_questions(self):
        if self.type_materi == "TEXT" and not (self.materi_text or "").strip():
            raise ValueError("Materi teks wajib diisi.")
        if self.total_multiple_choice + self.total_short_answer + self.total_essay < 1:
            raise ValueError("Minimal satu jenis soal harus diminta.")
        return self


class GenerationSettingsSchema(BaseModel):
    generation_free_limit: int = Field(gt=0, le=1_000_000)
    generation_cost_per_generate: float = Field(ge=0, le=1_000_000)
    generation_enabled: Literal["true", "false"] = "false"
    generation_max_questions_per_generate: int = Field(gt=0, le=500)
    generation_max_material_characters: int = Field(gt=0, le=1_000_000_000)
    generation_max_reference_characters: int = Field(gt=0, le=250_000)

class GenerationReferenceSchema(BaseModel):
    url: str
    title: str | None = None
    extracted_content: str | None = None
    extraction_status: str
    error_message: str | None = None

class GenerationOptionSchema(BaseModel):
    label: str
    text: str
    is_correct: bool

class GenerationQuestionSchema(BaseModel):
    number: int
    type: str
    cognitive_level: str
    question: str
    answer: str
    explanation: str
    options: list[GenerationOptionSchema] = []

class GenerationBlueprintSchema(BaseModel):
    number: int
    question_number: int
    material_topic: str
    learning_objective: str
    indicator: str
    question_type: str
    cognitive_level: str
    difficulty: str

class GenerationListItemSchema(BaseModel):
    id: str
    parent_generation_id: str | None = None
    title: str
    subject: str
    class_name: str
    total_questions: int
    status: str
    ai_provider: str | None
    ai_model: str | None
    ai_duration_ms: int | None = None
    created_at: str

class GenerationDetailSchema(GenerationListItemSchema):
    summary: str | None
    questions: list[GenerationQuestionSchema]
    blueprints: list[GenerationBlueprintSchema]
    references: list[GenerationReferenceSchema]

__all__ = ["AIGenerationRequest", "AIGenerationResponse", "GenerationBlueprintSchema", "GenerationCreateSchema", "GenerationDetailSchema", "GenerationListItemSchema", "GenerationOptionSchema", "GenerationQuestionSchema", "GenerationReferenceSchema", "GenerationSettingsSchema"]
