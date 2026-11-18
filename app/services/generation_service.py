from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.cognitive_levels import ACTIVE_COGNITIVE_LEVELS
from app.integrations.ai.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIProviderHTTPError,
    AIResponseError,
)
from app.integrations.ai.factory import AIProviderFactory
from app.integrations.ai.schemas import AIGenerationRequest, QuestionDistribution
from app.integrations.material.extractor import MaterialExtractor
from app.integrations.references.content_service import ReferenceContentService
from app.models.generation import (
    Generation,
    GenerationBlueprint,
    GenerationQuestion,
    GenerationQuestionOption,
    GenerationQuestionType,
    GenerationReference,
    GenerationStatus,
    GenerationUsage,
    MaterialType,
)
from app.models.user import User
from app.repositories.generation_repository import (
    GenerationRepository,
    GenerationSettingRepository,
)
from app.schemas.generation import GenerationCreateSchema
from app.services.audit_service import AuditService
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def log_generation_event(generation_id, stage: str, event: str, **metadata) -> None:
    fields = " ".join(f"{key}={value}" for key, value in metadata.items())
    failed = event == "failed" or (event == "finished" and metadata.get("status") == "FAILED")
    logger.log(
        logging.ERROR if failed else logging.INFO,
        "[GEN:%s] Stage: %s - %s%s",
        str(generation_id),
        stage,
        event,
        f" {fields}" if fields else "",
    )


