from __future__ import annotations

import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.core.security import detect_device
from app.repositories.audit_repository import AuditLogRepository

from app.schemas.audit_log import (
    AuditLogFilter,
    AuditLogResponse,
    PaginatedResponse,
)

class AuditService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.repository = AuditLogRepository(db)

    def log(
        self,
        *,
        action: str,
        feature: str,
        user_id: uuid.UUID | None = None,
        resource: str | None = None,
        resource_id: str | None = None,
        description: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device: str | None = None,
    ) -> AuditLog:
        audit = AuditLog(
            user_id=user_id,
            action=action,
            feature=feature,
            resource=resource,
            resource_id=resource_id,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            device=device or detect_device(user_agent),
        )

        self.db.add(audit)
        self.db.flush()

        return audit

    def get_all_logs(
        self,
        filters: AuditLogFilter,
    ) -> PaginatedResponse[AuditLogResponse]:
        items, total = self.repository.get_all_paginated(filters)

        total_pages = math.ceil(total / filters.per_page) if total > 0 else 0

        # Transform SQLAlchemy Model -> Pydantic Response Schema
        log_responses = [AuditLogResponse.model_validate(log) for log in items]

        return PaginatedResponse[AuditLogResponse](
            items=log_responses,
            total=total,
            page=filters.page,
            per_page=filters.per_page,
            total_pages=total_pages,
        )

    def get_log_by_id(self, log_id: uuid.UUID) -> AuditLogResponse:
        log = self.repository.get_by_id(log_id)
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audit log dengan ID '{log_id}' tidak ditemukan",
            )
        return AuditLogResponse.model_validate(log)