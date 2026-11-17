from __future__ import annotations

import xml.etree.ElementTree as ET
from io import BytesIO
from types import SimpleNamespace as Namespace
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.integrations.ai.schemas import AIGenerationResponse
from app.integrations.ai.exceptions import AIConfigurationError, AIProviderHTTPError, AIProviderError, AIResponseError
from app.integrations.exports.docx import TEMPLATES, build_generation_docx
from app.integrations.references.content_service import ReferenceContentService
from app.models.generation import (
    GenerationBlueprint,
    GenerationQuestion,
    GenerationQuestionOption,
    GenerationQuestionType,
    GenerationStatus,
    MaterialType,
)
from app.models.user import UserRole
from app.routers import generation as generation_router
from app.schemas.auth import PasswordChangeSchema, UserUpdateSchema
from app.services.generation_service import GenerationService, generation_error_title, generation_user_error, truncate_material
from app.services.generation_runner import GenerationRunner


class FakeDB:
    def __init__(self):
        self.committed = False
        self.deleted = None

    def commit(self):
        self.committed = True

    def delete(self, value):
        self.deleted = value

    def rollback(self):
        pass


def generation_fixture(owner_id=None):
    owner_id = owner_id or uuid4()
    question = GenerationQuestion(
        generation_id=uuid4(),
        number=3,
        type=GenerationQuestionType.MULTIPLE_CHOICE,
        question="Hitung $2+2$",
        answer="B",
        explanation="Hasilnya empat.",
    )
    question.options = [
        GenerationQuestionOption(label="A", text="3", is_correct=False),
        GenerationQuestionOption(label="B", text="4", is_correct=True),
        GenerationQuestionOption(label="C", text="5", is_correct=False),
        GenerationQuestionOption(label="D", text="6", is_correct=False),
    ]
    blueprint = GenerationBlueprint(
        generation_id=question.generation_id,
        question_id=uuid4(),
        number=1,
        material_topic="Operasi bilangan",
        learning_objective="Menghitung penjumlahan",
        indicator="Menyelesaikan penjumlahan",
        question_type=GenerationQuestionType.MULTIPLE_CHOICE,
        cognitive_level="C1",
        difficulty="EASY",
    )
    blueprint.question = question
    return Namespace(
        id=question.generation_id,
        user_id=owner_id,
        title="Eksponen dan Bilangan",
        description="Materi tes",
        subject="Matematika",
        class_name="10",
        type_materi=MaterialType.TEXT,
        material_text="Materi sumber $x^2$",
        material_file_path=None,
        material_file_name=None,
        material_file_mime_type=None,
        status=GenerationStatus.COMPLETED,
        summary="Ringkasan $x^2$",
        questions=[question],
        blueprints=[blueprint],
        references=[],
        generation_cost=0,
        ai_provider="gemini",
        ai_model="test-model",
        created_at=Namespace(strftime=lambda _fmt: "01-01-2026 00:00"),
        total_questions=1,
        total_multiple_choice=1,
        total_short_answer=0,
        total_essay=0,
    )


def test_blueprint_question_number_comes_from_question_relationship():
    generation = generation_fixture()
    assert generation.blueprints[0].question_number == 3


def test_ai_response_rejects_mismatched_question_and_blueprint_levels():
    payload = {
        "summary": "Ringkasan berdasarkan sumber.",
        "questions": [{"number": 1, "type": "ESSAY", "cognitive_level": "C1", "question": "Sebutkan konsep.", "answer": "Konsep sumber.", "explanation": "Tercantum dalam sumber."}],
        "blueprint": [{"number": 1, "question_number": 1, "material_topic": "Konsep", "learning_objective": "Mengingat konsep", "indicator": "Menyebutkan konsep", "question_type": "ESSAY", "cognitive_level": "C4", "difficulty": "EASY"}],
    }
    with pytest.raises(ValueError, match="Level kognitif"):
        AIGenerationResponse.model_validate(payload)


def test_generation_schema_rejects_empty_cognitive_selection():
    from pydantic import ValidationError

    from app.schemas.generation import GenerationCreateSchema

    with pytest.raises(ValidationError):
        GenerationCreateSchema(title="T", subject="S", class_name="1", type_materi="TEXT", materi_text="materi", cognitive_levels=[], total_essay=1)


