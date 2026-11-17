from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException
from starlette.requests import Request

from app.main import app as application
from app.routers import auth as auth_router


def request(path="/auth", *, cookie=None):
    headers = [(b"user-agent", b"unit-test")]
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 8080),
        "server": ("testserver", 80),
        "app": application,
        "router": application.router,
    })


def settings():
    return SimpleNamespace(
        csrf_cookie_name="csrf",
        csrf_max_age=300,
        session_cookie_name="session",
        session_max_age=3600,
        debug=True,
    )


def test_auth_helpers_and_public_csrf_validation(monkeypatch):
    req = request(cookie="csrf=csrf-value")
    monkeypatch.setattr(auth_router, "get_settings", settings)
    monkeypatch.setattr(auth_router, "generate_csrf_token", lambda: "generated-token")
    monkeypatch.setattr(auth_router, "sign_csrf_token", lambda token: f"signed-{token}")
    monkeypatch.setattr(auth_router, "verify_csrf_token", lambda token, signature: (token, signature) == ("csrf-value", "signature"))
    assert auth_router.get_client_ip(req) == "127.0.0.1"
    assert auth_router.get_user_agent(req) == "unit-test"
    assert auth_router.verify_public_csrf(req, "csrf-value", "signature")
    assert not auth_router.verify_public_csrf(req, "other", "signature")
    assert auth_router.csrf_context() == {"csrf_token": "generated-token", "csrf_signature": "signed-generated-token"}


def test_auth_pages_set_csrf_cookie(monkeypatch):
    monkeypatch.setattr(auth_router, "get_settings", settings)
    monkeypatch.setattr(auth_router, "generate_csrf_token", lambda: "csrf-value")
    monkeypatch.setattr(auth_router, "sign_csrf_token", lambda _token: "signed-value")

    login_response = auth_router.login_page(request("/auth/login"))
    register_response = auth_router.register_page(request("/auth/register"))
    assert login_response.status_code == 200
    assert register_response.status_code == 200
    assert "csrf=csrf-value" in login_response.headers["set-cookie"]
    assert "csrf=csrf-value" in register_response.headers["set-cookie"]


def test_login_returns_auth_cookies_or_validation_error(monkeypatch):
    monkeypatch.setattr(auth_router, "get_settings", settings)
    monkeypatch.setattr(auth_router, "verify_public_csrf", lambda *_args: True)
    user = SimpleNamespace(id="user-id")

    class Service:
        def __init__(self, _db):
            pass

        def login(self, *_args, **_kwargs):
            return user, "session-token", "csrf-session"

    monkeypatch.setattr(auth_router, "AuthService", Service)
    success = auth_router.login(request("/auth/login"), "guru@example.com", "password-123", "csrf", "signature", object())
    assert success.status_code == 303
    assert success.headers["location"] == "/dashboard"
    set_cookies = success.headers.getlist("set-cookie")
    assert any("session=session-token" in cookie for cookie in set_cookies)
    assert any("kisikisi_session_csrf=csrf-session" in cookie for cookie in set_cookies)

    monkeypatch.setattr(auth_router, "verify_public_csrf", lambda *_args: False)
    rejected = auth_router.login(request("/auth/login"), "guru@example.com", "password-123", "bad", "signature", object())
    assert rejected.status_code == 403


def test_register_redirects_after_success_and_preserves_fields_on_failure(monkeypatch):
    monkeypatch.setattr(auth_router, "verify_public_csrf", lambda *_args: True)

    class Service:
        def __init__(self, _db):
            pass

        def register(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(auth_router, "AuthService", Service)
    success = auth_router.register(request("/auth/register"), "Guru Baru", "guru@example.com", "password-123", "password-123", "123", "csrf", "signature", object())
    assert success.status_code == 303
    assert success.headers["location"] == "/auth/login?registered=1"

    class FailingService(Service):
        def register(self, *_args, **_kwargs):
            raise HTTPException(status_code=409, detail="Email sudah terdaftar.")

    monkeypatch.setattr(auth_router, "AuthService", FailingService)
    failed = auth_router.register(request("/auth/register"), "Guru Baru", "guru@example.com", "password-123", "password-123", "123", "csrf", "signature", object())
    assert failed.status_code == 409
    assert "guru@example.com" in failed.body.decode()


def test_logout_me_profile_and_password_handlers_use_auth_service(monkeypatch):
    monkeypatch.setattr(auth_router, "get_settings", settings)
    calls = []
    user = SimpleNamespace(id="user-id")
    session = SimpleNamespace(user_id="user-id")

    class Service:
        def __init__(self, _db):
            pass

        def logout(self, *_args, **_kwargs):
            calls.append("logout")

        def update_profile(self, current_user, data, **_kwargs):
            calls.append("profile")
            return current_user

        def change_password(self, *_args, **_kwargs):
            calls.append("password")

    monkeypatch.setattr(auth_router, "AuthService", Service)
    response = auth_router.logout(request("/auth/logout"), session, object())
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"
    assert auth_router.me(user) is user
    assert auth_router.update_me(SimpleNamespace(), request(), user, object()) is user
    assert auth_router.change_password(SimpleNamespace(), request(), user, object()) == {"message": "Password berhasil diubah."}
    assert calls == ["logout", "profile", "password"]
