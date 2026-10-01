from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.ai.exceptions import AIProviderHTTPError, AIResponseError
from app.integrations.ai.factory import AIProviderFactory
from app.integrations.ai.schemas import AIGenerationRequest, QuestionDistribution
from app.integrations.material.extractor import MaterialExtractor
from app.integrations.references.content_service import ReferenceContentService
from app.models.generation import (Generation, GenerationBlueprint, GenerationQuestion, GenerationQuestionOption, GenerationQuestionType, GenerationReference, GenerationStatus, GenerationUsage, MaterialType)
from app.models.user import User
from app.repositories.generation_repository import GenerationRepository, GenerationSettingRepository
from app.schemas.generation import GenerationCreateSchema
from app.services.audit_service import AuditService

def truncate_material(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    boundary = text.rfind(" ", 0, limit)
    return text[:boundary if boundary > limit * 0.8 else limit].rstrip()


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
        now = datetime.now(timezone.utc)
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

    def create(self, data: GenerationCreateSchema, user: User, *, upload=None, ip_address=None, user_agent=None, existing_generation=None):
        if self.setting("generation.enabled").lower() != "true":
            raise HTTPException(status_code=403, detail="Fitur generation sedang tidak tersedia.")
        distribution = {"multiple_choice": data.total_multiple_choice, "short_answer": data.total_short_answer, "essay": data.total_essay}
        total = sum(distribution.values())
        if total > int(self.setting("generation.max_questions_per_generate")):
            raise HTTPException(status_code=422, detail="Jumlah soal melebihi batas per generation.")
        if self.quota(user.id)["remaining"] < 1:
            raise HTTPException(status_code=403, detail="Kuota generation Anda sudah habis.")
        if data.type_materi == "FILE" and upload is None:
            raise HTTPException(status_code=422, detail="File materi wajib diunggah.")
        generation = existing_generation
        if generation is None:
            generation = Generation(user_id=user.id, title=data.title.strip(), description=data.description, subject=data.subject.strip(), class_name=data.class_name.strip(), type_materi=MaterialType(data.type_materi), material_text="", status=GenerationStatus.PENDING, total_multiple_choice=data.total_multiple_choice, total_short_answer=data.total_short_answer, total_essay=data.total_essay, total_questions=total)
            self.repository.add(generation)
            self.audit.log(action="GENERATION_CREATED", feature="GENERATION", user_id=user.id, resource="GENERATION", resource_id=str(generation.id), ip_address=ip_address, user_agent=user_agent)
        else:
            generation.status = GenerationStatus.PENDING
            generation.error_message = None
            generation.summary = None
            generation.questions.clear()
            generation.blueprints.clear()
            generation.references.clear()
        self.db.commit()
        self.audit.log(action="GENERATION_STARTED", feature="GENERATION", user_id=user.id, resource="GENERATION", resource_id=str(generation.id), ip_address=ip_address, user_agent=user_agent)
        generation.status = GenerationStatus.PROCESSING
        generation.started_at = datetime.now(timezone.utc)
        self.db.commit()
        try:
            maximum_material = int(self.setting("generation.max_material_characters"))
            file_name = file_mime = None
            if data.type_materi == "TEXT":
                material = "\n".join(line.strip() for line in (data.materi_text or "").splitlines() if line.strip())
                material = truncate_material(material, maximum_material)
            else:
                maximum_file_size = get_settings().max_upload_size
                if upload.size is not None and upload.size > maximum_file_size:
                    raise ValueError("File kosong atau melebihi batas ukuran.")
                file_bytes = upload.file.read(maximum_file_size + 1)
                extracted = MaterialExtractor().extract(upload.filename or "materi", upload.content_type or "", file_bytes, maximum_file_size)
                material, file_name, file_mime = truncate_material(extracted.text, maximum_material), extracted.filename, extracted.mime_type
                storage_root = Path(get_settings().storage_path) / "generation_private"
                storage_root.mkdir(mode=0o700, parents=True, exist_ok=True)
                storage_root.chmod(0o700)
                storage_file = storage_root / f"{uuid.uuid4().hex}{Path(file_name).suffix.lower()}"
                storage_file.write_bytes(file_bytes)
                storage_file.chmod(0o600)
                generation.material_file_name = file_name
                generation.material_file_path = str(storage_file)
                generation.material_file_mime_type = file_mime
            generation.material_text = material
            references, reference_texts = [], []
            reference_limit = int(self.setting("generation.max_reference_characters"))
            for url in data.references:
                if not url.strip():
                    continue
                content, title, error = ReferenceContentService().fetch(url.strip(), reference_limit)
                references.append(GenerationReference(generation_id=generation.id, url=url.strip(), title=title, extracted_content=content, extraction_status="SUCCESS" if content else "FAILED", error_message=error))
                if content:
                    reference_texts.append(f"URL: {url.strip()}\n{content}")
            self.db.add_all(references)
            # Keep source material available if provider setup or generation fails,
            # so the user can retry the failed generation later.
            self.db.commit()
            request = AIGenerationRequest(title=data.title, description=data.description or "", subject=data.subject, class_name=data.class_name, material=material, references=reference_texts, question_distribution=QuestionDistribution(**distribution))
            provider = AIProviderFactory.create()
            result = None
            repair_context = None
            for attempt in range(3):
                try:
                    candidate = provider.generate(request, repair=attempt > 0, repair_context=repair_context)
                    counts = {"MULTIPLE_CHOICE": 0, "SHORT_ANSWER": 0, "ESSAY": 0}
                    for question in candidate.questions:
                        counts[question.type] += 1
                    if counts != {"MULTIPLE_CHOICE": data.total_multiple_choice, "SHORT_ANSWER": data.total_short_answer, "ESSAY": data.total_essay}:
                        expected_counts = {"MULTIPLE_CHOICE": data.total_multiple_choice, "SHORT_ANSWER": data.total_short_answer, "ESSAY": data.total_essay}
                        repair_context = {
                            "previous_response": candidate.model_dump_json(),
                            "feedback": f"Jumlah tipe soal tidak sesuai. Jumlah yang diminta: {expected_counts}. Jumlah yang diterima: {counts}.",
                        }
                        raise AIResponseError("Jumlah soal dari Gemini tidak sesuai permintaan.", repair_context=repair_context)
                    result = candidate
                    break
                except AIResponseError as exc:
                    repair_context = exc.repair_context or {"feedback": str(exc)}
                    if attempt == 2:
                        raise
                except AIProviderHTTPError as exc:
                    if not exc.retryable or attempt == 2:
                        raise
                except Exception:
                    if attempt == 2:
                        raise
            generation.ai_provider = provider.name
            generation.ai_model = provider.model
            generation.summary = result.summary
            generation.generation_cost = float(self.setting("generation.cost_per_generate"))
            db_questions = []
            for item in result.questions:
                question = GenerationQuestion(generation_id=generation.id, number=item.number, type=item.type, question=item.question, answer=item.answer, explanation=item.explanation)
                question.options = [GenerationQuestionOption(label=o.label, text=o.text, is_correct=o.is_correct) for o in item.options]
                db_questions.append(question)
            self.db.add_all(db_questions)
            self.db.flush()
            question_by_number = {q.number: q for q in db_questions}
            self.db.add_all([GenerationBlueprint(generation_id=generation.id, question_id=question_by_number[item.question_number].id, number=item.number, material_topic=item.material_topic, learning_objective=item.learning_objective, indicator=item.indicator, question_type=item.question_type, cognitive_level=item.cognitive_level, difficulty=item.difficulty) for item in result.blueprint])
            # Serialize final quota consumption for this user to avoid spending the last slot twice.
            self.db.scalar(select(User).where(User.id == user.id).with_for_update())
            if self.quota(user.id)["remaining"] < 1:
                raise ValueError("Kuota generation Anda sudah habis.")
            self.db.add(GenerationUsage(user_id=user.id, generation_id=generation.id, free_generation_used=1, cost=generation.generation_cost))
            generation.status = GenerationStatus.COMPLETED
            generation.completed_at = datetime.now(timezone.utc)
            generation.error_message = None
            self.audit.log(action="GENERATION_COMPLETED", feature="GENERATION", user_id=user.id, resource="GENERATION", resource_id=str(generation.id), ip_address=ip_address, user_agent=user_agent)
            self.db.commit()
            return generation
        except Exception:
            self.db.rollback()
            generation = self.db.get(Generation, generation.id)
            if generation:
                generation.status = GenerationStatus.FAILED
                generation.error_message = "Generation gagal. Silakan coba kembali."
                generation.completed_at = datetime.now(timezone.utc)
                self.audit.log(action="GENERATION_FAILED", feature="GENERATION", user_id=user.id, resource="GENERATION", resource_id=str(generation.id), description="Generation gagal.", ip_address=ip_address, user_agent=user_agent)
                self.db.commit()
            return generation

    def retry(self, generation_id, user: User, *, ip_address=None, user_agent=None):
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
            references=[item.url for item in previous.references],
            total_multiple_choice=previous.total_multiple_choice,
            total_short_answer=previous.total_short_answer,
            total_essay=previous.total_essay,
        )
        return self.create(data, user, existing_generation=previous, ip_address=ip_address, user_agent=user_agent)

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
                if values["cognitive_level"] not in {"C1", "C2", "C3", "C4", "C5", "C6"} or values["difficulty"] not in {"EASY", "MEDIUM", "HARD"}:
                    raise HTTPException(status_code=422, detail="Level kognitif atau kesulitan tidak valid.")
                row.material_topic = values["material_topic"].strip()
                row.learning_objective = values["learning_objective"].strip()
                row.indicator = values["indicator"].strip()
                row.cognitive_level = values["cognitive_level"]
                row.difficulty = values["difficulty"]
        self.db.commit()
        return generation