def truncate_material(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    raise ValueError(
        f"Materi berisi {len(text):,} karakter, melebihi batas {limit:,}. "
        "Ringkas atau pecah materi lalu unggah kembali agar tidak ada bagian sumber yang terlewat."
    )


def _read_progress(value: str | None) -> dict:
    try:
        payload = json.loads(value or "{}")
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def generation_user_error(exc: Exception, *, stage: str | None = None) -> str:
    """Map internal generation failures to safe, actionable user-facing text."""
    if isinstance(exc, AIConfigurationError):
        return "Autentikasi layanan AI gagal. Periksa konfigurasi API key atau hubungi administrator."
    if isinstance(exc, AIProviderHTTPError):
        provider_status = " ".join(
            str(value or "")
            for value in (
                exc.provider_error_status,
                exc.provider_error_code,
                exc.provider_error_type,
                exc.provider_error_message,
            )
        ).lower()
        if exc.status_code == 429 or any(term in provider_status for term in ("quota", "resource_exhausted", "rate_limit")):
            return "Kuota atau batas penggunaan layanan AI telah tercapai. Coba kembali nanti atau hubungi administrator."
        if exc.status_code in {401, 403} or any(term in provider_status for term in ("api_key_invalid", "invalid api key", "api key not valid", "unauthenticated")):
            return "Autentikasi layanan AI gagal. Periksa konfigurasi API key atau hubungi administrator."
        if exc.status_code in {408, 504}:
            return "Layanan AI tidak memberikan respons dalam batas waktu yang ditentukan. Coba kembali."
        if exc.status_code >= 500:
            return "Layanan AI sedang mengalami gangguan. Coba kembali beberapa saat lagi."
        return "Layanan AI menolak permintaan. Periksa materi dan pengaturan generation, lalu coba kembali."
    if isinstance(exc, AIResponseError):
        return "Respons AI tidak sesuai dengan format yang diharapkan. Coba kembali; jika berulang, hubungi administrator."
    if isinstance(exc, AIProviderError):
        cause = exc.__cause__
        if isinstance(cause, (TimeoutError,)) or (cause and "timeout" in type(cause).__name__.lower()):
            return "Layanan AI tidak memberikan respons dalam batas waktu yang ditentukan. Coba kembali."
        return "Tidak dapat terhubung ke layanan AI. Periksa koneksi lalu coba kembali."
    if isinstance(exc, SQLAlchemyError):
        return "Terjadi kegagalan saat menyimpan hasil generation. Silakan coba kembali."
    if isinstance(exc, HTTPException) and exc.status_code == 404:
        return "File atau sumber materi tidak ditemukan. Periksa kembali materi yang digunakan."
    if isinstance(exc, ValueError) and "kuota" in str(exc).lower():
        return "Kuota generation Anda sudah habis. Hubungi administrator jika Anda memerlukan tambahan kuota."
    if stage in {"material_file_validation", "material_file_extraction"}:
        return "Sistem gagal membaca atau memproses file sumber materi. Pastikan file tidak kosong, tidak rusak, dan menggunakan format yang didukung."
    if stage in {"material_settings", "material_validation"}:
        return "Materi tidak memenuhi validasi yang diperlukan. Periksa isi dan batas ukuran materi, lalu coba kembali."
    return "Generation gagal pada tahap pemrosesan. Periksa materi lalu coba kembali. Jika masalah berulang, hubungi administrator dengan ID generation."


def generation_error_title(message: str | None) -> str:
    text = (message or "").lower()
    if "autentikasi layanan ai" in text:
        return "Autentikasi layanan AI gagal"
    if "kuota" in text or "batas penggunaan layanan ai" in text:
        return "Kuota layanan AI tercapai"
    if "batas waktu" in text or "timeout" in text:
        return "Layanan AI mengalami timeout"
    if "file" in text or "materi" in text or "sumber materi" in text:
        return "Sumber materi bermasalah"
    if "respons ai" in text or "format" in text:
        return "Hasil AI tidak valid"
    if "menyimpan hasil" in text:
        return "Penyimpanan generation gagal"
    if "terhubung ke layanan ai" in text or "gangguan" in text:
        return "Layanan AI tidak tersedia"
    return "Generation gagal diproses"


def generation_progress_error(message: str | None, *, stage: str | None = None) -> str:
    """Return a safe, canonical error for a confirmed FAILED progress record.

    Older rows may contain a raw exception string. Classify it without ever
    returning that string to the browser.
    """
    text = (message or "").lower()
    if any(term in text for term in ("autentikasi layanan ai", "invalid api key", "api_key_invalid", "api key not valid")):
        return "Autentikasi layanan AI gagal. Periksa konfigurasi API key atau hubungi administrator."
    if any(term in text for term in ("kuota", "quota", "resource_exhausted", "rate_limit")):
        return "Kuota atau batas penggunaan layanan AI telah tercapai. Coba kembali nanti atau hubungi administrator."
    if any(term in text for term in ("timeout", "timed out", "batas waktu")):
        return "Layanan AI tidak memberikan respons dalam batas waktu yang ditentukan. Coba kembali."
    if any(term in text for term in ("respons ai", "response validation", "format yang diharapkan", "output tidak valid")):
        return "Respons AI tidak sesuai dengan format yang diharapkan. Coba kembali; jika berulang, hubungi administrator."
    if any(term in text for term in ("database", "sqlalchemy", "sql error", "menyimpan hasil", "persistence")):
        return "Terjadi kegagalan saat menyimpan hasil generation. Silakan coba kembali."
    if any(term in text for term in ("file", "pdf", "docx", "extract", "ekstrak")):
        return "Sistem gagal membaca atau memproses file sumber materi. Pastikan file tidak kosong, tidak rusak, dan menggunakan format yang didukung."
    if any(term in text for term in ("materi", "karakter", "kosong", "validasi")):
        return "Materi tidak memenuhi validasi yang diperlukan. Periksa isi dan batas ukuran materi, lalu coba kembali."

    stage_messages = {
        "gemini": "Tidak dapat terhubung ke layanan AI. Periksa koneksi lalu coba kembali.",
        "output_validation": "Respons AI tidak sesuai dengan format yang diharapkan. Coba kembali; jika berulang, hubungi administrator.",
        "file_extraction": "Sistem gagal membaca atau memproses file sumber materi. Pastikan file tidak kosong, tidak rusak, dan menggunakan format yang didukung.",
        "material_validation": "Materi tidak memenuhi validasi yang diperlukan. Periksa isi dan batas ukuran materi, lalu coba kembali.",
        "database_persistence": "Terjadi kegagalan saat menyimpan hasil generation. Silakan coba kembali.",
    }
    return stage_messages.get(stage or "", "Generation gagal pada tahap pemrosesan. Periksa materi lalu coba kembali. Jika masalah berulang, hubungi administrator dengan ID generation.")


class GenerationService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = GenerationRepository(db)
        self.settings = GenerationSettingRepository(db)
        self.audit = AuditService(db)

    def setting(self, key):
        value = self.settings.get(key)
        if value is None:
            raise HTTPException(status_code=503, detail="Pengaturan generation belum tersedia.")
        return value

    def quota(self, user_id):
        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        usage_filter = (GenerationUsage.user_id == user_id, GenerationUsage.created_at >= day_start, GenerationUsage.created_at < day_end)
        used = self.db.scalar(select(func.coalesce(func.sum(GenerationUsage.free_generation_used), 0)).where(*usage_filter)) or 0
        cost = self.db.scalar(select(func.coalesce(func.sum(GenerationUsage.cost), 0)).where(*usage_filter)) or 0
        limit = int(self.setting("generation.free_limit"))
        return {"used": int(used), "limit": limit, "remaining": max(0, limit - int(used)), "cost": float(cost)}

    def list(self, user, *, page=1, per_page=20, search=None, status=None):
        rows, total = self.repository.list_owned(None if user.role.value == "ADMIN" else user.id, page=page, per_page=per_page, search=search, status=status)
        return rows, total

    def detail(self, generation_id, user):
        generation = self.repository.get_any(generation_id) if user.role.value == "ADMIN" else self.repository.get_owned(generation_id, user.id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation tidak ditemukan.")
        return generation

    def validate_start(self, data: GenerationCreateSchema, user: User, *, upload=None) -> None:
        if self.setting("generation.enabled").lower() != "true":
            raise HTTPException(status_code=403, detail="Fitur generation sedang tidak tersedia.")
        total = data.total_multiple_choice + data.total_short_answer + data.total_essay
        if total > int(self.setting("generation.max_questions_per_generate")):
            raise HTTPException(status_code=422, detail="Jumlah soal melebihi batas per generation.")
        if self.quota(user.id)["remaining"] < 1:
            raise HTTPException(status_code=403, detail="Kuota generation Anda sudah habis.")
        if data.type_materi == "FILE" and upload is None:
            raise HTTPException(status_code=422, detail="File materi wajib diunggah.")

    @staticmethod
    def failed_progress(progress_json: str | None, *, stage: str, message: str, duration_ms: int | None = None) -> str:
        progress = _read_progress(progress_json)
        now = datetime.now(UTC)
        progress.update(status="FAILED", current_stage=stage, error=message, updated_at=now.isoformat(), completed_at=now.isoformat())
        if progress.get("started_at"):
            try:
                started = datetime.fromisoformat(progress["started_at"])
                progress["total_duration_ms"] = max(0, int((now - started).total_seconds() * 1000))
            except (TypeError, ValueError):
                pass
        for item in progress.get("stages", []):
            if item.get("id") == stage and item.get("status") == "PROCESSING":
                item["status"] = "FAILED"
                item["message"] = message
                if duration_ms is not None:
                    item["duration_ms"] = max(0, int(duration_ms))
        return json.dumps(progress, ensure_ascii=False)

    def _progress(self, generation: Generation, stage: str, state: str, *, duration_ms=None, message=None, **details) -> None:
        progress = _read_progress(generation.progress_json)
        stages = progress.setdefault("stages", [])
        item = next((candidate for candidate in stages if candidate.get("id") == stage), None)
        now = datetime.now(UTC).isoformat()
        if item is None:
            item = {"id": stage, "status": state, "started_at": now}
            stages.append(item)
        item["status"] = state
        item["updated_at"] = now
        if duration_ms is not None:
            item["duration_ms"] = max(0, int(duration_ms))
        if message:
            item["message"] = message
        if details:
            item["details"] = details
        progress.update(
            status=generation.status.value,
            current_stage=stage,
            updated_at=now,
            started_at=generation.started_at.isoformat() if generation.started_at else None,
            total_duration_ms=(int((datetime.now(UTC) - generation.started_at).total_seconds() * 1000) if generation.started_at else None),
        )
        generation.progress_json = json.dumps(progress, ensure_ascii=False)
        self.db.commit()

    def create(self, data: GenerationCreateSchema, user: User, *, upload=None, ip_address=None, user_agent=None, existing_generation=None, generation_id=None):
        total_started = time.perf_counter()
        generation_id = existing_generation.id if existing_generation else generation_id or "not-created"
        log_generation_event(generation_id, "request_initialization", "started", user_id=user.id, input_type=data.type_materi, reference_count=len(data.references), cognitive_levels=','.join(data.cognitive_levels), retry=bool(existing_generation))
        try:
            if self.setting("generation.enabled").lower() != "true":
                raise HTTPException(status_code=403, detail="Fitur generation sedang tidak tersedia.")
            distribution = {"multiple_choice": data.total_multiple_choice, "short_answer": data.total_short_answer, "essay": data.total_essay}
            total = sum(distribution.values())
            maximum_questions = int(self.setting("generation.max_questions_per_generate"))
            log_generation_event(generation_id, "preflight", "settings_loaded", maximum_questions=maximum_questions)
            if total > maximum_questions:
                raise HTTPException(status_code=422, detail="Jumlah soal melebihi batas per generation.")
            quota = self.quota(user.id)
            log_generation_event(generation_id, "preflight", "quota_checked", remaining=quota["remaining"])
            if quota["remaining"] < 1:
                raise HTTPException(status_code=403, detail="Kuota generation Anda sudah habis.")
            if data.type_materi == "FILE" and upload is None:
                raise HTTPException(status_code=422, detail="File materi wajib diunggah.")
            log_generation_event(generation_id, "preflight", "completed", material_type=data.type_materi, question_count=total)
        except Exception as exc:
            log_generation_event(
                generation_id,
                "preflight",
                "failed",
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", "-"),
                file_name=Path(upload.filename or "materi").name if upload is not None else "-",
                mime_type=upload.content_type or "unknown" if upload is not None else "-",
                file_size=upload.size or 0 if upload is not None else 0,
            )
            raise
        generation = existing_generation
        if generation is None:
            generation = Generation(id=generation_id if generation_id != "not-created" else None, user_id=user.id, title=data.title.strip(), description=data.description, subject=data.subject.strip(), class_name=data.class_name.strip(), type_materi=MaterialType(data.type_materi), material_text="", status=GenerationStatus.PENDING, total_multiple_choice=data.total_multiple_choice, total_short_answer=data.total_short_answer, total_essay=data.total_essay, total_questions=total, cognitive_levels=json.dumps(data.cognitive_levels), progress_json=json.dumps({"status": "PENDING", "stages": [], "input_type": data.type_materi, "reference_count": len(data.references)}))
            self.repository.add(generation)
            self.audit.log(action="GENERATION_CREATED", feature="GENERATION", user_id=user.id, resource="GENERATION", resource_id=str(generation.id), ip_address=ip_address, user_agent=user_agent)
        else:
            generation.status = GenerationStatus.PENDING
            generation.error_message = None
            generation.summary = None
            generation.questions.clear()
            generation.blueprints.clear()
            generation.references.clear()
            generation.cognitive_levels = json.dumps(data.cognitive_levels)
        self.db.commit()
        log_generation_event(generation.id, "database", "pending_saved")
        self.audit.log(action="GENERATION_STARTED", feature="GENERATION", user_id=user.id, resource="GENERATION", resource_id=str(generation.id), ip_address=ip_address, user_agent=user_agent)
        generation.status = GenerationStatus.PROCESSING
        generation.started_at = datetime.now(UTC)
        generation.ai_duration_ms = None
        self.db.commit()
        log_generation_event(generation.id, "database", "processing_saved")
        self._progress(generation, "request_initialization", "SUCCESS")
        stage = "material_settings"
        file_byte_count = 0
        stage_started = time.perf_counter()
        active_progress_stage = "material_validation"
        try:
            log_generation_event(generation.id, stage, "started")
            self._progress(generation, "material_validation", "PROCESSING")
            maximum_material = int(self.setting("generation.max_material_characters"))
            file_name = file_mime = None
            if data.type_materi == "TEXT":
                material = "\n".join(line.strip() for line in (data.materi_text or "").splitlines() if line.strip())
                material = truncate_material(material, maximum_material)
                log_generation_event(generation.id, "material", "text_ready", character_count=len(material), length_validated=True)
                self._progress(generation, "material_validation", "SUCCESS", duration_ms=(time.perf_counter() - stage_started) * 1000, character_count=len(material))
            else:
                stage = "material_file_validation"
                active_progress_stage = "material_validation"
                stage_started = time.perf_counter()
                log_generation_event(generation.id, stage, "started", file_name=Path(upload.filename or "materi").name, mime_type=upload.content_type or "unknown", file_size=upload.size or 0)
                maximum_file_size = get_settings().max_upload_size
                if upload.size is not None and upload.size > maximum_file_size:
                    raise ValueError("File kosong atau melebihi batas ukuran.")
                upload.file.seek(0)
                file_bytes = upload.file.read(maximum_file_size + 1)
                file_byte_count = len(file_bytes)
                if not file_bytes:
                    raise ValueError("File materi kosong.")
                self._progress(generation, "material_validation", "SUCCESS", duration_ms=(time.perf_counter() - stage_started) * 1000, file_size=file_byte_count)
                self._progress(generation, "file_extraction", "PROCESSING", file_name=Path(upload.filename or "materi").name, mime_type=upload.content_type or "unknown", file_size=file_byte_count)
                stage = "material_file_extraction"
                active_progress_stage = "file_extraction"
                extraction_started = time.perf_counter()
                try:
                    extracted = MaterialExtractor().extract(upload.filename or "materi", upload.content_type or "", file_bytes, maximum_file_size)
                except ValueError as exc:
                    log_generation_event(generation.id, stage, "failed", file_name=Path(upload.filename or "materi").name, mime_type=upload.content_type or "unknown", byte_count=file_byte_count, duration_ms=int((time.perf_counter() - extraction_started) * 1000), error_type=type(exc).__name__)
                    raise
                material, file_name, file_mime = truncate_material(extracted.text, maximum_material), extracted.filename, extracted.mime_type
                extraction_duration = (time.perf_counter() - extraction_started) * 1000
                log_generation_event(generation.id, stage, "completed", file_name=file_name, mime_type=file_mime, byte_count=file_byte_count, character_count=len(material), estimated_tokens=(len(material) + 3) // 4, duration_ms=int(extraction_duration))
                self._progress(generation, "file_extraction", "SUCCESS", duration_ms=extraction_duration, character_count=len(material), estimated_tokens=(len(material) + 3) // 4, pages=MaterialExtractor.page_count(file_bytes, file_name))
                stage = "material_file_storage"
                storage_root = Path(get_settings().storage_path) / "generation_private"
                storage_root.mkdir(mode=0o700, parents=True, exist_ok=True)
                storage_root.chmod(0o700)
                storage_file = storage_root / f"{uuid.uuid4().hex}{Path(file_name).suffix.lower()}"
                storage_file.write_bytes(file_bytes)
                storage_file.chmod(0o600)
                generation.material_file_name = file_name
                generation.material_file_path = str(storage_file)
                generation.material_file_mime_type = file_mime
                log_generation_event(generation.id, stage, "completed")
            generation.material_text = material
            if not material.strip():
                raise ValueError("Materi tidak memiliki teks yang dapat diproses. Periksa isi file atau materi yang dimasukkan.")
            references, reference_texts = [], []
            stage = "references"
            active_progress_stage = "references"
            stage_started = time.perf_counter()
            if data.references:
                self._progress(generation, "references", "PROCESSING", reference_count=len(data.references))
            reference_limit = int(self.setting("generation.max_reference_characters"))
            log_generation_event(generation.id, stage, "started", reference_count=len(data.references))
            for index, url in enumerate(data.references, start=1):
                if not url.strip():
                    continue
                reference_started = time.perf_counter()
                safe_url = ReferenceContentService.safe_log_url(url.strip())
                log_generation_event(generation.id, stage, "fetch_started", reference_index=index, url=safe_url)
                content, title, error = ReferenceContentService().fetch(url.strip(), reference_limit)
                references.append(GenerationReference(generation_id=generation.id, url=url.strip(), title=title, extracted_content=content, extraction_status="SUCCESS" if content else "FAILED", error_message=error))
                if content:
                    reference_texts.append(f"URL: {url.strip()}\n{content}")
                log_generation_event(generation.id, stage, "fetch_completed", reference_index=index, url=safe_url, result="success" if content else "failed", error=error if not content else "none", character_count=len(content or ""), duration_ms=int((time.perf_counter() - reference_started) * 1000))
            self.db.add_all(references)
            # Keep source material available if provider setup or generation fails,
            # so the user can retry the failed generation later.
            self.db.commit()
            log_generation_event(generation.id, "references", "saved", successful_count=len(reference_texts))
            if data.references:
                self._progress(generation, "references", "SUCCESS", duration_ms=(time.perf_counter() - stage_started) * 1000, successful_count=len(reference_texts), failed_count=len(data.references) - len(reference_texts))
            stage = "ai_request"
            preparation_started = time.perf_counter()
            active_progress_stage = "ai_preparation"
            log_generation_event(generation.id, stage, "building")
            request = AIGenerationRequest(title=data.title, description=data.description or "", subject=data.subject, class_name=data.class_name, material=material, references=reference_texts, cognitive_levels=data.cognitive_levels, question_distribution=QuestionDistribution(**distribution))
            from app.integrations.ai.prompts.generation_prompt import build_generation_prompt
            prompt = build_generation_prompt(request)
            self._progress(generation, "ai_preparation", "SUCCESS", duration_ms=(time.perf_counter() - preparation_started) * 1000, prompt_characters=len(prompt), estimated_tokens=(len(prompt) + 3) // 4, cognitive_levels=','.join(data.cognitive_levels), question_count=total)
            stage = "provider_initialization"
            log_generation_event(generation.id, stage, "started")
            provider = AIProviderFactory.create()
            log_generation_event(generation.id, stage, "completed", provider=provider.name, model=provider.model)
            result = None
            repair_context = None
            ai_duration_ms = 0
            stage_started = time.perf_counter()
            active_progress_stage = "gemini"
            self._progress(generation, "gemini", "PROCESSING", model=provider.model)
            for attempt in range(3):
                stage = "ai_request"
                active_progress_stage = "gemini"
                stage_started = time.perf_counter()
                self._progress(generation, "gemini", "PROCESSING", attempt=attempt + 1, model=provider.model)
                log_generation_event(generation.id, stage, "started", attempt=attempt + 1, repair=attempt > 0, provider=provider.name, model=provider.model)
                request_started = time.perf_counter()
                try:
                    try:
                        candidate = provider.generate(request, repair=attempt > 0, repair_context=repair_context, generation_id=str(generation.id), attempt=attempt + 1)
                    finally:
                        attempt_ai_duration_ms = int((time.perf_counter() - request_started) * 1000)
                        ai_duration_ms += attempt_ai_duration_ms
                        log_generation_event(generation.id, "gemini", "attempt_finished", attempt=attempt + 1, duration_ms=attempt_ai_duration_ms, cumulative_ai_duration_ms=ai_duration_ms)
                    log_generation_event(generation.id, "gemini", "response_received", attempt=attempt + 1, duration_ms=int((time.perf_counter() - request_started) * 1000), question_count=len(candidate.questions))
                    active_progress_stage = "output_validation"
                    self._progress(generation, "output_validation", "PROCESSING", attempt=attempt + 1)
                    stage_started = time.perf_counter()
                    validation_started = stage_started
                    log_generation_event(generation.id, stage, "response_received", attempt=attempt + 1, question_count=len(candidate.questions), blueprint_count=len(candidate.blueprint))
                    counts = {"MULTIPLE_CHOICE": 0, "SHORT_ANSWER": 0, "ESSAY": 0}
                    for question in candidate.questions:
                        counts[question.type] += 1
                    if counts != {"MULTIPLE_CHOICE": data.total_multiple_choice, "SHORT_ANSWER": data.total_short_answer, "ESSAY": data.total_essay}:
                        expected_counts = {"MULTIPLE_CHOICE": data.total_multiple_choice, "SHORT_ANSWER": data.total_short_answer, "ESSAY": data.total_essay}
                        repair_context = {
                            "previous_response": candidate.model_dump_json(),
                            "feedback": f"Jumlah tipe soal tidak sesuai. Jumlah yang diminta: {expected_counts}. Jumlah yang diterima: {counts}.",
                        }
                        log_generation_event(generation.id, stage, "count_validation_failed", attempt=attempt + 1, received_counts=counts)
                        raise AIResponseError("Jumlah soal dari Gemini tidak sesuai permintaan.", repair_context=repair_context)
                    allowed_levels = set(data.cognitive_levels)
                    invalid_levels = [q.number for q in candidate.questions if q.cognitive_level not in allowed_levels]
                    if invalid_levels:
                        repair_context = {"previous_response": candidate.model_dump_json(), "feedback": f"Level kognitif soal nomor {invalid_levels} berada di luar pilihan pengguna {sorted(allowed_levels)}. Perbaiki level soal dan blueprint agar sama."}
                        raise AIResponseError("Gemini menghasilkan level kognitif di luar pilihan.", repair_context=repair_context)
                    result = candidate
                    log_generation_event(generation.id, stage, "validated", attempt=attempt + 1)
                    self._progress(generation, "gemini", "SUCCESS", duration_ms=(time.perf_counter() - request_started) * 1000, attempt=attempt + 1)
                    self._progress(generation, "output_validation", "SUCCESS", duration_ms=(time.perf_counter() - validation_started) * 1000, question_count=len(candidate.questions), blueprint_count=len(candidate.blueprint))
                    break
                except AIResponseError as exc:
                    active_progress_stage = "output_validation"
                    diagnostic = (exc.repair_context or {}).get("feedback", "")
                    repair_context = exc.repair_context or {"feedback": str(exc)}
                    validation_duration = int((time.perf_counter() - stage_started) * 1000)
                    log_generation_event(generation.id, "output_validation", "response_invalid", attempt=attempt + 1, error_type=type(exc).__name__, diagnostic=diagnostic[:300].replace("\n", " "), retrying=attempt < 2, duration_ms=validation_duration)
                    self._progress(generation, "output_validation", "FAILED", duration_ms=validation_duration, message="Output tidak valid; mencoba perbaikan." if attempt < 2 else "Output AI tidak valid.")
                    if attempt == 2:
                        raise
                except AIProviderHTTPError as exc:
                    log_generation_event(generation.id, stage, "provider_http_error", attempt=attempt + 1, status_code=exc.status_code, retryable=exc.retryable, retrying=exc.retryable and attempt < 2, request_duration_ms=exc.request_duration_ms, response_metadata=exc.response_metadata, provider_error_type=exc.provider_error_type, provider_error_code=exc.provider_error_code, provider_error_status=exc.provider_error_status)
                    if not exc.retryable or attempt == 2:
                        raise
                except Exception as exc:
                    log_generation_event(generation.id, stage, "provider_error", attempt=attempt + 1, error_type=type(exc).__name__, retrying=attempt < 2)
                    if attempt == 2:
                        raise
            stage = "result_persistence"
            persistence_started = time.perf_counter()
            active_progress_stage = "database_persistence"
            self._progress(generation, "database_persistence", "PROCESSING", question_count=len(result.questions), blueprint_count=len(result.blueprint))
            log_generation_event(generation.id, stage, "started", question_count=len(result.questions), blueprint_count=len(result.blueprint))
            generation.ai_provider = provider.name
            generation.ai_model = provider.model
            generation.ai_duration_ms = ai_duration_ms
            generation.summary = result.summary
            generation.generation_cost = float(self.setting("generation.cost_per_generate"))
            db_questions = []
            for item in result.questions:
                question = GenerationQuestion(generation_id=generation.id, number=item.number, type=item.type, cognitive_level=item.cognitive_level, question=item.question, answer=item.answer, explanation=item.explanation)
                question.options = [GenerationQuestionOption(label=o.label, text=o.text, is_correct=o.is_correct) for o in item.options]
                db_questions.append(question)
            self.db.add_all(db_questions)
            self.db.flush()
            question_by_number = {q.number: q for q in db_questions}
            self.db.add_all([GenerationBlueprint(generation_id=generation.id, question_id=question_by_number[item.question_number].id, number=item.number, material_topic=item.material_topic, learning_objective=item.learning_objective, indicator=item.indicator, question_type=item.question_type, cognitive_level=item.cognitive_level, difficulty=item.difficulty) for item in result.blueprint])
            self.db.flush()
            log_generation_event(generation.id, stage, "completed", question_count=len(db_questions), blueprint_count=len(result.blueprint))
            persistence_duration_ms = int((time.perf_counter() - persistence_started) * 1000)
            # Serialize final quota consumption for this user to avoid spending the last slot twice.
            stage = "quota_consumption"
            log_generation_event(generation.id, stage, "started")
            self.db.scalar(select(User).where(User.id == user.id).with_for_update())
            if self.quota(user.id)["remaining"] < 1:
                raise ValueError("Kuota generation Anda sudah habis.")
            self.db.add(GenerationUsage(user_id=user.id, generation_id=generation.id, free_generation_used=1, cost=generation.generation_cost))
            log_generation_event(generation.id, stage, "recorded")
            generation.status = GenerationStatus.COMPLETED
            generation.completed_at = datetime.now(UTC)
            generation.error_message = None
            self.audit.log(action="GENERATION_COMPLETED", feature="GENERATION", user_id=user.id, resource="GENERATION", resource_id=str(generation.id), ip_address=ip_address, user_agent=user_agent)
            log_generation_event(generation.id, "audit", "completed")
            self.db.commit()
            self._progress(generation, "database_persistence", "SUCCESS", duration_ms=persistence_duration_ms, question_count=len(db_questions), blueprint_count=len(result.blueprint), option_count=sum(len(item.options) for item in result.questions))
            total_duration_ms = int((time.perf_counter() - total_started) * 1000)
            progress = _read_progress(generation.progress_json)
            progress.update(status="COMPLETED", current_stage="generation_complete", completed_at=generation.completed_at.isoformat(), total_duration_ms=total_duration_ms, question_count=len(db_questions), error=None)
            generation.progress_json = json.dumps(progress, ensure_ascii=False)
            self.db.commit()
            log_generation_event(generation.id, "generation", "finished", status="SUCCESS", total_duration_ms=total_duration_ms, ai_duration_ms=ai_duration_ms, question_count=len(db_questions), completed_at=generation.completed_at.isoformat())
            return generation
        except Exception as exc:
            logger.exception(
                "generation id=%s stage=%s event=exception error_type=%s",
                generation.id,
                stage,
                type(exc).__name__,
            )
            log_generation_event(
                generation.id,
                stage,
                "failed",
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", "-"),
                provider_error_type=getattr(exc, "provider_error_type", None) or (type(exc.__cause__).__name__ if exc.__cause__ else "-"),
                provider_error_code=getattr(exc, "provider_error_code", "-"),
                provider_error_status=getattr(exc, "provider_error_status", "-"),
                provider_error_message=getattr(exc, "provider_error_message", "-"),
                file_name=Path(upload.filename or "materi").name if upload is not None else "-",
                mime_type=upload.content_type or "unknown" if upload is not None else "-",
                file_size=file_byte_count or (upload.size or 0 if upload is not None else 0),
            )
            self.db.rollback()
            generation = self.db.get(Generation, generation.id)
            if generation:
                generation.status = GenerationStatus.FAILED
                generation.error_message = generation_user_error(exc, stage=stage)
                generation.completed_at = datetime.now(UTC)
                generation.progress_json = self.failed_progress(generation.progress_json, stage=active_progress_stage, message=generation.error_message, duration_ms=int((time.perf_counter() - stage_started) * 1000))
                self.audit.log(action="GENERATION_FAILED", feature="GENERATION", user_id=user.id, resource="GENERATION", resource_id=str(generation.id), description="Generation gagal.", ip_address=ip_address, user_agent=user_agent)
                self.db.commit()
                log_generation_event(generation.id, active_progress_stage, "failed", error_type=type(exc).__name__, duration_ms=int((time.perf_counter() - stage_started) * 1000), error=str(exc)[:500])
                log_generation_event(generation.id, "generation", "finished", status="FAILED", total_duration_ms=int((time.perf_counter() - total_started) * 1000), question_count=len(generation.questions), completed_at=generation.completed_at.isoformat())
            return generation

    def prepare_retry(self, generation_id, user: User, *, ip_address=None, user_agent=None):
        previous = self.detail(generation_id, user)
        if previous.user_id != user.id:
            raise HTTPException(status_code=403, detail="Anda hanya dapat mengulang generation milik sendiri.")
        if previous.status != GenerationStatus.FAILED:
            raise HTTPException(status_code=409, detail="Hanya generation yang gagal yang dapat diulang.")
        if not previous.material_text.strip():
            raise HTTPException(status_code=409, detail="Materi generation ini tidak tersimpan, sehingga tidak dapat diulang.")
        data = GenerationCreateSchema(
            title=previous.title,
            description=previous.description,
            subject=previous.subject,
            class_name=previous.class_name,
            type_materi="TEXT",
            materi_text=previous.material_text,
            cognitive_levels=[level for level in json.loads(getattr(previous, "cognitive_levels", None) or '["C1","C2","C3","C4"]') if level in ACTIVE_COGNITIVE_LEVELS] or list(ACTIVE_COGNITIVE_LEVELS),
            references=[item.url for item in previous.references],
            total_multiple_choice=previous.total_multiple_choice,
            total_short_answer=previous.total_short_answer,
            total_essay=previous.total_essay,
        )
        self.validate_start(data, user)
        total = data.total_multiple_choice + data.total_short_answer + data.total_essay
        progress = {
            "status": "PENDING",
            "current_stage": "request_initialization",
            "input_type": "TEXT",
            "reference_count": len(data.references),
            "started_at": None,
            "total_duration_ms": 0,
            "stages": [{"id": "request_initialization", "status": "PENDING"}],
        }
        regenerated = Generation(
            user_id=user.id,
            parent_generation_id=previous.id,
            title=data.title,
            description=data.description,
            subject=data.subject,
            class_name=data.class_name,
            type_materi=MaterialType.TEXT,
            material_text=data.materi_text or "",
            status=GenerationStatus.PENDING,
            total_multiple_choice=data.total_multiple_choice,
            total_short_answer=data.total_short_answer,
            total_essay=data.total_essay,
            total_questions=total,
            cognitive_levels=json.dumps(data.cognitive_levels),
            progress_json=json.dumps(progress, ensure_ascii=False),
        )
        self.repository.add(regenerated)
        self.audit.log(action="GENERATION_RETRY_CREATED", feature="GENERATION", user_id=user.id, resource="GENERATION", resource_id=str(regenerated.id), description=f"Regenerate dari {previous.id}.", ip_address=ip_address, user_agent=user_agent)
        self.db.commit()
        return regenerated, data

    def delete(self, generation_id, user: User):
        generation = self.detail(generation_id, user)
        if generation.user_id != user.id:
            raise HTTPException(status_code=403, detail="Anda hanya dapat menghapus generation milik sendiri.")
        file_path = generation.material_file_path
        self.db.delete(generation)
        self.db.commit()
        if file_path:
            private_root = (Path(get_settings().storage_path) / "generation_private").resolve()
            try:
                candidate = Path(file_path).resolve()
                if candidate.is_relative_to(private_root) and candidate.is_file():
                    candidate.unlink(missing_ok=True)
            except (OSError, RuntimeError):
                pass
        return True

    def update_summary(self, generation_id, user: User, summary: str):
        generation = self.detail(generation_id, user)
        if generation.user_id != user.id:
            raise HTTPException(status_code=403, detail="Anda hanya dapat mengubah generation milik sendiri.")
        if len(summary) > 100_000:
            raise HTTPException(status_code=422, detail="Rangkuman melebihi batas panjang.")
        generation.summary = summary.strip()
        self.db.commit()
        return generation

    def update_metadata(self, generation_id, user: User, *, title: str, description: str | None, subject: str, class_name: str):
        generation = self.detail(generation_id, user)
        if generation.user_id != user.id:
            raise HTTPException(status_code=403, detail="Anda hanya dapat mengubah generation milik sendiri.")
        if not title.strip() or not subject.strip() or not class_name.strip():
            raise HTTPException(status_code=422, detail="Judul, mata pelajaran, dan kelas wajib diisi.")
        if len(title.strip()) > 255 or len(subject.strip()) > 150 or len(class_name.strip()) > 100:
            raise HTTPException(status_code=422, detail="Panjang judul, mata pelajaran, atau kelas melebihi batas.")
        generation.title = title.strip()
        generation.description = description.strip() if description else None
        generation.subject = subject.strip()
        generation.class_name = class_name.strip()
        self.db.commit()
        return generation

    def update_question(self, generation_id, question_id, user: User, *, question: str, answer: str, explanation: str, options: list[dict]):
        generation = self.detail(generation_id, user)
        if generation.user_id != user.id:
            raise HTTPException(status_code=403, detail="Anda hanya dapat mengubah generation milik sendiri.")
        item = next((q for q in generation.questions if str(q.id) == str(question_id)), None)
        if item is None:
            raise HTTPException(status_code=404, detail="Soal tidak ditemukan.")
        if not question.strip() or not answer.strip() or not explanation.strip():
            raise HTTPException(status_code=422, detail="Soal, jawaban, dan pembahasan wajib diisi.")
        if len(question) > 20_000 or len(answer) > 10_000 or len(explanation) > 30_000:
            raise HTTPException(status_code=422, detail="Soal, jawaban, atau pembahasan melebihi batas panjang.")
        if item.type == GenerationQuestionType.MULTIPLE_CHOICE:
            if [option["label"] for option in options] != ["A", "B", "C", "D"] or any(not option.get("text", "").strip() for option in options):
                raise HTTPException(status_code=422, detail="Pilihan ganda harus memiliki opsi A-D.")
            if any(len(option["text"]) > 10_000 for option in options):
                raise HTTPException(status_code=422, detail="Panjang pilihan jawaban melebihi batas.")
            if answer.strip() not in {"A", "B", "C", "D"}:
                raise HTTPException(status_code=422, detail="Pilih satu jawaban benar dari A-D.")
        item.question, item.answer, item.explanation = question.strip(), answer.strip(), explanation.strip()
        item.options.clear()
        item.options.extend(GenerationQuestionOption(label=o["label"], text=o["text"].strip(), is_correct=(o["label"] == answer.strip()) if item.type == "MULTIPLE_CHOICE" else False) for o in options if o.get("text", "").strip())
        self.db.commit()
        return generation

    def update_blueprints(self, generation_id, user: User, rows: list[dict]):
        generation = self.detail(generation_id, user)
        if generation.user_id != user.id:
            raise HTTPException(status_code=403, detail="Anda hanya dapat mengubah generation milik sendiri.")
        by_number = {row.question_number: row for row in generation.blueprints}
        if len(rows) != len(by_number) or {int(values["question_number"]) for values in rows} != set(by_number):
            raise HTTPException(status_code=422, detail="Seluruh kisi-kisi harus dikirim bersama.")
        for values in rows:
            row = by_number.get(int(values["question_number"]))
            if row:
                if any(not values[field].strip() for field in ("material_topic", "learning_objective", "indicator")):
                    raise HTTPException(status_code=422, detail="Topik, tujuan, dan indikator wajib diisi.")
                if any(len(values[field]) > 10_000 for field in ("material_topic", "learning_objective", "indicator")):
                    raise HTTPException(status_code=422, detail="Isi kisi-kisi melebihi batas panjang.")
                if values["cognitive_level"] not in ACTIVE_COGNITIVE_LEVELS and values["cognitive_level"] != row.cognitive_level:
                    raise HTTPException(status_code=422, detail="Level kognitif baru saat ini hanya tersedia untuk C1 sampai C4.")
                if values["cognitive_level"] not in {"C1", "C2", "C3", "C4", "C5", "C6"} or values["difficulty"] not in {"EASY", "MEDIUM", "HARD"}:
                    raise HTTPException(status_code=422, detail="Level kognitif atau kesulitan tidak valid.")
                row.material_topic = values["material_topic"].strip()
                row.learning_objective = values["learning_objective"].strip()
                row.indicator = values["indicator"].strip()
                row.cognitive_level = values["cognitive_level"]
                row.question.cognitive_level = values["cognitive_level"]
                row.difficulty = values["difficulty"]
        self.db.commit()
        return generation
