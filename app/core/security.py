import secrets

from fastapi import HTTPException, Request, status
from pwdlib import PasswordHash


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")

    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token

    return token


def validate_csrf_token(request: Request, token: str) -> None:
    session_token = request.session.get("csrf_token")

    if not session_token or not secrets.compare_digest(
        session_token,
        token,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )


def login_user(request: Request, user_id: int) -> None:
    csrf_token = get_csrf_token(request)

    request.session.clear()

    request.session["user_id"] = user_id
    request.session["csrf_token"] = csrf_token


def logout_user(request: Request) -> None:
    request.session.clear()
