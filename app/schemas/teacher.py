from pydantic import BaseModel, ConfigDict


class TeacherCreate(BaseModel):
    user_id: int
    employee_number: str | None = None


class TeacherRead(BaseModel):
    id: int
    user_id: int
    employee_number: str | None

    model_config = ConfigDict(
        from_attributes=True,
    )
