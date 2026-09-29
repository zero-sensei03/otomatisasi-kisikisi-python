from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
    )
