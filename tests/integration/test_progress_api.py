from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.generation import GenerationStatus
from app.routers import generation as generation_router
from app.services.generation_service import GenerationService


def test_progress_error_card_is_hidden_in_initial_markup_and_css():
    template = Path("app/templates/pages/generation/progress.html").read_text()
    stylesheet = Path("app/static/css/app.css").read_text()

    assert 'id="progress-error" class="alert alert-danger" role="alert" hidden' in template
    assert "#progress-error[hidden], #progress-retry-form[hidden], #progress-result[hidden] { display: none !important; }" in stylesheet


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


@pytest.mark.parametrize("status", [GenerationStatus.PENDING, GenerationStatus.PROCESSING, GenerationStatus.COMPLETED])
def test_non_failed_progress_status_never_exposes_stale_error_on_reload(monkeypatch, status):
    owner_id = uuid4()
    generation_id = uuid4()
    generation = SimpleNamespace(
        id=generation_id,
        user_id=owner_id,
        title="Progress uji",
        status=status,
        progress_json=json.dumps({
            "status": "FAILED",
            "current_stage": "gemini",
            "error": "previous failure with secret=hidden",
            "stages": [{"id": "gemini", "status": "FAILED", "message": "old traceback"}],
        }),
        started_at=None,
        error_message="old raw traceback with api_key=secret",
        questions=[],
    )
    monkeypatch.setattr(GenerationService, "detail", lambda _self, _id, _user: generation)
    user = SimpleNamespace(id=owner_id)

    first = generation_router.generation_progress_status(generation_id, db=object(), user=user)
    second = generation_router.generation_progress_status(generation_id, db=object(), user=user)

    for payload in (first, second):
        assert payload["status"] == status.value
        assert payload["error"] is None
        assert payload["error_title"] is None
        assert "error" not in payload["progress"]
        assert "message" not in payload["progress"]["stages"][0]
        assert payload["progress"]["status"] == status.value
    assert (first["result_url"] is not None) is (status == GenerationStatus.COMPLETED)


@pytest.mark.parametrize(
    ("stored_error", "stage", "expected"),
    [
        ("Layanan AI tidak memberikan respons dalam batas waktu yang ditentukan. Coba kembali.", "gemini", "batas waktu"),
        ("Sistem gagal membaca atau memproses file sumber materi.", "file_extraction", "file sumber materi"),
        ("Materi tidak memenuhi validasi yang diperlukan.", "material_validation", "validasi"),
        ("sqlalchemy.exc.OperationalError: secret database statement", "database_persistence", "menyimpan hasil"),
        (None, "material_validation", "validasi"),
        ("Traceback with api_key=secret and private server details", "gemini", "layanan ai"),
    ],
)
def test_failed_progress_exposes_cause_specific_safe_message(monkeypatch, stored_error, stage, expected):
    owner_id = uuid4()
    generation_id = uuid4()
    generation = SimpleNamespace(
        id=generation_id,
        user_id=owner_id,
        title="Generation gagal",
        status=GenerationStatus.FAILED,
        progress_json=json.dumps({"status": "FAILED", "current_stage": stage, "error": "stale raw error", "stages": []}),
        started_at=None,
        error_message=stored_error,
        questions=[],
    )
    monkeypatch.setattr(GenerationService, "detail", lambda _self, _id, _user: generation)

    payload = generation_router.generation_progress_status(generation_id, db=object(), user=SimpleNamespace(id=owner_id))

    assert payload["status"] == "FAILED"
    assert expected in payload["error"].lower()
    assert payload["error_title"]
    assert "secret" not in payload["error"].lower()
    assert "traceback" not in payload["error"].lower()
    assert "error" not in payload["progress"]