def test_generation_schema_rejects_c5_and_c6_while_preserving_active_multiselect():
    from pydantic import ValidationError

    from app.schemas.generation import GenerationCreateSchema

    base = dict(title="T", subject="S", class_name="1", type_materi="TEXT", materi_text="materi", total_essay=1)
    valid = GenerationCreateSchema(**base, cognitive_levels=["C1", "C4"])
    assert valid.cognitive_levels == ["C1", "C4"]
    for inactive in ("C5", "C6"):
        with pytest.raises(ValidationError, match="belum tersedia"):
            GenerationCreateSchema(**base, cognitive_levels=[inactive])


def test_progress_failure_marks_stage_and_total_duration():
    import json

    from app.services.generation_service import GenerationService

    progress = {
        "started_at": "2026-01-01T00:00:00+00:00",
        "stages": [{"id": "file_extraction", "status": "PROCESSING"}],
    }
    failed = json.loads(GenerationService.failed_progress(
        json.dumps(progress), stage="file_extraction", message="File tidak valid", duration_ms=250,
    ))
    assert failed["status"] == "FAILED"
    assert failed["stages"][0]["status"] == "FAILED"
    assert failed["stages"][0]["duration_ms"] == 250
    assert failed["total_duration_ms"] >= 0


def test_background_upload_retains_mime_type_and_rewinds_pointer():
    upload = GenerationRunner._create_upload(b"%PDF-1.7", "materi.pdf", "application/pdf")
    assert upload is not None
    assert upload.filename == "materi.pdf"
    assert upload.content_type == "application/pdf"
    assert upload.file.read() == b"%PDF-1.7"


def test_progress_status_reads_generation_without_submitting_another_job(monkeypatch):
    import json

    generation = generation_fixture()
    generation.progress_json = json.dumps({"status": "COMPLETED", "total_duration_ms": 1200, "stages": []})
    generation.started_at = None
    monkeypatch.setattr(GenerationService, "detail", lambda _self, _generation_id, _user: generation)
    monkeypatch.setattr(generation_router.generation_runner, "submit", lambda *_args, **_kwargs: pytest.fail("status polling must not submit generation"))

    status = generation_router.generation_progress_status(generation.id, FakeDB(), Namespace(id=generation.user_id))

    assert status["status"] == "COMPLETED"
    assert status["total_duration_ms"] == 1200
    assert status["result_url"] == f"/generation/{generation.id}"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AIConfigurationError("secret-api-key"), "Autentikasi layanan AI gagal."),
        (AIProviderHTTPError(400, "private provider detail", retryable=False, provider_error_code="API_KEY_INVALID"), "Autentikasi layanan AI gagal."),
        (AIProviderHTTPError(429, "private provider detail", retryable=True, provider_error_status="RESOURCE_EXHAUSTED"), "Kuota"),
        (AIProviderHTTPError(504, "provider detail", retryable=True), "batas waktu"),
        (AIProviderError("transport details",), "terhubung ke layanan AI"),
        (AIResponseError("raw response containing private data"), "format yang diharapkan"),
    ],
)
def test_generation_errors_are_mapped_to_safe_actionable_messages(error, expected):
    message = generation_user_error(error)
    assert expected.lower() in message.lower()
    assert "secret-api-key" not in message
    assert "private provider detail" not in message
    assert "raw response" not in message


def test_generation_error_mapper_identifies_material_and_database_failures():
    from sqlalchemy.exc import OperationalError

    assert "file sumber materi" in generation_user_error(ValueError("broken extraction"), stage="material_file_extraction").lower()
    assert "menyimpan hasil" in generation_user_error(OperationalError("statement", {}, RuntimeError("db secret"))).lower()
    assert generation_error_title("Kuota atau batas penggunaan layanan AI telah tercapai.") == "Kuota layanan AI tercapai"


