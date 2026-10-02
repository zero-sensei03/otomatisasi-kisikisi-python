from __future__ import annotations

import json as json_module
import logging

import httpx
import pytest

from app.integrations.ai.exceptions import AIConfigurationError, AIProviderHTTPError
from app.integrations.ai.gemini_provider import GEMINI_ENDPOINT, GeminiProvider
from app.integrations.ai.schemas import AIGenerationRequest, QuestionDistribution
from app.main import CredentialRedactingFormatter


@pytest.fixture
def request_data() -> AIGenerationRequest:
    return AIGenerationRequest(
        title="Penjumlahan",
        subject="Matematika",
        class_name="4",
        material="Penjumlahan menggabungkan dua bilangan.",
        question_distribution=QuestionDistribution(multiple_choice=1, short_answer=0, essay=0),
    )


def test_gemini_interactions_request_and_response(monkeypatch, request_data):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-secret")
    monkeypatch.setenv("AI_MODEL", "gemini-3.1-flash-lite")
    output = {
        "summary": "Penjumlahan menggabungkan dua bilangan.",
        "questions": [
            {
                "number": 1,
                "type": "MULTIPLE_CHOICE",
                "question": "Berapakah 2 + 2?",
                "options": [
                    {"label": "A", "text": "3", "is_correct": False},
                    {"label": "B", "text": "4", "is_correct": True},
                    {"label": "C", "text": "5", "is_correct": False},
                    {"label": "D", "text": "6", "is_correct": False},
                ],
                "answer": "B",
                "explanation": "Dua ditambah dua sama dengan empat.",
            }
        ],
        "blueprint": [
            {
                "number": 1,
                "question_number": 1,
                "material_topic": "Penjumlahan",
                "learning_objective": "Menjumlahkan bilangan sederhana",
                "indicator": "Menghitung hasil penjumlahan",
                "question_type": "MULTIPLE_CHOICE",
                "cognitive_level": "C1",
                "difficulty": "EASY",
            }
        ],
    }
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, headers=kwargs["headers"], payload=kwargs["json"], timeout=kwargs["timeout"])
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "steps": [{"type": "model_output", "content": [{"type": "text", "text": json_module.dumps(output)}]}],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.integrations.ai.gemini_provider.httpx.post", fake_post)
    result = GeminiProvider().generate(request_data, generation_id="generation-test-id")

    assert captured["url"] == GEMINI_ENDPOINT
    assert captured["headers"]["x-goog-api-key"] == "unit-test-secret"
    assert captured["payload"]["model"] == "gemini-3.1-flash-lite"
    assert captured["payload"]["response_format"] == {"type": "text", "mime_type": "application/json"}
    assert captured["payload"]["store"] is False
    assert captured["timeout"] == 90
    assert result.questions[0].answer == "B"
    assert result.blueprint[0].question_number == 1


def test_gemini_http_error_preserves_provider_body_and_redacts_key(monkeypatch, request_data):
    key = "private-unit-test-key"
    monkeypatch.setenv("GEMINI_API_KEY", key)
    monkeypatch.setenv("AI_MODEL", "gemini-3.1-flash-lite")

    def fake_post(url, **_kwargs):
        return httpx.Response(
            400,
            json=[
                {
                    "error": {
                        "code": 400,
                        "status": "INVALID_ARGUMENT",
                        "message": f"Invalid request for key={key}",
                        "details": [{"field": "response_format", "reason": "BAD_FIELD"}],
                    }
                }
            ],
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.integrations.ai.gemini_provider.httpx.post", fake_post)

    with pytest.raises(AIProviderHTTPError) as captured:
        GeminiProvider().generate(request_data, generation_id="generation-test-id")

    error = captured.value
    assert error.status_code == 400
    assert error.retryable is False
    assert error.provider_error_code == 400
    assert error.provider_error_status == "INVALID_ARGUMENT"
    assert error.provider_error_message == "Invalid request for key=[REDACTED]"
    assert "BAD_FIELD" in error.provider_error_details
    assert "INVALID_ARGUMENT" in error.diagnostic
    assert "response_format" in error.response_body
    assert key not in error.diagnostic
    assert key not in error.response_body
    assert "[REDACTED]" in error.diagnostic


def test_gemini_rejects_environment_assignment_inside_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "APP_NAME=not-a-real-key")
    monkeypatch.setenv("AI_MODEL", "gemini-3.1-flash-lite")

    with pytest.raises(AIConfigurationError, match="Format GEMINI_API_KEY salah"):
        GeminiProvider()


def test_application_formatter_redacts_credentials_from_traceback():
    record = logging.LogRecord(
        name="app.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="database postgresql://deploy:db-secret@localhost/app api_key=AIza123456789012345678901234567890",
        args=(),
        exc_info=None,
    )

    rendered = CredentialRedactingFormatter("%(message)s").format(record)

    assert "db-secret" not in rendered
    assert "AIza123456789012345678901234567890" not in rendered
    assert "api_key=AIza" not in rendered
    assert "[REDACTED]" in rendered
