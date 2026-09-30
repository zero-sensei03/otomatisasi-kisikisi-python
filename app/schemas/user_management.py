from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import UserRole


class UserCreateSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)
    role: UserRole
    is_active: bool = True
    nip: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_password(self) -> "UserCreateSchema":
        if self.password != self.password_confirmation:
            raise ValueError("Password dan konfirmasi password tidak sama.")

        return self

    @model_validator(mode="after")
    def validate_teacher_data(self) -> "UserCreateSchema":
        if self.role == UserRole.GURU:
            if not self.nip:
                raise ValueError("NIP wajib diisi untuk role GURU.")
        else:
            self.nip = None

        return self


class UserUpdateSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    role: UserRole
    is_active: bool
    nip: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_teacher_data(self) -> "UserUpdateSchema":
        if self.role == UserRole.GURU:
            if not self.nip:
                raise ValueError("NIP wajib diisi untuk role GURU.")
        else:
            self.nip = None

        return self


class UserPasswordUpdateSchema(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(
        min_length=8,
        max_length=128,
    )

    @model_validator(mode="after")
    def validate_password(self) -> "UserPasswordUpdateSchema":
        if self.password != self.password_confirmation:
            raise ValueError("Password dan konfirmasi password tidak sama.")

        return self


class UserListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    nip: str | None = None


class UserPaginationSchema(BaseModel):
    items: list[UserListItemSchema]
    page: int
    per_page: int
    total: int
    total_pages: int


class UserManagementResponse(BaseModel):
    message: str
    user: UserListItemSchema