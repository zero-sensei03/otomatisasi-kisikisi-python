from pydantic import BaseModel, ConfigDict, Field


class ClassRoomCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )
    grade_level: str = Field(
        min_length=1,
        max_length=50,
    )
    description: str | None = None


class ClassRoomUpdate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )
    grade_level: str = Field(
        min_length=1,
        max_length=50,
    )
    description: str | None = None


class ClassRoomRead(BaseModel):
    id: int
    name: str
    grade_level: str
    description: str | None
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
    )