from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from app.models.generation import GenerationStatus
from app.routers import generation as generation_router
from app.services.generation_service import GenerationService


def test_progress_status_endpoint_returns_safe_persisted_error_without_resubmitting(monkeypatch):
    owner_id = uuid4()
    generation_id = uuid4()
    generation = SimpleNamespace(
        id=generation_id,
        user_id=owner_id,
        title="Generation uji",
        status=GenerationStatus.FAILED,
        progress_json=json.dumps({"status": "FAILED", "current_stage": "gemini", "total_duration_ms": 120}),
        started_at=None,
        error_message="Layanan AI tidak memberikan respons dalam batas waktu yang ditentukan.",
        questions=[],
    )
    monkeypatch.setattr(GenerationService, "detail", lambda _self, _id, _user: generation)

    def fail_if_submitted(*_args, **_kwargs):
        raise AssertionError("Polling status must not submit another generation")

    monkeypatch.setattr(generation_router.generation_runner, "submit", fail_if_submitted)
    payload = generation_router.generation_progress_status(
        generation_id,
        db=object(),
        user=SimpleNamespace(id=owner_id),
    )

    assert payload["status"] == "FAILED"
    assert payload["error_title"] == "Layanan AI mengalami timeout"
    assert payload["total_duration_ms"] == 120
