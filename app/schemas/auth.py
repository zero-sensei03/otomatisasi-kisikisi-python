from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class RegisterSchema(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=150,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    password_confirmation: str = Field(
        min_length=8,
        max_length=128,
    )

    nip: str | None = Field(
        default=None,
        max_length=50,
    )


class UserUpdateSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    email: EmailStr | None = None

    is_active: bool | None = None


class PasswordChangeSchema(BaseModel):
    current_password: str = Field(
        min_length=8,
        max_length=128,
    )

    new_password: str = Field(
        min_length=8,
        max_length=128,
    )

    new_password_confirmation: str = Field(
        min_length=8,
        max_length=128,
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class PaginatedUsersResponse(BaseModel):
    items: list[UserResponse]
    page: int
    per_page: int
    total: int
    total_pages: int