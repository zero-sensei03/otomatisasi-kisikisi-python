from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_database,
    require_roles,
)
from app.models.user import User, UserRole
from app.schemas.audit_log import AuditLogFilter
from app.services.audit_service import AuditService


router = APIRouter(
    prefix="/audit-logs",
    tags=["Admin Audit Logs"],
)


templates = Jinja2Templates(
    directory="app/templates"
)


# ============================================================
# AUTHORIZATION
# ============================================================

admin_required = Depends(
    require_roles(UserRole.ADMIN)
)


# ============================================================
# DATE HELPER
# ============================================================

def parse_date(
    value: str | None,
    *,
    end_of_day: bool = False,
) -> datetime.datetime | None:
    """
    Parse tanggal dari input HTML <input type="date">.

    Contoh:
        2026-09-30
        ->
        2026-09-30 00:00:00

    Untuk end_at:
        2026-09-30
        ->
        2026-09-30 23:59:59.999999
    """

    if not value:
        return None

    try:
        date_value = datetime.date.fromisoformat(value)
    except ValueError:
        return None

    if end_of_day:
        return datetime.datetime.combine(
            date_value,
            datetime.time.max,
        )

    return datetime.datetime.combine(
        date_value,
        datetime.time.min,
    )


# ============================================================
# FILTER DEPENDENCY
# ============================================================

def get_audit_log_filters(
    search: str | None = Query(None),
    full_name: str | None = Query(None),
    action: str | None = Query(None),
    feature: str | None = Query(None),
    resource: str | None = Query(None),
    start_at: str | None = Query(None),
    end_at: str | None = Query(None),
    page: int = Query(
        1,
        ge=1,
    ),
    per_page: int = Query(
        10,
        ge=1,
        le=100,
    ),
) -> AuditLogFilter:

    return AuditLogFilter(
        search=search or None,
        full_name=full_name or None,
        action=action or None,
        feature=feature or None,
        resource=resource or None,
        start_at=parse_date(start_at),
        end_at=parse_date(
            end_at,
            end_of_day=True,
        ),
        page=page,
        per_page=per_page,
    )


# ============================================================
# AUDIT LOG LIST
# ============================================================

@router.get(
    "",
    response_class=HTMLResponse,
)
def list_audit_logs(
    request: Request,

    filters: Annotated[
        AuditLogFilter,
        Depends(get_audit_log_filters),
    ],

    db: Session = Depends(get_database),

    # Hanya ADMIN
    current_user: User = admin_required,
):
    service = AuditService(db)

    paginated_data = service.get_all_logs(
        filters
    )

    return templates.TemplateResponse(
        request=request,
        name="pages/admin/audit_logs/index.html",
        context={
            "current_user": current_user,

            "logs": paginated_data.items,
            "total": paginated_data.total,
            "page": paginated_data.page,
            "per_page": paginated_data.per_page,
            "total_pages": paginated_data.total_pages,

            # Filter object
            "filters": filters,

            # Filter values
            "search": filters.search or "",
            "full_name": filters.full_name or "",
            "action": filters.action or "",
            "feature": filters.feature or "",
            "resource": filters.resource or "",

            # Date values untuk HTML input
            "start_at": (
                filters.start_at.strftime(
                    "%Y-%m-%d"
                )
                if filters.start_at
                else ""
            ),

            "end_at": (
                filters.end_at.strftime(
                    "%Y-%m-%d"
                )
                if filters.end_at
                else ""
            ),
        },
    )
