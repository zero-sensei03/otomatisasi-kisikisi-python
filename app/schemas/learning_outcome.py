from pydantic import BaseModel, ConfigDict, Field


class LearningOutcomeCreate(BaseModel):
    subject_id: int
    code: str = Field(
        min_length=1,
        max_length=50,
    )
    description: str = Field(
        min_length=1,
    )


class LearningOutcomeUpdate(BaseModel):
    subject_id: int
    code: str = Field(
        min_length=1,
        max_length=50,
    )
    description: str = Field(
        min_length=1,
    )


class LearningOutcomeRead(BaseModel):
    id: int
    subject_id: int
    code: str
    description: str
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
    )