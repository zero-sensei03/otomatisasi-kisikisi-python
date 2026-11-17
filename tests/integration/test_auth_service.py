from __future__ import annotations

import datetime

import pytest
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.user_session import UserSession
from app.schemas.auth import LoginSchema, PasswordChangeSchema, RegisterSchema, UserUpdateSchema
from app.services.auth_service import AuthService


def test_register_normalizes_email_and_creates_teacher_profile(db_session, monkeypatch):
    monkeypatch.setattr("app.services.auth_service.hash_password", lambda _password: "hashed-password")
    service = AuthService(db_session)
    user = service.register(RegisterSchema(
        full_name="  Guru Tes ",
        email="GURU@example.com",
        password="password-123",
        password_confirmation="password-123",
        nip="  12345 ",
    ))

    assert user.email == "guru@example.com"
    assert user.full_name == "Guru Tes"
    assert user.role == UserRole.GURU
    assert user.password_hash == "hashed-password"
    assert user.teacher.nip == "12345"


@pytest.mark.parametrize("case", ["duplicate", "password_confirmation"])
def test_register_rejects_duplicate_email_or_mismatched_password(db_session, monkeypatch, case):
    monkeypatch.setattr("app.services.auth_service.hash_password", lambda _password: "hashed")
    service = AuthService(db_session)
    db_session.add(User(email="guru@example.com", full_name="Guru Lama", password_hash="hashed"))
    db_session.commit()
    payload = RegisterSchema(
        full_name="Guru Baru",
        email="guru@example.com" if case == "duplicate" else "baru@example.org",
        password="password-123",
        password_confirmation="different-123" if case == "password_confirmation" else "password-123",
    )

    with pytest.raises(HTTPException) as error:
        service.register(payload)
    assert error.value.status_code == (409 if case == "duplicate" else 422)


def test_login_creates_session_and_rejects_inactive_or_invalid_user(db_session, monkeypatch):
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_args: True)
    monkeypatch.setattr("app.services.auth_service.generate_token", lambda: "session-token")
    monkeypatch.setattr("app.services.auth_service.generate_csrf_token", lambda: "csrf-token")
    user = User(email="guru@example.com", full_name="Guru", password_hash="hashed")
    db_session.add(user)
    db_session.commit()
    service = AuthService(db_session)

    logged_in, token, csrf = service.login(LoginSchema(email=user.email, password="password-123"), user_agent="Mozilla/5.0 (Windows NT 10.0)")
    assert logged_in.id == user.id
    assert (token, csrf) == ("session-token", "csrf-token")
    session = db_session.query(UserSession).one()
    assert session.device == "Windows PC"
    assert session.token_hash

    with pytest.raises(HTTPException) as missing:
        service.login(LoginSchema(email="missing@example.org", password="password-123"))
    assert missing.value.status_code == 401

    user.is_active = False
    db_session.commit()
    with pytest.raises(HTTPException) as inactive:
        service.login(LoginSchema(email=user.email, password="password-123"))
    assert inactive.value.status_code == 403


def test_profile_password_change_and_session_revocation(db_session, monkeypatch):
    password_hashes = iter(["hash-new"])
    monkeypatch.setattr("app.services.auth_service.hash_password", lambda _password: next(password_hashes))
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda password, hashed: password == "old-password" and hashed == "hash-old")
    user = User(email="guru@example.com", full_name="Guru", password_hash="hash-old")
    db_session.add(user)
    db_session.commit()
    session = UserSession(user_id=user.id, token_hash="t" * 64, csrf_token_hash="c" * 64, expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1))
    db_session.add(session)
    db_session.commit()
    service = AuthService(db_session)

    updated = service.update_profile(user, UserUpdateSchema(full_name="Guru Baru", email=" GURU2@example.org "))
    assert updated.full_name == "Guru Baru"
    assert updated.email == "guru2@example.org"

    service.change_password(user, PasswordChangeSchema(current_password="old-password", new_password="new-password", new_password_confirmation="new-password"))
    assert user.password_hash == "hash-new"
    db_session.refresh(session)
    assert db_session.get(UserSession, session.id).revoked_at is not None

    with pytest.raises(HTTPException, match="Password lama salah"):
        service.change_password(user, PasswordChangeSchema(current_password="wrong-password", new_password="next-password", new_password_confirmation="next-password"))


def test_logout_is_idempotent_and_valid_session_rejects_revoked_or_expired():
    from types import SimpleNamespace

    service = object.__new__(AuthService)
    service.db = SimpleNamespace(commit=lambda: None)
    service.audit = SimpleNamespace(log=lambda **_kwargs: None)
    revoked = SimpleNamespace(revoked_at=datetime.datetime.now(datetime.UTC), user_id=None, id="session")
    assert service.logout(revoked) is None

    class SessionDB:
        def __init__(self, session):
            self.session = session

        def scalar(self, _statement):
            return self.session

    service.db = SessionDB(None)
    assert service.get_valid_session("missing") is None
    service.db = SessionDB(SimpleNamespace(revoked_at=datetime.datetime.now(datetime.UTC)))
    assert service.get_valid_session("revoked") is None
