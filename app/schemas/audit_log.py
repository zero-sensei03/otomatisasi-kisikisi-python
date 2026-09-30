from __future__ import annotations

import datetime
import uuid
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


# --- Filter Request ---
class AuditLogFilter(BaseModel):
    search: Optional[str] = None
    full_name: Optional[str] = None
    action: Optional[str] = None
    feature: Optional[str] = None
    resource: Optional[str] = None
    start_at: Optional[datetime.datetime] = None
    end_at: Optional[datetime.datetime] = None

    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)


# --- Response Schemas ---
class UserInAuditLog(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    action: str
    feature: str
    resource: Optional[str]
    resource_id: Optional[str]
    description: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    device: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    user: Optional[UserInAuditLog] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    per_page: int
    total_pages: int