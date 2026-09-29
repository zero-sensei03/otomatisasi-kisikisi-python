from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    get_csrf_token,
    login_user,
    logout_user,
    validate_csrf_token,
)
from app.services.auth import authenticate_user


router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates",
)


@router.get(
    "/login",
    response_class=HTMLResponse,
)
def login_page(request: Request):
    user_id = request.session.get("user_id")

    if user_id:
        return RedirectResponse(
            url="/dashboard",
            status_code=303,
        )

    csrf_token = get_csrf_token(request)

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "csrf_token": csrf_token,
            "error": None,
        },
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    user = authenticate_user(
        db=db,
        username_or_email=username.strip(),
        password=password,
    )

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "csrf_token": get_csrf_token(request),
                "error": "Username/email atau password salah.",
                "username": username,
            },
            status_code=401,
        )

    login_user(
        request,
        user.id,
    )

    return RedirectResponse(
        url="/dashboard",
        status_code=303,
    )


@router.post("/logout")
def logout(
    request: Request,
    csrf_token: str = Form(...),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    logout_user(request)

    return RedirectResponse(
        url="/login",
        status_code=303,
    )
