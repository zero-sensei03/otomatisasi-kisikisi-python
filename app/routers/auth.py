from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Request,
    status,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import (
    get_current_session,
    get_current_user,
    get_database,
)
from app.core.security import (
    generate_csrf_token,
    sign_csrf_token,
    verify_csrf_token,
)
from app.models.user import User
from app.schemas.auth import (
    LoginSchema,
    PasswordChangeSchema,
    RegisterSchema,
    UserResponse,
    UserUpdateSchema,
)
from app.services.auth_service import AuthService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

templates = Jinja2Templates(
    directory="app/templates"
)


def get_client_ip(
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
    token = generate_csrf_token()

    return {
        "csrf_token": token,
        "csrf_signature": sign_csrf_token(
            token
        ),
    }


def verify_public_csrf(
    request: Request,
    token: str,
    signature: str,
) -> bool:
    cookie = request.cookies.get(
        get_settings().csrf_cookie_name
    )

    return (
        cookie == token
        and verify_csrf_token(
            token,
            signature,
        )
    )


@router.get(
    "/login",
    response_class=HTMLResponse,
)
def login_page(
    request: Request,
):
    context = csrf_context()

    response = templates.TemplateResponse(
        request=request,
        name="pages/auth/login.html",
        context={
            "title": "Masuk",
            "error": None,
            **context,
        },
    )

    settings = get_settings()

    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=context["csrf_token"],
        max_age=settings.csrf_max_age,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        path="/auth",
    )

    return response


@router.post(
    "/login",
    response_class=HTMLResponse,
)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    csrf_signature: str = Form(...),
    db: Session = Depends(get_database),
):
    context = {
        "csrf_token": csrf_token,
        "csrf_signature": csrf_signature,
        "email": email,
    }

    if not verify_public_csrf(
        request,
        csrf_token,
        csrf_signature,
    ):
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/login.html",
            context={
                "title": "Masuk",
                "error": (
                    "Permintaan tidak valid. "
                    "Silakan muat ulang halaman."
                ),
                **context,
            },
            status_code=403,
        )

    try:
        service = AuthService(db)

        user, session_token, session_csrf = (
            service.login(
                LoginSchema(
                    email=email,
                    password=password,
                ),
                ip_address=get_client_ip(
                    request
                ),
                user_agent=get_user_agent(
                    request
                ),
            )
        )

        settings = get_settings()

        response = RedirectResponse(
            "/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )

        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_token,
            max_age=settings.session_max_age,
            httponly=True,
            secure=not settings.debug,
            samesite="lax",
            path="/",
        )

        response.set_cookie(
            key="kisikisi_session_csrf",
            value=session_csrf,
            max_age=settings.session_max_age,
            httponly=False,
            secure=not settings.debug,
            samesite="lax",
            path="/",
        )

        response.delete_cookie(
            key=settings.csrf_cookie_name,
            path="/auth",
        )

        return response

    except Exception as exc:
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/login.html",
            context={
                "title": "Masuk",
                "error": getattr(
                    exc,
                    "detail",
                    "Login gagal.",
                ),
                **context,
            },
            status_code=getattr(
                exc,
                "status_code",
                400,
            ),
        )


@router.get(
    "/register",
    response_class=HTMLResponse,
)
def register_page(
    request: Request,
):
    context = csrf_context()

    response = templates.TemplateResponse(
        request=request,
        name="pages/auth/register.html",
        context={
            "title": "Daftar Guru",
            "error": None,
            **context,
        },
    )

    settings = get_settings()

    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=context["csrf_token"],
        max_age=settings.csrf_max_age,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        path="/auth",
    )

    return response


@router.post(
    "/register",
    response_class=HTMLResponse,
)
def register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirmation: str = Form(...),
    nip: str = Form(""),
    csrf_token: str = Form(...),
    csrf_signature: str = Form(...),
    db: Session = Depends(get_database),
):
    context = {
        "csrf_token": csrf_token,
        "csrf_signature": csrf_signature,
        "full_name": full_name,
        "email": email,
        "nip": nip,
    }

    if not verify_public_csrf(
        request,
        csrf_token,
        csrf_signature,
    ):
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/register.html",
            context={
                "title": "Daftar Guru",
                "error": (
                    "Permintaan tidak valid. "
                    "Silakan muat ulang halaman."
                ),
                **context,
            },
            status_code=403,
        )

    try:
        service = AuthService(db)

        service.register(
            RegisterSchema(
                full_name=full_name,
                email=email,
                password=password,
                password_confirmation=(
                    password_confirmation
                ),
                nip=nip or None,
            ),
            ip_address=get_client_ip(
                request
            ),
            user_agent=get_user_agent(
                request
            ),
        )

        return RedirectResponse(
            "/auth/login?registered=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except Exception as exc:
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/register.html",
            context={
                "title": "Daftar Guru",
                "error": getattr(
                    exc,
                    "detail",
                    "Registrasi gagal.",
                ),
                **context,
            },
            status_code=getattr(
                exc,
                "status_code",
                400,
            ),
        )


@router.post(
    "/logout",
)
def logout(
    request: Request,
    session=Depends(get_current_session),
    db: Session = Depends(get_database),
):
    service = AuthService(db)

    service.logout(
        session,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )

    response = RedirectResponse(
        "/auth/login",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    settings = get_settings()

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
    )

    response.delete_cookie(
        key="kisikisi_session_csrf",
        path="/",
    )

    return response


@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
)
def update_me(
    data: UserUpdateSchema,
    request: Request,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_database),
):
    service = AuthService(db)

    return service.update_profile(
        current_user,
        data,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )


@router.post(
    "/change-password",
)
def change_password(
    data: PasswordChangeSchema,
    request: Request,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_database),
):
    service = AuthService(db)

    service.change_password(
        current_user,
        data,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )

    return {
        "message": "Password berhasil diubah."
    }