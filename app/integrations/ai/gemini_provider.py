import json
import logging
import re

import httpx
from pydantic import ValidationError

from app.integrations.ai.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIProviderHTTPError,
    AIResponseError,
)
from app.integrations.ai.prompts.generation_prompt import build_generation_prompt
from app.integrations.ai.schemas import AIGenerationRequest, AIGenerationResponse
from app.integrations.ai.settings import AISettings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class GeminiProvider:
    name = "gemini"

    def __init__(self):
        settings = AISettings()
        self.api_key = settings.gemini_api_key.strip()
        self.model = settings.ai_model.strip()
        logger.info("Gemini configuration model=%s api_key_configured=%s", self.model or "unset", bool(self.api_key))
        if not self.api_key:
            raise AIConfigurationError("GEMINI_API_KEY belum dikonfigurasi.")

    def generate(self, request: AIGenerationRequest, *, repair: bool = False, repair_context: dict | None = None) -> AIGenerationResponse:
        url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        input_text = build_generation_prompt(request, repair=repair, repair_context=repair_context)
        request_payload = {
            "model": self.model,
            "input": input_text,
            "response_format": {"type": "text", "mime_type": "application/json"},
            "store": False,
        }
        try:
            response = httpx.post(url, headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            }, json=request_payload, timeout=90.0)
        except httpx.HTTPError as exc:
            raise AIProviderError("Koneksi ke Gemini API gagal.") from exc

        if response.is_error:
            message = response.reason_phrase
            try:
                error_data = response.json().get("error", {})
                message = error_data.get("message") or message
            except (ValueError, AttributeError):
                pass
            message = str(message).replace(self.api_key, "[REDACTED]")
            retryable = response.status_code == 429 or response.status_code >= 500
            raise AIProviderHTTPError(
                response.status_code,
                f"Gemini API HTTP {response.status_code}: {message}",
                retryable=retryable,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AIResponseError("Gemini mengembalikan response envelope yang tidak valid.") from exc

        status = payload.get("status")
        steps = payload.get("steps", [])
        if status != "completed":
            safe_error = payload.get("error")
            if isinstance(safe_error, dict):
                safe_error = safe_error.get("message") or safe_error.get("code")
            if not isinstance(safe_error, str):
                safe_error = "tidak ada detail error"
            raise AIResponseError(f"Gemini interaction status={status}: {safe_error[:500]}")

        text_parts = [
            content["text"]
            for step in steps
            if isinstance(step, dict) and step.get("type") == "model_output"
            for content in step.get("content", [])
            if isinstance(content, dict) and content.get("type") == "text" and content.get("text")
        ]
        if not text_parts:
            step_types = [step.get("type", "unknown") for step in steps if isinstance(step, dict)]
            raise AIResponseError(f"Gemini selesai tanpa output teks (step_types={step_types}).")

        text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", "\n".join(text_parts), flags=re.IGNORECASE)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            feedback = f"JSON tidak valid pada baris {exc.lineno}, kolom {exc.colno}: {exc.msg}"
            raise AIResponseError(
                "Output Gemini bukan JSON valid.",
                repair_context={"previous_response": text, "feedback": feedback},
            ) from exc
        try:
            return AIGenerationResponse.model_validate(data)
        except ValidationError as exc:
            errors = exc.errors(include_input=False)
            feedback = "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: {item['type']}"
                for item in errors[:20]
            )
            raise AIResponseError(
                "Output Gemini tidak sesuai kontrak AI.",
                repair_context={"previous_response": text, "feedback": feedback},
            ) from exc
