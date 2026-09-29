from pydantic import BaseModel, ConfigDict, Field


class SubjectCreate(BaseModel):
    code: str = Field(
        min_length=1,
        max_length=50,
    )
    name: str = Field(
        min_length=1,
        max_length=150,
    )
    description: str | None = None


class SubjectUpdate(BaseModel):
    code: str = Field(
        min_length=1,
        max_length=50,
    )
    name: str = Field(
        min_length=1,
        max_length=150,
    )
    description: str | None = None


class SubjectRead(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
    )