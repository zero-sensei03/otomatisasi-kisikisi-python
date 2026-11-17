from __future__ import annotations

import pytest

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.user import User, UserRole
from app.schemas.user_management import UserCreateSchema, UserPasswordUpdateSchema, UserUpdateSchema
from app.services.user_management_service import UserManagementService


def admin(db_session):
    user = User(email="admin@example.com", full_name="Admin", password_hash="hash", role=UserRole.ADMIN)
    db_session.add(user)
    db_session.commit()
    return user


def test_user_management_creates_teacher_and_rejects_duplicate_email(db_session, monkeypatch):
    monkeypatch.setattr("app.services.user_management_service.hash_password", lambda _password: "hashed")
    administrator = admin(db_session)
    service = UserManagementService(db_session)
    payload = UserCreateSchema(email="guru@example.com", full_name="Guru Baru", password="password-123", password_confirmation="password-123", role=UserRole.GURU, nip="12345")
    created = service.create_user(data=payload, admin_user=administrator, ip_address=None, user_agent=None, device=None)

    assert created.email == "guru@example.com"
    assert created.teacher.nip == "12345"
    with pytest.raises(ValueError, match="sudah digunakan"):
        service.create_user(data=payload, admin_user=administrator, ip_address=None, user_agent=None, device=None)


def test_user_management_update_role_adds_or_removes_teacher_profile(db_session):
    administrator = admin(db_session)
    target = User(email="guru@example.com", full_name="Guru", password_hash="hash", role=UserRole.GURU)
    from app.models.teacher import Teacher

    target.teacher = Teacher(nip="100")
    db_session.add(target)
    db_session.commit()
    service = UserManagementService(db_session)

    updated = service.update_user(
        user_id=target.id,
        data=UserUpdateSchema(email="guru@example.com", full_name="Guru Admin", role=UserRole.ADMIN, is_active=True),
        admin_user=administrator,
        ip_address=None,
        user_agent=None,
        device=None,
    )
    assert updated.role == UserRole.ADMIN
    assert updated.teacher is None
    db_session.expire(target, ["teacher"])

    updated = service.update_user(
        user_id=target.id,
        data=UserUpdateSchema(email="guru@example.com", full_name="Guru", role=UserRole.GURU, is_active=True, nip="200"),
        admin_user=administrator,
        ip_address=None,
        user_agent=None,
        device=None,
    )
    assert updated.teacher.nip == "200"


def test_user_management_protects_admin_self_and_changes_status(db_session):
    administrator = admin(db_session)
    service = UserManagementService(db_session)
    with pytest.raises(ForbiddenException):
        service.set_status(user_id=administrator.id, is_active=False, admin_user=administrator, ip_address=None, user_agent=None, device=None)
    with pytest.raises(ForbiddenException):
        service.update_user(
            user_id=administrator.id,
            data=UserUpdateSchema(email=administrator.email, full_name=administrator.full_name, role=UserRole.GURU, is_active=True, nip="123"),
            admin_user=administrator,
            ip_address=None,
            user_agent=None,
            device=None,
        )

    target = User(email="target@example.com", full_name="Target", password_hash="hash")
    db_session.add(target)
    db_session.commit()
    assert service.set_status(user_id=target.id, is_active=False, admin_user=administrator, ip_address=None, user_agent=None, device=None).is_active is False
    assert service.set_status(user_id=target.id, is_active=True, admin_user=administrator, ip_address=None, user_agent=None, device=None).is_active is True


def test_user_management_password_reset_list_get_and_delete(db_session, monkeypatch):
    monkeypatch.setattr("app.services.user_management_service.hash_password", lambda _password: "reset-hash")
    administrator = admin(db_session)
    target = User(email="target@example.com", full_name="Target", password_hash="old")
    db_session.add(target)
    db_session.commit()
    service = UserManagementService(db_session)

    changed = service.update_password(
        user_id=target.id,
        data=UserPasswordUpdateSchema(password="new-password", password_confirmation="new-password"),
        admin_user=administrator,
        ip_address=None,
        user_agent=None,
        device=None,
    )
    assert changed.password_hash == "reset-hash"
    assert service.get_user(target.id).id == target.id
    users, total = service.list_users(search="target", role=UserRole.GURU, is_active=True)
    assert total == 1 and users[0].id == target.id

    with pytest.raises(ForbiddenException):
        service.delete_user(user_id=administrator.id, admin_user=administrator, ip_address=None, user_agent=None, device=None)
    service.delete_user(user_id=target.id, admin_user=administrator, ip_address=None, user_agent=None, device=None)
    with pytest.raises(NotFoundException):
        service.get_user(target.id)


def test_user_management_update_rejects_duplicate_email_and_self_deactivation(db_session):
    administrator = admin(db_session)
    target = User(email="target@example.com", full_name="Target", password_hash="hash")
    other = User(email="other@example.com", full_name="Other", password_hash="hash")
    db_session.add_all([target, other])
    db_session.commit()
    service = UserManagementService(db_session)

    with pytest.raises(ValueError, match="sudah digunakan"):
        service.update_user(
            user_id=target.id,
            data=UserUpdateSchema(email="other@example.com", full_name="Target", role=UserRole.GURU, is_active=True, nip="123"),
            admin_user=administrator,
            ip_address=None,
            user_agent=None,
            device=None,
        )

    with pytest.raises(ForbiddenException):
        service.delete_user(user_id=administrator.id, admin_user=administrator, ip_address=None, user_agent=None, device=None)


def test_user_management_get_user_not_found(db_session):
    service = UserManagementService(db_session)
    with pytest.raises(NotFoundException):
        import uuid

        service.get_user(uuid.UUID("00000000-0000-0000-0000-000000000001"))