def test_progress_status_only_returns_errors_for_failed_generation(monkeypatch):
    import json

    generation = generation_fixture()
    generation.error_message = "Autentikasi layanan AI gagal. Periksa konfigurasi API key atau hubungi administrator."
    generation.progress_json = json.dumps({"stages": []})
    generation.started_at = None
    monkeypatch.setattr(GenerationService, "detail", lambda _self, _generation_id, _user: generation)
    user = Namespace(id=generation.user_id)

    success = generation_router.generation_progress_status(generation.id, FakeDB(), user)
    assert success["error"] is None
    assert success["error_title"] is None

    generation.status = GenerationStatus.FAILED
    failed = generation_router.generation_progress_status(generation.id, FakeDB(), user)
    assert failed["error_title"] == "Autentikasi layanan AI gagal"
    assert "API key" in failed["error"]


def test_generation_progress_template_hides_warning_and_renders_error_conditionally():
    from pathlib import Path

    template = Path("app/templates/pages/generation/progress.html").read_text()
    assert "progress-note" not in template
    assert "nodes.error.hidden=!failed" in template
    assert "nodes.errorMessage.textContent=payload.error" in template
    assert "nodes.retry.hidden=!failed" in template


def test_settings_template_always_restores_submit_state_after_request():
    from pathlib import Path

    template = Path("app/templates/pages/admin/settings/index.html").read_text()
    assert "finally{if(timeout)clearTimeout(timeout);isSubmitting=false;submit.disabled=false" in template
    assert "response.status===422" in template
    assert "fieldNames.has(name)&&showFieldError(name,message)" in template
    assert "controller.abort()" in template


def test_oversized_material_is_rejected_instead_of_silently_truncated():
    with pytest.raises(ValueError, match="melebihi batas"):
        truncate_material("Materi panjang", 5)


def test_edit_blueprints_updates_all_rows_and_commits():
    generation = generation_fixture()
    service = object.__new__(GenerationService)
    service.db = FakeDB()
    service.detail = lambda _generation_id, _user: generation
    service.update_blueprints(
        generation.id,
        Namespace(id=generation.user_id),
        [
            {
                "question_number": 3,
                "material_topic": "Eksponen",
                "learning_objective": "Memahami pangkat",
                "indicator": "Menentukan nilai pangkat",
                "cognitive_level": "C2",
                "difficulty": "MEDIUM",
            }
        ],
    )
    assert generation.blueprints[0].material_topic == "Eksponen"
    assert generation.blueprints[0].cognitive_level == "C2"
    assert service.db.committed


def test_edit_blueprints_rejects_partial_batch():
    generation = generation_fixture()
    service = object.__new__(GenerationService)
    service.db = FakeDB()
    service.detail = lambda _generation_id, _user: generation
    with pytest.raises(HTTPException) as error:
        service.update_blueprints(generation.id, Namespace(id=generation.user_id), [])
    assert error.value.status_code == 422


def test_edit_summary_and_metadata_save_for_owner():
    generation = generation_fixture()
    service = object.__new__(GenerationService)
    service.db = FakeDB()
    service.detail = lambda _generation_id, _user: generation
    user = Namespace(id=generation.user_id)
    service.update_summary(generation.id, user, "Ringkasan baru")
    service.update_metadata(generation.id, user, title="Judul baru", description="Deskripsi baru", subject="IPA", class_name="8")
    assert generation.summary == "Ringkasan baru"
    assert generation.title == "Judul baru"
    assert generation.subject == "IPA"
    assert service.db.committed


def test_edit_question_updates_answer_and_option_correctness():
    generation = generation_fixture()
    service = object.__new__(GenerationService)
    service.db = FakeDB()
    service.detail = lambda _generation_id, _user: generation
    question = generation.questions[0]
    service.update_question(
        generation.id,
        question.id,
        Namespace(id=generation.user_id),
        question="Soal baru $x^2$",
        answer="C",
        explanation="C merupakan jawaban benar.",
        options=[{"label": key, "text": f"opsi {key}"} for key in "ABCD"],
    )
    assert question.question == "Soal baru $x^2$"
    assert question.answer == "C"
    assert [item.label for item in question.options if item.is_correct] == ["C"]


