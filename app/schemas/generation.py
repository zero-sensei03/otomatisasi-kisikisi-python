from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from app.integrations.ai.schemas import AIGenerationRequest, AIGenerationResponse

class GenerationCreateSchema(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    subject: str = Field(min_length=1, max_length=150)
    class_name: str = Field(min_length=1, max_length=100)
    type_materi: Literal["TEXT", "FILE"]
    materi_text: str | None = None
    references: list[str] = Field(default_factory=list)
    total_multiple_choice: int = Field(default=0, ge=0)
    total_short_answer: int = Field(default=0, ge=0)
    total_essay: int = Field(default=0, ge=0)
    @model_validator(mode="after")
    def validate_material_and_questions(self):
        if self.type_materi == "TEXT" and not (self.materi_text or "").strip():
            raise ValueError("Materi teks wajib diisi.")
        if self.total_multiple_choice + self.total_short_answer + self.total_essay < 1:
            raise ValueError("Minimal satu jenis soal harus diminta.")
        return self

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
    title: str
    subject: str
    class_name: str
    total_questions: int
    status: str
    ai_provider: str | None
    ai_model: str | None
    created_at: str

class GenerationDetailSchema(GenerationListItemSchema):
    summary: str | None
    questions: list[GenerationQuestionSchema]
    blueprints: list[GenerationBlueprintSchema]
    references: list[GenerationReferenceSchema]

__all__ = ["GenerationCreateSchema", "GenerationReferenceSchema", "GenerationQuestionSchema", "GenerationOptionSchema", "GenerationBlueprintSchema", "GenerationListItemSchema", "GenerationDetailSchema", "AIGenerationRequest", "AIGenerationResponse"]
