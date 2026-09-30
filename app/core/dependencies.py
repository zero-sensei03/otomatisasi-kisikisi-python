from __future__ import annotations

from collections.abc import Callable, Generator

from fastapi import Depends, Form, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import verify_csrf_token
from app.models.user import User, UserRole
from app.services.auth_service import AuthService


def get_database() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_session_token(
    request: Request,
) -> str | None:
    settings = request.app.state.settings

    return request.cookies.get(
        settings.session_cookie_name
    )


def get_current_session(
    request: Request,
    db: Session = Depends(get_database),
):
    token = get_session_token(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    service = AuthService(db)

    session = service.get_valid_session(token)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session tidak valid atau sudah berakhir.",
        )

    if not session.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun tidak aktif.",
        )

    return session


def get_current_user(
    session=Depends(get_current_session),
) -> User:
    return session.user


def require_roles(
    *roles: UserRole,
) -> Callable:
    def dependency(
        current_user: User = Depends(
            get_current_user
        ),
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak memiliki akses.",
            )

        return current_user

    return dependency


def require_csrf(
    csrf_token: str = Form(...),
    csrf_signature: str = Form(...),
) -> None:
    """
    Memverifikasi CSRF token menggunakan mekanisme
    signed token yang sama dengan authentication.

    Form harus mengirim:

        csrf_token
        csrf_signature

    Signature diverifikasi menggunakan SECRET_KEY.
    """

    if not verify_csrf_token(
        csrf_token,
        csrf_signature,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Permintaan tidak valid. "
                "Silakan muat ulang halaman."
            ),
        )


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_database),
) -> User | None:
    token = get_session_token(request)

    if not token:
        return None

    service = AuthService(db)

    session = service.get_valid_session(token)

    if not session:
        return None

    if not session.user.is_active:
        return None

    return session.user