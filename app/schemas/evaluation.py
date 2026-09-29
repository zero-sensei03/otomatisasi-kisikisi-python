from pydantic import BaseModel, ConfigDict, Field

from app.models.evaluation import EvaluationStatus


class EvaluationCreate(BaseModel):
    teacher_id: int
    subject_id: int
    class_id: int

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str | None = None

    semester: str = Field(
        min_length=1,
        max_length=20,
    )

    academic_year: str = Field(
        min_length=1,
        max_length=20,
    )

    status: EvaluationStatus = EvaluationStatus.DRAFT


class EvaluationUpdate(BaseModel):
    subject_id: int
    class_id: int

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str | None = None

    semester: str = Field(
        min_length=1,
        max_length=20,
    )

    academic_year: str = Field(
        min_length=1,
        max_length=20,
    )

    status: EvaluationStatus


class EvaluationRead(BaseModel):
    id: int
    teacher_id: int
    subject_id: int
    class_id: int
    name: str
    description: str | None
    semester: str
    academic_year: str
    status: EvaluationStatus

    model_config = ConfigDict(
        from_attributes=True,
    )