def test_retry_creates_separate_generation_and_preserves_failed_source():
    generation = generation_fixture()
    generation.status = GenerationStatus.FAILED
    generation.cognitive_levels = '["C1","C4"]'
    service = object.__new__(GenerationService)
    service.detail = lambda _generation_id, _user: generation
    service.validate_start = lambda _data, _user: None
    service.repository = Namespace(add=lambda item: setattr(service, "added", item))
    service.audit = Namespace(log=lambda **_kwargs: None)
    service.db = FakeDB()

    result, data = service.prepare_retry(generation.id, Namespace(id=generation.user_id))

    assert result.id != generation.id
    assert result.parent_generation_id == generation.id
    assert result.status == GenerationStatus.PENDING
    assert data.cognitive_levels == ["C1", "C4"]
    assert generation.questions  # Failed generation's previous output is untouched.
    assert service.db.committed


def test_settings_validation_returns_field_errors_without_redirect_or_database_write():
    request = Namespace(headers={"accept": "application/json"})
    db = FakeDB()

    response = generation_router.update_generation_settings(
        request,
        generation_free_limit="0",
        generation_cost_per_generate="2",
        generation_enabled="true",
        generation_max_questions_per_generate="10",
        generation_max_material_characters="1000",
        generation_max_reference_characters="500",
        db=db,
        user=Namespace(id=uuid4()),
    )

    import json

    payload = json.loads(response.body)
    assert response.status_code == 422
    assert "generation_free_limit" in payload["errors"]
    assert not db.committed


def test_valid_settings_ajax_request_returns_json_success_without_redirect():
    import json

    class SettingsDB:
        def __init__(self):
            self.rows = [Namespace(value="", is_active=False) for _ in range(6)]
            self.index = 0
            self.committed = False

        def scalar(self, _statement):
            row = self.rows[self.index]
            self.index += 1
            return row

        def commit(self):
            self.committed = True

    db = SettingsDB()
    response = generation_router.update_generation_settings(
        Namespace(headers={"accept": "application/json"}),
        generation_free_limit="25",
        generation_cost_per_generate="1.25",
        generation_enabled="true",
        generation_max_questions_per_generate="20",
        generation_max_material_characters="30000",
        generation_max_reference_characters="5000",
        db=db,
        user=Namespace(id=uuid4()),
    )
    payload = json.loads(response.body)
    assert response.status_code == 200
    assert payload["settings"]["generation.free_limit"] == "25"
    assert db.committed
    assert all(row.is_active for row in db.rows)


def test_settings_database_error_returns_http_500_and_rolls_back():
    from sqlalchemy.exc import SQLAlchemyError

    class BrokenDB(FakeDB):
        def scalar(self, _statement):
            return Namespace(value="1", is_active=True)

        def commit(self):
            raise SQLAlchemyError("database unavailable")

    db = BrokenDB()
    response = generation_router.update_generation_settings(
        Namespace(headers={"accept": "application/json"}),
        generation_free_limit="25",
        generation_cost_per_generate="1.25",
        generation_enabled="true",
        generation_max_questions_per_generate="20",
        generation_max_material_characters="30000",
        generation_max_reference_characters="5000",
        db=db,
        user=Namespace(id=uuid4()),
    )
    assert response.status_code == 500
    assert not db.committed


def test_retry_route_redirects_to_same_progress_page_and_submits_worker(monkeypatch):
    generation = generation_fixture()
    captured = {}
    data = Namespace(materi_text=generation.material_text)
    monkeypatch.setattr(GenerationService, "prepare_retry", lambda _self, *_args, **_kwargs: (generation, data))
    monkeypatch.setattr(generation_router.generation_runner, "submit", lambda *args, **kwargs: captured.update(args=args, kwargs=kwargs))
    request = Namespace(client=Namespace(host="127.0.0.1"), headers={})

    response = generation_router.retry_generation(request, generation.id, FakeDB(), Namespace(id=generation.user_id))

    assert response.status_code == 303
    assert response.headers["location"] == f"/generation/{generation.id}/progress"
    assert captured["args"][:2] == (generation.id, generation.user_id)


