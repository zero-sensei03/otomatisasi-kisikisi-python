from __future__ import annotations

import uuid
from typing import Sequence
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, Session

from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogFilter


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_all_paginated(
        self,
        filters: AuditLogFilter,
    ) -> tuple[Sequence[AuditLog], int]:
        """
        Mengambil daftar AuditLog dengan filter dan paginasi.
        Mengembalikan tuple: (items, total_count).
        """
        # Base query dengan outerjoin agar log tanpa user (misal user terhapus/system) tetap terbaca
        stmt = (
            select(AuditLog)
            .outerjoin(AuditLog.user)
            .options(joinedload(AuditLog.user))
        )
        
        # Query untuk menghitung total baris
        count_stmt = select(func.count(AuditLog.id)).outerjoin(AuditLog.user)

        conditions = []

        # 1. Generic Search (mencari di action, feature, resource, description, atau nama/email user)
        if filters.search:
            search_pattern = f"%{filters.search}%"
            conditions.append(
                or_(
                    AuditLog.action.ilike(search_pattern),
                    AuditLog.feature.ilike(search_pattern),
                    AuditLog.resource.ilike(search_pattern),
                    AuditLog.description.ilike(search_pattern),
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                )
            )

        # 2. Filter spesifik full_name
        if filters.full_name:
            conditions.append(User.full_name.ilike(f"%{filters.full_name}%"))

        # 3. Filter spesifik action
        if filters.action:
            conditions.append(AuditLog.action.ilike(filters.action))

        # 4. Filter spesifik feature
        if filters.feature:
            conditions.append(AuditLog.feature.ilike(filters.feature))

        # 5. Filter spesifik resource
        if filters.resource:
            conditions.append(AuditLog.resource.ilike(filters.resource))

        # 6. Filter rentang waktu (TimestampMixin asumsi menggunakan created_at)
        if filters.start_at:
            conditions.append(AuditLog.created_at >= filters.start_at)

        if filters.end_at:
            conditions.append(AuditLog.created_at <= filters.end_at)

        # Terapkan kondisi jika ada
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        # Hitung total items
        total_result = self.session.execute(count_stmt)
        total = total_result.scalar_one_or_none() or 0

        # Paginasi & Urutkan dari yang terbaru
        offset = (filters.page - 1) * filters.per_page
        stmt = (
            stmt.order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(filters.per_page)
        )

        result = self.session.execute(stmt)
        items = result.scalars().all()

        return items, total

    def get_by_id(self, log_id: uuid.UUID) -> AuditLog | None:
        """
        Mengambil detail satu AuditLog berdasarkan ID (lengkap dengan data user).
        """
        stmt = (
            select(AuditLog)
            .options(joinedload(AuditLog.user))
            .where(AuditLog.id == log_id)
        )
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()