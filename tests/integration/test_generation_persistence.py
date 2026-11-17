from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from starlette.datastructures import Headers, UploadFile

from app.integrations.ai.exceptions import AIConfigurationError
from app.integrations.ai.schemas import AIGenerationResponse
from app.models.generation import Generation, GenerationSetting, GenerationStatus
from app.models.user import User, UserRole
from app.schemas.generation import GenerationCreateSchema
from app.services.generation_service import GenerationService


def seed_generation_settings(db_session):
    db_session.add_all([
        GenerationSetting(key="generation.enabled", value="true"),
        GenerationSetting(key="generation.max_questions_per_generate", value="5"),
        GenerationSetting(key="generation.free_limit", value="5"),
        GenerationSetting(key="generation.max_material_characters", value="5000"),
        GenerationSetting(key="generation.max_reference_characters", value="1000"),
        GenerationSetting(key="generation.cost_per_generate", value="0.25"),
    ])
    user = User(email="teacher@example.test", full_name="Guru Uji", password_hash="not-used", role=UserRole.GURU)
    db_session.add(user)
    db_session.commit()
    return user


def valid_ai_result():
    return AIGenerationResponse.model_validate({
        "summary": "Penjumlahan menggabungkan dua bilangan.",
        "questions": [{
            "number": 1,
            "type": "MULTIPLE_CHOICE",
            "cognitive_level": "C1",
            "question": "Berapakah 2 + 2?",
            "options": [
                {"label": "A", "text": "3", "is_correct": False},
                {"label": "B", "text": "4", "is_correct": True},
                {"label": "C", "text": "5", "is_correct": False},
                {"label": "D", "text": "6", "is_correct": False},
            ],
            "answer": "B",
            "explanation": "Sumber menjelaskan hasilnya empat.",
        }],
        "blueprint": [{
            "number": 1,
            "question_number": 1,
            "material_topic": "Penjumlahan",
            "learning_objective": "Mengingat hasil penjumlahan",
            "indicator": "Mengidentifikasi hasil penjumlahan",
            "question_type": "MULTIPLE_CHOICE",
            "cognitive_level": "C1",
            "difficulty": "EASY",
        }],
    })


def create_data():
    return GenerationCreateSchema(
        title="Operasi Bilangan",
        subject="Matematika",
        class_name="4",
        type_materi="TEXT",
        materi_text="Penjumlahan menggabungkan dua bilangan.",
        cognitive_levels=["C1"],
        total_multiple_choice=1,
    )


def test_generation_service_persists_questions_blueprint_duration_and_summary(db_session, monkeypatch):
    user = seed_generation_settings(db_session)

    class FakeProvider:
        name = "gemini-test"
        model = "fake-model"

        def generate(self, *_args, **_kwargs):
            return valid_ai_result()

    monkeypatch.setattr("app.services.generation_service.AIProviderFactory.create", lambda: FakeProvider())
    generation = GenerationService(db_session).create(create_data(), user)

    persisted = db_session.get(Generation, generation.id)
    assert persisted.status == GenerationStatus.COMPLETED
    assert persisted.summary == "Penjumlahan menggabungkan dua bilangan."
    assert persisted.ai_duration_ms is not None and persisted.ai_duration_ms >= 0
    assert len(persisted.questions) == 1
    assert persisted.questions[0].cognitive_level == "C1"
    assert persisted.questions[0].options[1].is_correct is True
    assert len(persisted.blueprints) == 1
    assert persisted.blueprints[0].cognitive_level == "C1"
    assert json.loads(persisted.progress_json)["status"] == "COMPLETED"


def test_generation_repairs_invalid_ai_result_once_then_saves_valid_result(db_session, monkeypatch):
    user = seed_generation_settings(db_session)

    class RepairingProvider:
        name = "gemini-test"
        model = "fake-model"

        def __init__(self):
            self.calls = []

        def generate(self, _request, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return AIGenerationResponse.model_validate({"summary": "Ringkasan", "questions": [], "blueprint": []})
            return valid_ai_result()

    provider = RepairingProvider()
    monkeypatch.setattr("app.services.generation_service.AIProviderFactory.create", lambda: provider)
    generation = GenerationService(db_session).create(create_data(), user)

    assert generation.status == GenerationStatus.COMPLETED
    assert len(generation.questions) == 1
    assert len(provider.calls) == 2
    assert provider.calls[0]["repair"] is False
    assert provider.calls[1]["repair"] is True
    assert provider.calls[1]["repair_context"]["feedback"]


def test_generation_provider_failure_is_persisted_as_safe_failed_generation(db_session, monkeypatch):
    user = seed_generation_settings(db_session)

    class FailingProvider:
        name = "gemini-test"
        model = "fake-model"

        def generate(self, *_args, **_kwargs):
            raise AIConfigurationError("private credential diagnostic")

    monkeypatch.setattr("app.services.generation_service.AIProviderFactory.create", lambda: FailingProvider())
    generation = GenerationService(db_session).create(create_data(), user)

    persisted = db_session.get(Generation, generation.id)
    assert persisted.status == GenerationStatus.FAILED
    assert "Autentikasi layanan AI gagal" in persisted.error_message
    assert "private credential diagnostic" not in persisted.error_message
    assert persisted.ai_duration_ms is None
    assert persisted.material_text == "Penjumlahan menggabungkan dua bilangan."
    assert json.loads(persisted.progress_json)["status"] == "FAILED"


@pytest.mark.parametrize("reference_content", ["Referensi tambahan", None])
def test_file_generation_extracts_and_stores_material_with_reference_outcome(db_session, monkeypatch, tmp_path, reference_content):
    user = seed_generation_settings(db_session)
    primary_pdf = b"%PDF-1.7\nstream\n(Materi utama PDF) Tj\nendstream"

    class FakeProvider:
        name = "gemini-test"
        model = "fake-model"

        def generate(self, request, **_kwargs):
            self.references = request.references
            return valid_ai_result()

    provider = FakeProvider()
    monkeypatch.setattr("app.services.generation_service.AIProviderFactory.create", lambda: provider)
    monkeypatch.setattr("app.services.generation_service.get_settings", lambda: type("Settings", (), {"max_upload_size": 1_000_000, "storage_path": str(tmp_path)})())
    monkeypatch.setattr(
        "app.services.generation_service.ReferenceContentService.fetch",
        lambda _self, _url, _limit: (reference_content, "Sumber", None if reference_content else "Referensi timeout."),
    )
    upload = UploadFile(
        filename="materi.pdf",
        file=BytesIO(primary_pdf),
        size=len(primary_pdf),
        headers=Headers({"content-type": "application/pdf"}),
    )
    data = GenerationCreateSchema(
        title="Materi PDF",
        subject="Matematika",
        class_name="4",
        type_materi="FILE",
        references=["https://source.example/item"],
        cognitive_levels=["C1"],
        total_multiple_choice=1,
    )

    generation = GenerationService(db_session).create(data, user, upload=upload)
    persisted = db_session.get(Generation, generation.id)

    assert persisted.status == GenerationStatus.COMPLETED
    assert "Materi utama PDF" in persisted.material_text
    assert persisted.material_file_path is not None
    assert Path(persisted.material_file_path).is_file()
    assert len(persisted.references) == 1
    assert persisted.references[0].extraction_status == ("SUCCESS" if reference_content else "FAILED")
    assert len(provider.references) == (1 if reference_content else 0)