def test_ai_duration_formatting_uses_milliseconds_seconds_and_minutes():
    assert generation_router.format_ai_duration(845) == "845 ms"
    assert generation_router.format_ai_duration(12_450) == "12,45 detik"
    assert generation_router.format_ai_duration(64_250) == "1 menit 04,25 detik"
    assert generation_router.format_ai_duration(None) == "Belum tersedia"


def test_non_owner_cannot_delete_generation():
    generation = generation_fixture(owner_id=uuid4())
    service = object.__new__(GenerationService)
    service.detail = lambda _generation_id, _user: generation
    service.db = FakeDB()
    with pytest.raises(HTTPException) as error:
        service.delete(generation.id, Namespace(id=uuid4()))
    assert error.value.status_code == 403
    assert service.db.deleted is None


def test_owner_delete_only_removes_files_inside_private_storage(tmp_path, monkeypatch):
    generation = generation_fixture()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"keep")
    generation.material_file_path = str(outside)
    service = object.__new__(GenerationService)
    service.detail = lambda _generation_id, _user: generation
    service.db = FakeDB()
    monkeypatch.setattr("app.services.generation_service.get_settings", lambda: Namespace(storage_path=str(tmp_path / "storage")))
    service.delete(generation.id, Namespace(id=generation.user_id))
    assert outside.exists()


def test_daily_quota_uses_today_usage_and_database_setting():
    class QuotaDB:
        def __init__(self):
            self.statements = []

        def scalar(self, statement):
            self.statements.append(statement)
            return [4, 0.75][len(self.statements) - 1]

    service = object.__new__(GenerationService)
    service.db = QuotaDB()
    service.setting = lambda _key: "10"
    result = service.quota(uuid4())
    assert result == {"used": 4, "limit": 10, "remaining": 6, "cost": 0.75}
    assert all("generation_usage.created_at" in str(statement) for statement in service.db.statements)


def test_admin_generation_list_is_not_owner_filtered():
    class Repository:
        def list_owned(self, user_id, **kwargs):
            self.user_id = user_id
            return [], 0

    service = object.__new__(GenerationService)
    service.repository = Repository()
    result = service.list(Namespace(role=UserRole.ADMIN), page=1)
    assert result == ([], 0)
    assert service.repository.user_id is None


def test_admin_can_view_other_owner_detail_but_guru_gets_404():
    generation = generation_fixture()

    class Repository:
        def get_owned(self, _generation_id, _user_id):
            return None

        def get_any(self, _generation_id):
            return generation

    service = object.__new__(GenerationService)
    service.repository = Repository()
    with pytest.raises(HTTPException) as error:
        service.detail(generation.id, Namespace(role=UserRole.GURU, id=uuid4()))
    assert error.value.status_code == 404
    assert service.detail(generation.id, Namespace(role=UserRole.ADMIN)) is generation


