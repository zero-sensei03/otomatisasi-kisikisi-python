from __future__ import annotations

import pytest

from app.integrations.ai.exceptions import AIConfigurationError
from app.integrations.ai.factory import AIProviderFactory


@pytest.mark.parametrize(
    ("provider", "message"),
    [("openai", "OpenAI belum dikonfigurasi"), ("unknown", "AI_PROVIDER tidak didukung")],
)
def test_factory_rejects_unavailable_ai_providers(monkeypatch, provider, message):
    monkeypatch.setattr("app.integrations.ai.factory.AISettings", lambda: type("Settings", (), {"ai_provider": provider})())
    with pytest.raises(AIConfigurationError, match=message):
        AIProviderFactory.create()


def test_factory_creates_gemini_provider(monkeypatch):
    marker = object()
    monkeypatch.setattr("app.integrations.ai.factory.AISettings", lambda: type("Settings", (), {"ai_provider": " GEMINI "})())
    monkeypatch.setattr("app.integrations.ai.factory.GeminiProvider", lambda: marker)
    assert AIProviderFactory.create() is marker
