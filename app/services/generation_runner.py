from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from io import BytesIO
from threading import Lock
from uuid import UUID

from starlette.datastructures import Headers, UploadFile

from app.core.database import SessionLocal
from app.models.generation import Generation, GenerationStatus
from app.models.user import User
from app.schemas.generation import GenerationCreateSchema
from app.services.generation_service import GenerationService, generation_user_error, log_generation_event

logger = logging.getLogger(__name__)


class GenerationRunner:
    """Owns in-process generation jobs and waits for them during app shutdown."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._executor: ThreadPoolExecutor | None = None
        self._futures: dict[UUID, Future] = {}

    def submit(
        self,
        generation_id: UUID,
        user_id: UUID,
        data: GenerationCreateSchema,
        *,
        upload_bytes: bytes | None,
        upload_name: str | None,
        upload_mime: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="generation")
            future = self._executor.submit(
                self._run,
                generation_id,
                user_id,
                data,
                upload_bytes,
                upload_name,
                upload_mime,
                ip_address,
                user_agent,
            )
            self._futures[generation_id] = future
            future.add_done_callback(lambda _future: self._remove(generation_id))

    def _remove(self, generation_id: UUID) -> None:
        with self._lock:
            self._futures.pop(generation_id, None)

    @staticmethod
    def _create_upload(upload_bytes: bytes | None, upload_name: str | None, upload_mime: str | None) -> UploadFile | None:
        if upload_bytes is None:
            return None
        return UploadFile(
            filename=upload_name or "materi",
            file=BytesIO(upload_bytes),
            size=len(upload_bytes),
            headers=Headers({"content-type": upload_mime or "application/octet-stream"}),
        )

    @staticmethod
    def _run(
        generation_id: UUID,
        user_id: UUID,
        data: GenerationCreateSchema,
        upload_bytes: bytes | None,
        upload_name: str | None,
        upload_mime: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        upload = GenerationRunner._create_upload(upload_bytes, upload_name, upload_mime)
        with SessionLocal() as db:
            try:
                user = db.get(User, user_id)
                generation = db.get(Generation, generation_id)
                if user is None or generation is None:
                    raise RuntimeError("Generation queue record or user is missing.")
                GenerationService(db).create(
                    data,
                    user,
                    upload=upload,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    existing_generation=generation,
                )
            except Exception as exc:
                logger.exception(
                    "generation id=%s stage=background_runner event=failed error_type=%s",
                    generation_id,
                    type(exc).__name__,
                )
                db.rollback()
                generation = db.get(Generation, generation_id)
                if generation is not None:
                    generation.status = GenerationStatus.FAILED
                    generation.error_message = generation_user_error(exc, stage="request_initialization")
                    generation.progress_json = GenerationService.failed_progress(
                        generation.progress_json,
                        stage="request_initialization",
                        message=generation.error_message,
                    )
                    db.commit()
                    log_generation_event(generation_id, "generation", "finished", status="FAILED")
            finally:
                if upload is not None:
                    upload.file.close()

    def shutdown(self) -> None:
        with self._lock:
            executor = self._executor
            self._executor = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=False)


generation_runner = GenerationRunner()