def test_question_template_two_has_narrow_number_and_vertical_options():
    generation = generation_fixture()
    content = build_generation_docx("soal_2", generation).getvalue()
    with ZipFile(BytesIO(content)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    table = root.find(".//w:tbl", ns)
    widths = [int(node.attrib["{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w"]) for node in table.findall("./w:tblGrid/w:gridCol", ns)]
    assert widths[0] < widths[1]
    option_cell = table.findall("./w:tr", ns)[1].findall("./w:tc", ns)[2]
    assert len(option_cell.findall("./w:p", ns)) == 4
    assert ["".join(node.itertext()) for node in option_cell.findall("./w:p", ns)] == ["A. 3", "B. 4", "C. 5", "D. 6"]


def test_all_docx_templates_render():
    generation = generation_fixture()
    assert set(TEMPLATES) == {"materi", "soal_1", "soal_2", "pembahasan", "kisi_kisi"}
    for key in TEMPLATES:
        with ZipFile(build_generation_docx(key, generation)) as archive:
            assert archive.testzip() is None
            xml = archive.read("word/document.xml")
            ET.fromstring(xml)
            if key == "kisi_kisi":
                assert b"Soal 3" in xml
                assert b"Operasi bilangan" in xml


def test_summary_export_uses_requested_filename(monkeypatch):
    generation = generation_fixture()
    monkeypatch.setattr(GenerationService, "detail", lambda _self, _id, _user: generation)
    response = generation_router.export_generation(
        generation.id,
        "summary",
        db=FakeDB(),
        user=Namespace(id=generation.user_id),
    )
    assert response.headers["content-disposition"] == 'attachment; filename="rangkuman-eksponen.docx"'


def test_private_material_route_rejects_path_outside_storage(tmp_path, monkeypatch):
    generation = generation_fixture()
    generation.type_materi = MaterialType.FILE
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.7")
    generation.material_file_path = str(outside)
    generation.material_file_name = "materi.pdf"
    monkeypatch.setattr(GenerationService, "detail", lambda _self, _id, _user: generation)
    monkeypatch.setattr(generation_router, "get_settings", lambda: Namespace(storage_path=str(tmp_path / "private-root")))
    with pytest.raises(HTTPException) as error:
        generation_router.generation_material_file(generation.id, db=FakeDB(), user=Namespace(id=generation.user_id))
    assert error.value.status_code == 404


def test_private_material_route_serves_file_only_from_private_storage(tmp_path, monkeypatch):
    generation = generation_fixture()
    private = tmp_path / "generation_private"
    private.mkdir()
    file_path = private / "random.pdf"
    file_path.write_bytes(b"%PDF-1.7")
    generation.type_materi = MaterialType.FILE
    generation.material_file_path = str(file_path)
    generation.material_file_name = "materi.pdf"
    monkeypatch.setattr(GenerationService, "detail", lambda _self, _id, _user: generation)
    monkeypatch.setattr(generation_router, "get_settings", lambda: Namespace(storage_path=str(tmp_path)))
    response = generation_router.generation_material_file(generation.id, db=FakeDB(), user=Namespace(id=generation.user_id))
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_source_material_detail_uses_private_file_link_for_file_material():
    from app.main import app

    generation = generation_fixture()
    generation.type_materi = MaterialType.FILE
    generation.material_file_name = "materi.pdf"
    user = Namespace(id=generation.user_id, role=UserRole.GURU, full_name="Guru Uji")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(GenerationService, "detail", lambda _self, _id, _user: generation)
    request = Request({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http", "path": f"/generation/{generation.id}", "raw_path": f"/generation/{generation.id}".encode(), "query_string": b"", "headers": [], "client": ("127.0.0.1", 1234), "server": ("testserver", 80), "app": app, "router": app.router})
    try:
        response = generation_router.generation_detail(request, generation.id, FakeDB(), user)
        body = response.body.decode()
        assert "/material\"" in body
        assert "materi.pdf" in body
        assert "Materi sumber $x^2$" not in body
        assert "Kisi-kisi untuk soal 3" in body
        assert 'name="question_number" value="3"' in body
        assert '<details class="blueprint-editor-disclosure"' in body
        assert '<summary class="button button-outline button-sm">Edit Semua Kisi-Kisi</summary>' in body
        assert 'name="material_topic"' in body
        assert 'name="learning_objective"' in body
        assert 'name="indicator"' in body
        assert 'name="cognitive_level"' in body
        assert 'name="difficulty"' in body
        assert 'id="edit-blueprints"' not in body
        generation.type_materi = MaterialType.TEXT
        response = generation_router.generation_detail(request, generation.id, FakeDB(), user)
        assert "Materi sumber $x^2$" in response.body.decode()
    finally:
        monkeypatch.undo()


def test_edit_blueprints_route_forwards_complete_form_rows(monkeypatch):
    generation = generation_fixture()
    captured = {}

    def fake_update(_self, generation_id, user, rows):
        captured.update(generation_id=generation_id, user=user, rows=rows)

    monkeypatch.setattr(GenerationService, "update_blueprints", fake_update)
    user = Namespace(id=generation.user_id)
    response = generation_router.edit_blueprints(
        generation.id,
        question_number=[3],
        material_topic=["Eksponen"],
        learning_objective=["Memahami pangkat"],
        indicator=["Menentukan nilai pangkat"],
        cognitive_level=["C2"],
        difficulty=["MEDIUM"],
        db=FakeDB(),
        user=user,
        _=None,
    )
    assert response.status_code == 303
    assert captured["generation_id"] == generation.id
    assert captured["user"] is user
    assert captured["rows"] == [{
        "question_number": 3,
        "material_topic": "Eksponen",
        "learning_objective": "Memahami pangkat",
        "indicator": "Menentukan nilai pangkat",
        "cognitive_level": "C2",
        "difficulty": "MEDIUM",
    }]


def test_profile_updates_nip_and_profile_fields(monkeypatch):
    teacher = Namespace(nip="old")
    user = Namespace(id=uuid4(), role=UserRole.GURU, teacher=teacher)
    captured = {}

    def fake_update_profile(_self, current_user, data, **_kwargs):
        captured.update(user=current_user, schema=data)

    monkeypatch.setattr(generation_router.AuthService, "update_profile", fake_update_profile)
    request = Namespace(client=Namespace(host="127.0.0.1"), headers={})
    response = generation_router.update_profile(request, "Nama Baru", "new@example.com", "NIP-123", FakeDB(), user)
    assert response.status_code == 303
    assert user.teacher.nip == "NIP-123"
    assert isinstance(captured["schema"], UserUpdateSchema)
    assert captured["schema"].full_name == "Nama Baru"


def test_profile_password_change_uses_existing_auth_service(monkeypatch):
    user = Namespace(id=uuid4())
    captured = {}

    def fake_change_password(_self, current_user, data, **_kwargs):
        captured.update(user=current_user, schema=data)

    monkeypatch.setattr(generation_router.AuthService, "change_password", fake_change_password)
    request = Namespace(client=Namespace(host="127.0.0.1"), headers={})
    response = generation_router.update_profile_password(request, "Current123!", "NextPass123!", "NextPass123!", FakeDB(), user)
    assert response.headers["location"] == "/auth/login?password_changed=1"
    assert isinstance(captured["schema"], PasswordChangeSchema)


def test_reference_rejects_private_network_before_http_request(monkeypatch):
    import socket

    from app.integrations.references import content_service

    monkeypatch.setattr(content_service.socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))])
    text, title, error = ReferenceContentService().fetch("http://127.0.0.1/resource", 1000)
    assert text is None
    assert title is None
    assert "publik" in error


