from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.models.generation import GenerationStatus
from app.models.user import User
from app.schemas.generation import GenerationCreateSchema
from app.services import generation_runner as runner_module
from app.services.generation_runner import GenerationRunner
from app.services.generation_service import GenerationService


def test_runner_rebuilds_upload_closes_it_and_calls_generation_service(monkeypatch):
    generation_id, user_id = uuid4(), uuid4()
    user = SimpleNamespace(id=user_id)
    generation = SimpleNamespace(id=generation_id)
    db = SimpleNamespace(get=lambda model, _id: user if model is User else generation)
    monkeypatch.setattr(runner_module, "SessionLocal", lambda: _SessionContext(db))
    received = {}

    def create(_service, data, passed_user, **kwargs):
        kwargs["upload"].file.seek(0)
        received["upload_contents"] = kwargs["upload"].file.read()
        received.update(data=data, user=passed_user, **kwargs)

    monkeypatch.setattr(GenerationService, "create", create)
    data = GenerationCreateSchema(title="T", subject="S", class_name="1", type_materi="FILE", cognitive_levels=["C1"], total_essay=1)

    GenerationRunner._run(
        generation_id,
        user_id,
        data,
        b"file contents",
        "materi.docx",
        "application/octet-stream",
        "127.0.0.1",
        "unit-test-agent",
    )

    assert received["user"] is user
    assert received["existing_generation"] is generation
    assert received["upload_contents"] == b"file contents"
    assert received["upload"].file.closed


def test_runner_persists_failed_status_when_queued_user_is_missing(monkeypatch):
    generation_id = uuid4()
    generation = SimpleNamespace(
        id=generation_id,
        status=GenerationStatus.PENDING,
        error_message=None,
        progress_json='{"status":"PENDING","stages":[]}',
    )

    class FakeDB:
        committed = False

        def get(self, model, _id):
            return None if model is User else generation

        def rollback(self):
            pass

        def commit(self):
            self.committed = True

    db = FakeDB()
    monkeypatch.setattr(runner_module, "SessionLocal", lambda: _SessionContext(db))
    data = GenerationCreateSchema(title="T", subject="S", class_name="1", type_materi="TEXT", materi_text="Materi", cognitive_levels=["C1"], total_essay=1)

    GenerationRunner._run(generation_id, uuid4(), data, None, None, None, None, None)

    assert generation.status == GenerationStatus.FAILED
    assert "periksa materi" in generation.error_message.lower()
    assert db.committed


class _SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *_args):
        return False
