from __future__ import annotations

import math
import uuid

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Query,
    Request,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_database,
    require_csrf,
    require_roles,
)
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
)
from app.core.security import (
    detect_device,
    generate_csrf_token,
    sign_csrf_token,
)
from app.models.user import User, UserRole
from app.schemas.user_management import (
    UserCreateSchema,
    UserPasswordUpdateSchema,
    UserUpdateSchema,
)
from app.services.user_management_service import (
    UserManagementService,
)


router = APIRouter(
    prefix="/users",
    tags=["Admin User Management"],
)


templates = Jinja2Templates(
    directory="app/templates"
)


admin_required = Depends(
    require_roles(UserRole.ADMIN)
)


def get_request_ip(
    request: Request,
) -> str | None:
    if request.client:
        return request.client.host

    return None


def get_user_agent(
    request: Request,
) -> str | None:
    return request.headers.get(
        "user-agent"
    )


def csrf_context() -> dict[str, str]:
    """
    Membuat CSRF token dan signature.

    Mekanisme ini sama dengan yang digunakan
    oleh halaman authentication.
    """

    token = generate_csrf_token()

    return {
        "csrf_token": token,
        "csrf_signature": sign_csrf_token(
            token
        ),
    }


def render_user_page(
    request: Request,
    *,
    current_user: User,
    users: list[User],
    total: int,
    page: int,
    per_page: int,
    search: str | None,
    role: str | None,
    status: str | None,
    csrf_token: str,
    csrf_signature: str,
    error: str | None = None,
    success: str | None = None,
):
    total_pages = (
        math.ceil(total / per_page)
        if total
        else 1
    )

    if page > total_pages:
        page = total_pages

    return templates.TemplateResponse(
        request=request,
        name="pages/admin/users/index.html",
        context={
            "current_user": current_user,
            "users": users,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "search": search or "",
            "role": role or "",
            "status": status or "",
            "error": error,
            "success": success,
            "roles": UserRole,
            "csrf_token": csrf_token,
            "csrf_signature": csrf_signature,
        },
    )


# ============================================================
# USER LIST
# ============================================================

@router.get(
    "",
    response_class=HTMLResponse,
)
def user_list(
    request: Request,
    page: int = Query(
        default=1,
        ge=1,
    ),
    per_page: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    search: str | None = Query(
        default=None
    ),
    role: str | None = Query(
        default=None
    ),
    status: str | None = Query(
        default=None
    ),
    success: str | None = Query(
        default=None
    ),
    error: str | None = Query(
        default=None
    ),
    db: Session = Depends(get_database),
    current_user: User = admin_required,
):
    role_enum = None

    if role:
        try:
            role_enum = UserRole(role)
        except ValueError:
            role_enum = None

    is_active = None

    if status == "active":
        is_active = True

    elif status == "inactive":
        is_active = False

    service = UserManagementService(db)

    users, total = service.list_users(
        page=page,
        per_page=per_page,
        search=search,
        role=role_enum,
        is_active=is_active,
    )

    csrf = csrf_context()

    return render_user_page(
        request,
        current_user=current_user,
        users=users,
        total=total,
        page=page,
        per_page=per_page,
        search=search,
        role=role,
        status=status,
        csrf_token=csrf["csrf_token"],
        csrf_signature=csrf["csrf_signature"],
        error=error,
        success=success,
    )


# ============================================================
# CREATE USER
# ============================================================

@router.get(
    "/create",
    response_class=HTMLResponse,
)
def create_user_page(
    request: Request,
    current_user: User = admin_required,
):
    csrf = csrf_context()

    return templates.TemplateResponse(
        request=request,
        name="pages/admin/users/create.html",
        context={
            "current_user": current_user,
            "roles": UserRole,
            "error": None,
            "form": None,
            "csrf_token": csrf["csrf_token"],
            "csrf_signature": csrf["csrf_signature"],
        },
    )