def test_reference_rejects_credentials_and_nonstandard_ports():
    service = ReferenceContentService()
    assert "credential" in service.fetch("http://user:pass@example.com/", 100)[2]
    assert "Port" in service.fetch("http://example.com:8080/", 100)[2]


def test_docx_extractor_rejects_oversized_uncompressed_xml(monkeypatch):
    from app.integrations.material import docx_extractor

    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("word/document.xml", "x" * 128)
    monkeypatch.setattr(docx_extractor, "MAX_DOCUMENT_XML_BYTES", 64)
    with pytest.raises(ValueError, match="terlalu besar"):
        docx_extractor.extract_docx(payload.getvalue())


def test_material_extractor_reads_docx_and_rejects_empty_content():
    from app.integrations.material.extractor import MaterialExtractor

    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Materi uji</w:t></w:r></w:p></w:body></w:document>')
    extractor = MaterialExtractor()
    result = extractor.extract("materi.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", payload.getvalue(), 1024)
    assert result.text == "Materi uji"
    with pytest.raises(ValueError, match="kosong"):
        extractor.extract("materi.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"", 1024)


def test_docx_extractor_rejects_xml_entity_declarations():
    from app.integrations.material.docx_extractor import extract_docx

    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("word/document.xml", b'<!DOCTYPE doc [<!ENTITY ext SYSTEM "file:///etc/passwd">]><doc>&ext;</doc>')
    with pytest.raises(ValueError, match="eksternal"):
        extract_docx(payload.getvalue())


def test_pdf_extractor_caps_decompressed_streams():
    import zlib

    from app.integrations.material.pdf_extractor import extract_pdf

    payload = b"%PDF-1.7\nstream\n" + zlib.compress(b"x" * (25 * 1024 * 1024)) + b"\nendstream"
    with pytest.raises(ValueError, match="terlalu besar"):
        extract_pdf(payload)
