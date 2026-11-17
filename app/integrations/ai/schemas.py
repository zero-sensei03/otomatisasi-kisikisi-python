from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.cognitive_levels import ACTIVE_COGNITIVE_LEVELS


class QuestionDistribution(BaseModel):
    multiple_choice: int = Field(ge=0)
    short_answer: int = Field(ge=0)
    essay: int = Field(ge=0)
    @model_validator(mode="after")
    def require_questions(self):
        if self.multiple_choice + self.short_answer + self.essay < 1:
            raise ValueError("Minimal satu jenis soal harus diminta.")
        return self

class AIGenerationRequest(BaseModel):
    title: str
    description: str = ""
    subject: str
    class_name: str
    material: str
    references: list[str] = Field(default_factory=list)
    cognitive_levels: list[str] = Field(default_factory=lambda: list(ACTIVE_COGNITIVE_LEVELS), min_length=1)
    question_distribution: QuestionDistribution

    @field_validator("cognitive_levels")
    @classmethod
    def validate_cognitive_levels(cls, values):
        invalid = sorted(set(values) - set(ACTIVE_COGNITIVE_LEVELS))
        if invalid:
            raise ValueError(f"Level kognitif {', '.join(invalid)} belum tersedia. Pilih C1 sampai C4.")
        return list(dict.fromkeys(values))

class QuestionOption(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str
    is_correct: bool

class GeneratedQuestion(BaseModel):
    number: int = Field(ge=1)
    type: Literal["MULTIPLE_CHOICE", "SHORT_ANSWER", "ESSAY"]
    cognitive_level: str
    question: str = Field(min_length=1)
    options: list[QuestionOption] = Field(default_factory=list)
    answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @field_validator("cognitive_level")
    @classmethod
    def validate_cognitive_level(cls, value):
        if value not in ACTIVE_COGNITIVE_LEVELS:
            raise ValueError("Level kognitif tidak tersedia. Gunakan C1 sampai C4.")
        return value

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value):
        if isinstance(value, str):
            normalized = value.strip().upper().replace(" ", "_").replace("-", "_")
            aliases = {"PILIHAN_GANDA": "MULTIPLE_CHOICE", "ISIAN": "SHORT_ANSWER", "ESAI": "ESSAY"}
            return aliases.get(normalized, normalized)
        return value

class GeneratedBlueprint(BaseModel):
    number: int = Field(ge=1)
    question_number: int = Field(ge=1)
    material_topic: str = Field(min_length=1)
    learning_objective: str = Field(min_length=1)
    indicator: str = Field(min_length=1)
    question_type: Literal["MULTIPLE_CHOICE", "SHORT_ANSWER", "ESSAY"]
    cognitive_level: str
    difficulty: Literal["EASY", "MEDIUM", "HARD"]

    @field_validator("cognitive_level")
    @classmethod
    def validate_cognitive_level(cls, value):
        if value not in ACTIVE_COGNITIVE_LEVELS:
            raise ValueError("Level kognitif tidak tersedia. Gunakan C1 sampai C4.")
        return value

    @field_validator("question_type", mode="before")
    @classmethod
    def normalize_question_type(cls, value):
        if isinstance(value, str):
            normalized = value.strip().upper().replace(" ", "_").replace("-", "_")
            aliases = {"PILIHAN_GANDA": "MULTIPLE_CHOICE", "ISIAN": "SHORT_ANSWER", "ESAI": "ESSAY"}
            return aliases.get(normalized, normalized)
        return value

class AIGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1)
    questions: list[GeneratedQuestion]
    blueprint: list[GeneratedBlueprint]
    @model_validator(mode="after")
    def validate_consistency(self):
        numbers = {q.number for q in self.questions}
        if len(numbers) != len(self.questions) or len(self.blueprint) != len(self.questions):
            raise ValueError("Nomor soal dan kisi-kisi harus unik serta berpasangan.")
        if numbers != set(range(1, len(self.questions) + 1)):
            raise ValueError("Nomor soal harus berurutan mulai dari 1.")
        if {b.question_number for b in self.blueprint} != numbers:
            raise ValueError("Setiap soal harus memiliki kisi-kisi.")
        if {b.number for b in self.blueprint} != set(range(1, len(self.blueprint) + 1)):
            raise ValueError("Nomor butir kisi-kisi harus unik dan berurutan.")
        for question in self.questions:
            blueprint = next(b for b in self.blueprint if b.question_number == question.number)
            if blueprint.question_type != question.type:
                raise ValueError("Jenis kisi-kisi tidak sesuai soal.")
            if blueprint.cognitive_level != question.cognitive_level:
                raise ValueError("Level kognitif soal dan kisi-kisi tidak sesuai.")
            if question.type == "MULTIPLE_CHOICE":
                if [o.label for o in question.options] != ["A", "B", "C", "D"]:
                    raise ValueError("Pilihan ganda harus memiliki opsi A-D.")
                correct = [o.label for o in question.options if o.is_correct]
                if len(correct) != 1 or question.answer != correct[0]:
                    raise ValueError("Pilihan ganda harus memiliki satu jawaban benar.")
            elif question.options:
                raise ValueError("Soal isian dan essay tidak memiliki opsi.")
        return self

AIRequest = AIGenerationRequest
AIResponse = AIGenerationResponse