@router.post(
    "/create",
    response_class=HTMLResponse,
)
def create_user(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    password_confirmation: str = Form(...),
    role: str = Form(...),
    is_active: str | None = Form(
        default=None
    ),
    nip: str | None = Form(default=None),
    db: Session = Depends(get_database),
    current_user: User = admin_required,
    _: None = Depends(require_csrf),
):
    try:
        role_enum = UserRole(role)

        data = UserCreateSchema(
            email=email,
            full_name=full_name,
            password=password,
            password_confirmation=password_confirmation,
            role=role_enum,
            is_active=is_active == "true",
            nip=nip,
        )

        service = UserManagementService(db)

        service.create_user(
            data=data,
            admin_user=current_user,
            ip_address=get_request_ip(request),
            user_agent=get_user_agent(request),
            device=detect_device(
                get_user_agent(request)
            ),
        )

        return RedirectResponse(
            url="/users?success=User berhasil dibuat.",
            status_code=303,
        )

    except (
        ValueError,
        ValidationError,
    ) as exc:
        db.rollback()

        error = str(exc)

        if isinstance(
            exc,
            ValidationError,
        ):
            error = exc.errors()[0]["msg"]

        csrf = csrf_context()

        return templates.TemplateResponse(
            request=request,
            name="pages/admin/users/create.html",
            context={
                "current_user": current_user,
                "roles": UserRole,
                "error": error,
                "form": {
                    "email": email,
                    "full_name": full_name,
                    "role": role,
                    "is_active": is_active,
                    "nip": nip or "",
                },
                "csrf_token": csrf["csrf_token"],
                "csrf_signature": csrf["csrf_signature"],
            },
            status_code=422,
        )


# ============================================================
# EDIT USER
# ============================================================

@router.get(
    "/{user_id}/edit",
    response_class=HTMLResponse,
)
def edit_user_page(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_database),
    current_user: User = admin_required,
):
    service = UserManagementService(db)

    try:
        user = service.get_user(
            user_id
        )

    except NotFoundException:
        return RedirectResponse(
            url="/users?error=User tidak ditemukan.",
            status_code=303,
        )

    csrf = csrf_context()

    return templates.TemplateResponse(
        request=request,
        name="pages/admin/users/edit.html",
        context={
            "current_user": current_user,
            "user": user,
            "roles": UserRole,
            "error": None,
            "csrf_token": csrf["csrf_token"],
            "csrf_signature": csrf["csrf_signature"],
        },
    )


@router.post(
    "/{user_id}/edit",
    response_class=HTMLResponse,
)
def edit_user(
    request: Request,
    user_id: uuid.UUID,
    email: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    is_active: str | None = Form(
        default=None
    ),
    nip: str | None = Form(default=None),
    db: Session = Depends(get_database),
    current_user: User = admin_required,
    _: None = Depends(require_csrf),
):
    try:
        role_enum = UserRole(role)

        data = UserUpdateSchema(
            email=email,
            full_name=full_name,
            role=role_enum,
            is_active=is_active == "true",
            nip=nip,
        )

        service = UserManagementService(db)

        service.update_user(
            user_id=user_id,
            data=data,
            admin_user=current_user,
            ip_address=get_request_ip(request),
            user_agent=get_user_agent(request),
            device=detect_device(
                get_user_agent(request)
            ),
        )

        return RedirectResponse(
            url="/users?success=User berhasil diperbarui.",
            status_code=303,
        )

    except (
        ValueError,
        ValidationError,
        ForbiddenException,
        NotFoundException,
    ) as exc:
        db.rollback()

        error = str(exc)

        if isinstance(
            exc,
            ValidationError,
        ):
            error = exc.errors()[0]["msg"]

        service = UserManagementService(db)

        try:
            user = service.get_user(
                user_id
            )

        except NotFoundException:
            return RedirectResponse(
                url="/users?error=User tidak ditemukan.",
                status_code=303,
            )

        csrf = csrf_context()

        return templates.TemplateResponse(
            request=request,
            name="pages/admin/users/edit.html",
            context={
                "current_user": current_user,
                "user": user,
                "roles": UserRole,
                "error": error,
                "csrf_token": csrf["csrf_token"],
                "csrf_signature": csrf["csrf_signature"],
            },
            status_code=422,
        )


# ============================================================
# CHANGE PASSWORD
# ============================================================

