import json
import logging
import platform
import re
import time
from hashlib import sha256

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
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
MAX_LOGGED_ERROR_BODY = 8_000


class GeminiProvider:
    name = "gemini"

    def __init__(self):
        settings = AISettings()
        self.api_key = settings.gemini_api_key.strip()
        self.model = settings.ai_model.strip()
        self.timeout_seconds = settings.ai_timeout_seconds
        logger.info(
            "Gemini configuration provider=gemini model=%s api_key_configured=%s api_key_length=%s "
            "sdk=REST/httpx httpx_version=%s python_version=%s endpoint=%s api_version=v1beta timeout_seconds=%s",
            self.model or "unset",
            bool(self.api_key),
            len(self.api_key),
            httpx.__version__,
            platform.python_version(),
            GEMINI_ENDPOINT,
            self.timeout_seconds,
        )
        if not self.api_key:
            raise AIConfigurationError("GEMINI_API_KEY belum dikonfigurasi.")

    def generate(self, request: AIGenerationRequest, *, repair: bool = False, repair_context: dict | None = None, generation_id: str | None = None, attempt: int = 1) -> AIGenerationResponse:
        correlation_id = generation_id or "untracked"
        logger.info("generation id=%s stage=prompt event=construction_started attempt=%s repair=%s", correlation_id, attempt, repair)
        input_text = build_generation_prompt(request, repair=repair, repair_context=repair_context)
        logger.info(
            "generation id=%s stage=prompt event=constructed character_count=%s sha256=%s "
            "prompt_preview=%r preview_scope=static_instructions_only",
            correlation_id,
            len(input_text),
            sha256(input_text.encode("utf-8")).hexdigest(),
            input_text.partition("Input:")[0][:1_000],
        )
        request_payload = {
            "model": self.model,
            "input": input_text,
            "response_format": {"type": "text", "mime_type": "application/json"},
            "store": False,
        }
        logger.info(
            "generation id=%s stage=ai_request event=request_configuration attempt=%s endpoint=%s api_version=v1beta "
            "provider=gemini model=%s sdk=REST/httpx httpx_version=%s timeout_seconds=%s "
            "prompt_character_count=%s system_instruction=none generation_config=none tools=none safety_settings=none "
            "response_format=%s structured_schema=none post_response_schema_validation=Pydantic request_fields=%s",
            correlation_id,
            attempt,
            GEMINI_ENDPOINT,
            self.model,
            httpx.__version__,
            self.timeout_seconds,
            len(input_text),
            json.dumps(request_payload["response_format"], separators=(",", ":")),
            ",".join(request_payload.keys()),
        )
        logger.info("generation id=%s stage=ai_request event=request_started attempt=%s", correlation_id, attempt)
        request_started = time.perf_counter()
        try:
            response = httpx.post(GEMINI_ENDPOINT, headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            }, json=request_payload, timeout=self.timeout_seconds)
        except httpx.HTTPError as exc:
            duration_ms = int((time.perf_counter() - request_started) * 1000)
            logger.exception(
                "generation id=%s stage=ai_request event=transport_exception provider=gemini model=%s "
                "endpoint=%s request_duration_ms=%s exception_type=%s",
                correlation_id,
                self.model,
                GEMINI_ENDPOINT,
                duration_ms,
                type(exc).__name__,
            )
            raise AIProviderError(f"Koneksi ke Gemini API gagal ({type(exc).__name__}).") from exc

        duration_ms = int((time.perf_counter() - request_started) * 1000)
        metadata = {
            "content_type": response.headers.get("content-type"),
            "request_id": response.headers.get("x-request-id") or response.headers.get("x-goog-request-id"),
            "server": response.headers.get("server"),
        }
        logger.info(
            "generation id=%s stage=ai_request event=response_received attempt=%s provider=gemini model=%s "
            "endpoint=%s http_status=%s request_duration_ms=%s response_metadata=%s",
            correlation_id,
            attempt,
            self.model,
            GEMINI_ENDPOINT,
            response.status_code,
            duration_ms,
            json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
        )

        if response.is_error:
            raw_body = response.text
            parsed_error = None
            try:
                parsed_error = response.json()
            except ValueError:
                pass
            provider_error = self._extract_provider_error(parsed_error)
            message = self._redact_secrets(self._one_line(str(provider_error.get("message") or provider_error.get("detail") or response.reason_phrase)))
            safe_raw_body = self._redact_secrets(raw_body)[:MAX_LOGGED_ERROR_BODY]
            error_details = self._redact_secrets(json.dumps(provider_error.get("details") or provider_error.get("errors"), ensure_ascii=False, default=str))
            detail_entries = provider_error.get("details") or provider_error.get("errors") or []
            detail_type = next((item.get("@type") or item.get("type") for item in detail_entries if isinstance(item, dict) and (item.get("@type") or item.get("type"))), None) if isinstance(detail_entries, list) else None
            error_info = next((item for item in detail_entries if isinstance(item, dict) and item.get("reason")), {}) if isinstance(detail_entries, list) else {}
            diagnostic_data = {
                "provider_error_type": provider_error.get("type") or provider_error.get("@type") or detail_type,
                "provider_error_code": provider_error.get("code"),
                "provider_error_status": provider_error.get("status"),
                "provider_error_reason": error_info.get("reason"),
                "provider_error_message": message,
                "provider_error_details": error_details,
                "response_metadata": metadata,
                "response_body": safe_raw_body,
                "response_body_truncated": len(raw_body) > MAX_LOGGED_ERROR_BODY,
            }
            diagnostic = json.dumps(diagnostic_data, ensure_ascii=False, default=str, separators=(",", ":"))
            retryable = response.status_code == 429 or response.status_code >= 500
            logger.error(
                "generation id=%s stage=ai_request event=provider_http_error attempt=%s provider=gemini model=%s "
                "endpoint=%s attempt_duration_ms=%s status_code=%s provider_error_code=%s "
                "provider_error_status=%s provider_error_message=%s provider_error_details=%s "
                "response_body=%s response_metadata=%s",
                correlation_id,
                attempt,
                self.model,
                GEMINI_ENDPOINT,
                duration_ms,
                response.status_code,
                provider_error.get("code"),
                provider_error.get("status"),
                self._one_line(str(message)),
                self._one_line(error_details),
                json.dumps(safe_raw_body, ensure_ascii=False),
                json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
            )
            raise AIProviderHTTPError(
                response.status_code,
                f"Gemini API HTTP {response.status_code}: {self._one_line(str(message))[:500]}",
                retryable=retryable,
                diagnostic=diagnostic,
                response_body=safe_raw_body,
                response_metadata=metadata,
                request_duration_ms=duration_ms,
                provider_error_type=provider_error.get("type") or provider_error.get("@type") or detail_type,
                provider_error_code=provider_error.get("code"),
                provider_error_status=provider_error.get("status"),
                provider_error_message=message,
                provider_error_details=error_details,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            logger.exception("generation id=%s stage=response_parsing event=invalid_json status_code=%s body_character_count=%s", correlation_id, response.status_code, len(response.text))
            raise AIResponseError("Gemini mengembalikan response envelope yang tidak valid.") from exc

        status = payload.get("status")
        steps = payload.get("steps", [])
        logger.info(
            "generation id=%s stage=response_parsing event=envelope_parsed status=%s step_count=%s "
            "response_fields=%s interaction_id=%s response_model=%s usage=%s request_duration_ms=%s",
            correlation_id,
            status,
            len(steps) if isinstance(steps, list) else "invalid",
            ",".join(payload.keys()) if isinstance(payload, dict) else "non-object",
            payload.get("id") if isinstance(payload, dict) else None,
            payload.get("model") if isinstance(payload, dict) else None,
            json.dumps(payload.get("usage"), ensure_ascii=False, separators=(",", ":")) if isinstance(payload, dict) and payload.get("usage") is not None else "none",
            duration_ms,
        )
        if status != "completed":
            safe_error = self._redact_secrets(json.dumps(payload.get("errors") or payload.get("error") or {}, ensure_ascii=False, default=str))[:3000]
            logger.error("generation id=%s stage=response_parsing event=interaction_not_completed status=%s errors=%s", correlation_id, status, safe_error)
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
        logger.info("generation id=%s stage=response_parsing event=text_extracted character_count=%s", correlation_id, len(text))
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            feedback = f"JSON tidak valid pada baris {exc.lineno}, kolom {exc.colno}: {exc.msg}"
            logger.exception("generation id=%s stage=json_parsing event=invalid_json response_character_count=%s", correlation_id, len(text))
            raise AIResponseError(
                "Output Gemini bukan JSON valid.",
                repair_context={"previous_response": text, "feedback": feedback},
            ) from exc
        try:
            result = AIGenerationResponse.model_validate(data)
            logger.info("generation id=%s stage=response_validation event=valid question_count=%s blueprint_count=%s", correlation_id, len(result.questions), len(result.blueprint))
            return result
        except ValidationError as exc:
            errors = exc.errors(include_input=False)
            feedback = "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: {item['type']}"
                for item in errors[:20]
            )
            logger.error("generation id=%s stage=response_validation event=invalid fields=%s", correlation_id, feedback)
            raise AIResponseError(
                "Output Gemini tidak sesuai kontrak AI.",
                repair_context={"previous_response": text, "feedback": feedback},
            ) from exc

    def _redact_secrets(self, value: str) -> str:
        safe = value.replace(self.api_key, "[REDACTED]") if self.api_key else value
        safe = re.sub(r"(?i)(x-goog-api-key\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", safe)
        safe = re.sub(r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", safe)
        safe = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+", r"\1[REDACTED]", safe)
        return safe

    @staticmethod
    def _extract_provider_error(payload) -> dict:
        """Normalize Gemini/proxy error bodies returned as objects or arrays."""
        if isinstance(payload, list):
            for item in payload:
                error = GeminiProvider._extract_provider_error(item)
                if error:
                    return error
            return {}
        if not isinstance(payload, dict):
            return {}
        nested_error = payload.get("error")
        if isinstance(nested_error, dict):
            return nested_error
        if isinstance(nested_error, list):
            return GeminiProvider._extract_provider_error(nested_error)
        if any(field in payload for field in ("code", "message", "status", "details", "errors", "detail")):
            return payload
        return {}

    @staticmethod
    def _one_line(value: str) -> str:
        return " ".join(value.split())
