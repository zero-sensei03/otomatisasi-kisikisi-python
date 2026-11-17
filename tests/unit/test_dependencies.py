from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import dependencies
from app.models.user import UserRole


def test_session_token_and_current_user_dependency_read_session_user():
    user = SimpleNamespace(is_active=True)
    session = SimpleNamespace(user=user)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(session_cookie_name="session"))),
        cookies={"session": "cookie-token"},
    )
    assert dependencies.get_session_token(request) == "cookie-token"
    assert dependencies.get_current_user(session) is user


@pytest.mark.parametrize("active", [True, False])
def test_current_session_rejects_missing_invalid_or_inactive_session(monkeypatch, active):
    session = SimpleNamespace(user=SimpleNamespace(is_active=active))
    monkeypatch.setattr(dependencies, "get_session_token", lambda _request: "token")
    monkeypatch.setattr(dependencies, "AuthService", lambda _db: SimpleNamespace(get_valid_session=lambda _token: session))
    request = SimpleNamespace()

    if active:
        assert dependencies.get_current_session(request, object()) is session
    else:
        with pytest.raises(HTTPException) as error:
            dependencies.get_current_session(request, object())
        assert error.value.status_code == 403

    monkeypatch.setattr(dependencies, "AuthService", lambda _db: SimpleNamespace(get_valid_session=lambda _token: None))
    with pytest.raises(HTTPException) as invalid:
        dependencies.get_current_session(request, object())
    assert invalid.value.status_code == 401


def test_role_and_csrf_dependencies_enforce_access(monkeypatch):
    admin_check = dependencies.require_roles(UserRole.ADMIN)
    admin = SimpleNamespace(role=UserRole.ADMIN)
    assert admin_check(admin) is admin
    with pytest.raises(HTTPException) as forbidden:
        admin_check(SimpleNamespace(role=UserRole.GURU))
    assert forbidden.value.status_code == 403

    monkeypatch.setattr(dependencies, "verify_csrf_token", lambda token, signature: token == "t" and signature == "s")
    assert dependencies.require_csrf("t", "s") is None
    with pytest.raises(HTTPException) as invalid:
        dependencies.require_csrf("bad", "s")
    assert invalid.value.status_code == 403


def test_optional_current_user_handles_no_token_and_active_user(monkeypatch):
    request = SimpleNamespace()
    monkeypatch.setattr(dependencies, "get_session_token", lambda _request: None)
    assert dependencies.get_current_user_optional(request, object()) is None

    user = SimpleNamespace(is_active=True)
    monkeypatch.setattr(dependencies, "get_session_token", lambda _request: "token")
    monkeypatch.setattr(dependencies, "AuthService", lambda _db: SimpleNamespace(get_valid_session=lambda _token: SimpleNamespace(user=user)))
    assert dependencies.get_current_user_optional(request, object()) is user
    monkeypatch.setattr(dependencies, "AuthService", lambda _db: SimpleNamespace(get_valid_session=lambda _token: SimpleNamespace(user=SimpleNamespace(is_active=False))))
    assert dependencies.get_current_user_optional(request, object()) is None