@router.get(
    "/{user_id}/password",
    response_class=HTMLResponse,
)
def edit_password_page(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_database),
    current_user: User = admin_required,
):
    service = UserManagementService(db)

    try:
        user = service.get_user(
            user_id
        )

    except NotFoundException:
        return RedirectResponse(
            url="/users?error=User tidak ditemukan.",
            status_code=303,
        )

    csrf = csrf_context()

    return templates.TemplateResponse(
        request=request,
        name="pages/admin/users/password.html",
        context={
            "current_user": current_user,
            "user": user,
            "error": None,
            "csrf_token": csrf["csrf_token"],
            "csrf_signature": csrf["csrf_signature"],
        },
    )


@router.post(
    "/{user_id}/password",
)
def edit_password(
    request: Request,
    user_id: uuid.UUID,
    password: str = Form(...),
    password_confirmation: str = Form(...),
    db: Session = Depends(get_database),
    current_user: User = admin_required,
    _: None = Depends(require_csrf),
):
    try:
        data = UserPasswordUpdateSchema(
            password=password,
            password_confirmation=password_confirmation,
        )

        service = UserManagementService(db)

        service.update_password(
            user_id=user_id,
            data=data,
            admin_user=current_user,
            ip_address=get_request_ip(request),
            user_agent=get_user_agent(request),
            device=detect_device(
                get_user_agent(request)
            ),
        )

        return RedirectResponse(
            url="/users?success=Password user berhasil diubah.",
            status_code=303,
        )

    except (
        ValueError,
        ValidationError,
        NotFoundException,
    ) as exc:
        db.rollback()

        error = str(exc)

        if isinstance(
            exc,
            ValidationError,
        ):
            error = exc.errors()[0]["msg"]

        service = UserManagementService(db)

        try:
            user = service.get_user(
                user_id
            )

        except NotFoundException:
            return RedirectResponse(
                url="/users?error=User tidak ditemukan.",
                status_code=303,
            )

        csrf = csrf_context()

        return templates.TemplateResponse(
            request=request,
            name="pages/admin/users/password.html",
            context={
                "current_user": current_user,
                "user": user,
                "error": error,
                "csrf_token": csrf["csrf_token"],
                "csrf_signature": csrf["csrf_signature"],
            },
            status_code=422,
        )


# ============================================================
# CHANGE USER STATUS
# ============================================================

@router.post(
    "/{user_id}/status",
)
def change_status(
    request: Request,
    user_id: uuid.UUID,
    is_active: str = Form(...),
    db: Session = Depends(get_database),
    current_user: User = admin_required,
    _: None = Depends(require_csrf),
):
    try:
        active = is_active == "true"

        service = UserManagementService(db)

        service.set_status(
            user_id=user_id,
            is_active=active,
            admin_user=current_user,
            ip_address=get_request_ip(request),
            user_agent=get_user_agent(request),
            device=detect_device(
                get_user_agent(request)
            ),
        )

        message = (
            "User berhasil diaktifkan."
            if active
            else "User berhasil dinonaktifkan."
        )

        return RedirectResponse(
            url=f"/users?success={message}",
            status_code=303,
        )

    except (
        ForbiddenException,
        NotFoundException,
    ) as exc:
        db.rollback()

        return RedirectResponse(
            url=f"/users?error={str(exc)}",
            status_code=303,
        )


# ============================================================
# DELETE USER
# ============================================================

@router.post(
    "/{user_id}/delete",
)
def delete_user(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_database),
    current_user: User = admin_required,
    _: None = Depends(require_csrf),
):
    try:
        service = UserManagementService(db)

        service.delete_user(
            user_id=user_id,
            admin_user=current_user,
            ip_address=get_request_ip(request),
            user_agent=get_user_agent(request),
            device=detect_device(
                get_user_agent(request)
            ),
        )

        return RedirectResponse(
            url="/users?success=User berhasil dihapus.",
            status_code=303,
        )

    except (
        ForbiddenException,
        NotFoundException,
    ) as exc:
        db.rollback()

        return RedirectResponse(
            url=f"/users?error={str(exc)}",
            status_code=303,
        )