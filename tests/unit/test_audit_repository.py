from __future__ import annotations

from uuid import uuid4

from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.schemas.audit_log import AuditLogFilter
from app.services.audit_service import AuditService


def test_audit_log_repository_filters_searches_paginates_and_loads_null_owner(db_session):
    user = User(email="admin@example.com", full_name="Admin Example", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    matching = AuditLog(user_id=user.id, action="UPDATE_SETTINGS", feature="SETTINGS", resource="CONFIG", description="Material limit changed", device="Desktop")
    unrelated = AuditLog(user_id=user.id, action="LOGIN", feature="AUTH", resource="USER", description="signed in", device="Mobile")
    orphan = AuditLog(user_id=None, action="SYSTEM_EVENT", feature="SYSTEM", resource="WORKER", description="worker completed", device="Server")
    db_session.add_all([matching, unrelated, orphan])
    db_session.commit()
    repository = AuditLogRepository(db_session)

    all_items, all_count = repository.get_all_paginated(AuditLogFilter(per_page=2))
    assert all_count == 3
    assert len(all_items) == 2
    assert all(item.user is not None or item.action == "SYSTEM_EVENT" for item in all_items)

    filtered, total = repository.get_all_paginated(AuditLogFilter(search="material", action="UPDATE_%", feature="SETTINGS", resource="CONFIG", full_name="Admin", page=1, per_page=10))
    assert total == 1
    assert filtered[0].id == matching.id
    assert repository.get_by_id(orphan.id).user is None
    assert repository.get_by_id(matching.id).action == "UPDATE_SETTINGS"
    assert repository.get_by_id(unrelated.id) is not None
    assert repository.get_by_id(uuid4()) is None


def test_audit_service_logs_and_returns_paginated_typed_results(db_session):
    user = User(email="teacher@example.com", full_name="Guru", password_hash="hash")
    db_session.add(user)
    db_session.commit()
    service = AuditService(db_session)
    log = service.log(action="LOGIN", feature="AUTH", user_id=user.id, user_agent="Mozilla/5.0 (Windows NT 10.0)")
    db_session.commit()

    result = service.get_all_logs(AuditLogFilter(search="LOGIN"))
    assert result.total == 1
    assert result.total_pages == 1
    assert result.items[0].action == "LOGIN"
    assert result.items[0].device == "Windows PC"
    assert service.get_log_by_id(log.id).id == log.id
