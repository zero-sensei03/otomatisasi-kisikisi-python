from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.security import (
    get_csrf_token,
    validate_csrf_token,
)
from app.models import User
from app.schemas.user import UserCreate
from app.services.user import UserService


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

templates = Jinja2Templates(
    directory="app/templates",
)


@router.get(
    "",
    response_class=HTMLResponse,
)
def index(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = UserService(db)

    users = service.get_all()

    return templates.TemplateResponse(
        request=request,
        name="users/index.html",
        context={
            "current_user": current_user,
            "users": users,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.get(
    "/create",
    response_class=HTMLResponse,
)
def create_page(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        request=request,
        name="users/create.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "error": None,
            "form": None,
        },
    )


@router.post("/create")
def create(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    employee_number: str = Form(""),
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = UserService(db)

    data = UserCreate(
        username=username.strip(),
        email=email.strip(),
        password=password,
        full_name=full_name.strip(),
    )

    try:
        service.create_guru(
            data=data,
            employee_number=(
                employee_number.strip()
                or None
            ),
        )

    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="users/create.html",
            context={
                "current_user": current_user,
                "csrf_token": get_csrf_token(request),
                "error": str(exc),
                "form": {
                    "username": username,
                    "email": email,
                    "full_name": full_name,
                    "employee_number": employee_number,
                },
            },
            status_code=400,
        )

    return RedirectResponse(
        url="/users",
        status_code=303,
    )


@router.get(
    "/{user_id}/edit",
    response_class=HTMLResponse,
)
def edit_page(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = UserService(db)

    user = service.get_by_id(user_id)

    if not user:
        return RedirectResponse(
            url="/users",
            status_code=303,
        )

    if user.role.value != "GURU":
        return RedirectResponse(
            url="/users",
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="users/edit.html",
        context={
            "current_user": current_user,
            "user": user,
            "csrf_token": get_csrf_token(request),
            "error": None,
        },
    )


@router.post("/{user_id}/edit")
def edit(
    user_id: int,
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(...),
    employee_number: str = Form(""),
    password: str = Form(""),
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = UserService(db)

    user = service.get_by_id(user_id)

    if not user:
        return RedirectResponse(
            url="/users",
            status_code=303,
        )

    try:
        service.update_guru(
            user_id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            employee_number=employee_number,
            password=password or None,
        )

    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="users/edit.html",
            context={
                "current_user": current_user,
                "user": user,
                "csrf_token": get_csrf_token(request),
                "error": str(exc),
                "form": {
                    "username": username,
                    "email": email,
                    "full_name": full_name,
                    "employee_number": employee_number,
                },
            },
            status_code=400,
        )

    return RedirectResponse(
        url="/users",
        status_code=303,
    )


@router.post("/{user_id}/toggle-active")
def toggle_active(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    if user_id == current_user.id:
        return RedirectResponse(
            url="/users",
            status_code=303,
        )

    service = UserService(db)

    user = service.get_by_id(user_id)

    if not user:
        return RedirectResponse(
            url="/users",
            status_code=303,
        )

    service.set_active(
        user_id=user.id,
        is_active=not user.is_active,
    )

    return RedirectResponse(
        url="/users",
        status_code=303,
    )


@router.post("/{user_id}/delete")
def delete(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = UserService(db)

    try:
        service.delete(
            user_id=user_id,
            current_user_id=current_user.id,
        )

    except ValueError:
        pass

    return RedirectResponse(
        url="/users",
        status_code=303,
    )
