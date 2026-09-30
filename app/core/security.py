from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from app.core.config import get_settings


password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    try:
        return password_hasher.verify(
            password_hash,
            password,
        )
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


def generate_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def sign_csrf_token(token: str) -> str:
    settings = get_settings()

    return hmac.new(
        settings.secret_key.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_csrf_token(
    token: str,
    signature: str,
) -> bool:
    expected = sign_csrf_token(token)

    return hmac.compare_digest(
        expected,
        signature,
    )


def generate_session_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_csrf_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def verify_csrf_hash(
    token: str,
    token_hash: str,
) -> bool:
    return hmac.compare_digest(
        hash_csrf_token(token),
        token_hash,
    )


def detect_device(user_agent: str | None) -> str:
    if not user_agent:
        return "Unknown Device"

    value = user_agent.lower()

    if "ipad" in value:
        return "iPad"

    if "iphone" in value:
        return "iPhone"

    if "android" in value:
        if "mobile" in value:
            return "Android Mobile"

        return "Android Tablet"

    if "windows" in value:
        return "Windows PC"

    if "macintosh" in value:
        return "Mac"

    if "linux" in value:
        return "Linux PC"

    return "Unknown Device"