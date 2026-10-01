import math
import re
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_database, require_csrf, require_roles
from app.core.config import get_settings
from app.core.security import generate_csrf_token, sign_csrf_token
from app.integrations.exports.docx import TEMPLATES as DOCX_TEMPLATES, build_generation_docx
from app.models.generation import GenerationSetting
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.schemas.auth import PasswordChangeSchema, UserUpdateSchema
from app.schemas.generation import GenerationCreateSchema
from app.services.auth_service import AuthService
from app.services.generation_service import GenerationService

router = APIRouter(tags=["Generation"])
templates = Jinja2Templates(directory="app/templates")
admin_required = Depends(require_roles(UserRole.ADMIN))


def csrf_context():
    token = generate_csrf_token()
    return {"csrf_token": token, "csrf_signature": sign_csrf_token(token)}


def request_meta(request):
    return request.client.host if request.client else None, request.headers.get("user-agent")


@router.get("/generation", response_class=HTMLResponse)
def generation_list(request: Request, page: int = Query(1, ge=1), search: str | None = None, status: str | None = None, db: Session = Depends(get_database), user: User = Depends(get_current_user)):
    service = GenerationService(db)
    rows, total = service.list(user, page=page, per_page=20, search=search, status=status)
    return templates.TemplateResponse(request=request, name="pages/generation/index.html", context={"current_user": user, "generations": rows, "total": total, "page": page, "total_pages": max(1, math.ceil(total / 20)), "search": search or "", "status_filter": status or "", "quota": service.quota(user.id), **csrf_context()})


@router.get("/generation/create", response_class=HTMLResponse)
def create_page(request: Request, retry_from: uuid.UUID | None = Query(None), db: Session = Depends(get_database), user: User = Depends(get_current_user)):
    service = GenerationService(db)
    form = None
    notice = None
    if retry_from:
        previous = service.detail(retry_from, user)
        if previous.user_id != user.id:
            raise HTTPException(status_code=403, detail="Anda tidak dapat mengulang generation milik pengguna lain.")
        if previous.status.value != "FAILED":
            raise HTTPException(status_code=409, detail="Generation ini tidak berstatus gagal.")
        form = {"title": previous.title, "description": previous.description or "", "subject": previous.subject, "class_name": previous.class_name, "type_materi": previous.type_materi.value, "materi_text": previous.material_text, "references": [item.url for item in previous.references], "total_multiple_choice": previous.total_multiple_choice, "total_short_answer": previous.total_short_answer, "total_essay": previous.total_essay}
        if not previous.material_text.strip():
            notice = "Materi dari percobaan lama tidak tersimpan. Masukkan kembali materi atau unggah ulang file untuk mencoba lagi."
    return templates.TemplateResponse(request=request, name="pages/generation/create.html", context={"current_user": user, "quota": service.quota(user.id), "csrf": csrf_context(), "error": None, "form": form, "notice": notice})


@router.post("/generation", response_class=HTMLResponse)
def create_generation(request: Request, title: str = Form(...), description: str | None = Form(None), subject: str = Form(...), class_name: str = Form(...), type_materi: str = Form(...), materi_text: str | None = Form(None), references: list[str] = Form(default=[]), total_multiple_choice: int = Form(0), total_short_answer: int = Form(0), total_essay: int = Form(0), materi_file: UploadFile | None = File(None), db: Session = Depends(get_database), user: User = Depends(get_current_user), _: None = Depends(require_csrf)):
    try:
        schema = GenerationCreateSchema(title=title, description=description, subject=subject, class_name=class_name, type_materi=type_materi, materi_text=materi_text, references=references, total_multiple_choice=total_multiple_choice, total_short_answer=total_short_answer, total_essay=total_essay)
        ip, agent = request_meta(request)
        generation = GenerationService(db).create(schema, user, upload=materi_file, ip_address=ip, user_agent=agent)
        if generation.status.value == "FAILED":
            return RedirectResponse(f"/generation/{generation.id}?error=Generation%20gagal.%20Silakan%20coba%20kembali.", status_code=303)
        return RedirectResponse(f"/generation/{generation.id}", status_code=303)
    except (ValidationError, ValueError, HTTPException) as exc:
        db.rollback()
        error = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else getattr(exc, "detail", str(exc))
        return templates.TemplateResponse(request=request, name="pages/generation/create.html", context={"current_user": user, "quota": GenerationService(db).quota(user.id), "csrf": csrf_context(), "error": error, "form": {"title": title, "description": description or "", "subject": subject, "class_name": class_name, "type_materi": type_materi, "materi_text": materi_text or "", "references": references, "total_multiple_choice": total_multiple_choice, "total_short_answer": total_short_answer, "total_essay": total_essay}}, status_code=422)


@router.get("/generation/{generation_id}", response_class=HTMLResponse)
def generation_detail(request: Request, generation_id: uuid.UUID, db: Session = Depends(get_database), user: User = Depends(get_current_user)):
    generation = GenerationService(db).detail(generation_id, user)
    return templates.TemplateResponse(request=request, name="pages/generation/detail.html", context={"current_user": user, "generation": generation, "csrf": csrf_context(), "is_owner": generation.user_id == user.id, "error": request.query_params.get("error"), "docx_templates": DOCX_TEMPLATES})


@router.get("/generation/{generation_id}/edit", response_class=HTMLResponse)
def generation_edit_page(request: Request, generation_id: uuid.UUID, db: Session = Depends(get_database), user: User = Depends(get_current_user)):
    generation = GenerationService(db).detail(generation_id, user)
    if generation.user_id != user.id:
        raise HTTPException(status_code=403, detail="Anda hanya dapat mengubah generation milik sendiri.")
    return templates.TemplateResponse(request=request, name="pages/generation/edit.html", context={"current_user": user, "generation": generation, "csrf": csrf_context()})


@router.get("/generation/{generation_id}/material")
def generation_material_file(generation_id: uuid.UUID, db: Session = Depends(get_database), user: User = Depends(get_current_user)):
    generation = GenerationService(db).detail(generation_id, user)
    if generation.type_materi.value != "FILE" or not generation.material_file_path:
        raise HTTPException(status_code=404, detail="File materi tidak ditemukan.")
    storage_root = (Path(get_settings().storage_path) / "generation_private").resolve()
    try:
        file_path = Path(generation.material_file_path).resolve(strict=True)
        if not file_path.is_relative_to(storage_root) or not file_path.is_file():
            raise ValueError("Invalid private file path")
    except (OSError, RuntimeError, ValueError):
        raise HTTPException(status_code=404, detail="File materi tidak ditemukan.") from None
    extension = file_path.suffix.lower()
    media_type = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}.get(extension)
    if media_type is None:
        raise HTTPException(status_code=404, detail="File materi tidak ditemukan.")
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(generation.material_file_name or "materi").name).strip("-.") or "materi"
    disposition = "inline" if extension == ".pdf" else "attachment"
    return FileResponse(file_path, media_type=media_type, headers={"Content-Disposition": f'{disposition}; filename="{filename}"', "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@router.post("/generation/{generation_id}/edit")
def update_generation_metadata(generation_id: uuid.UUID, title: str = Form(...), description: str | None = Form(None), subject: str = Form(...), class_name: str = Form(...), db: Session = Depends(get_database), user: User = Depends(get_current_user), _: None = Depends(require_csrf)):
    GenerationService(db).update_metadata(generation_id, user, title=title, description=description, subject=subject, class_name=class_name)
    return RedirectResponse(f"/generation/{generation_id}?success=Informasi%20generation%20disimpan.", status_code=303)


@router.post("/generation/{generation_id}/retry", response_class=HTMLResponse)
def retry_generation(request: Request, generation_id: uuid.UUID, db: Session = Depends(get_database), user: User = Depends(get_current_user), _: None = Depends(require_csrf)):
    ip, agent = request_meta(request)
    try:
        generation = GenerationService(db).retry(generation_id, user, ip_address=ip, user_agent=agent)
        if generation.status.value == "FAILED":
            return RedirectResponse(f"/generation/{generation.id}?error=Generation%20gagal.%20Silakan%20coba%20kembali.", status_code=303)
        return RedirectResponse(f"/generation/{generation.id}", status_code=303)
    except HTTPException as exc:
        db.rollback()
        if exc.status_code == 409 and "tidak tersimpan" in str(exc.detail):
            return RedirectResponse(f"/generation/create?retry_from={generation_id}", status_code=303)
        raise


@router.post("/generation/{generation_id}/delete")
def delete_generation(generation_id: uuid.UUID, db: Session = Depends(get_database), user: User = Depends(get_current_user), _: None = Depends(require_csrf)):
    GenerationService(db).delete(generation_id, user)
    return RedirectResponse("/generation?success=Generation%20dihapus.", status_code=303)


@router.post("/generation/{generation_id}/edit/summary")
def edit_summary(generation_id: uuid.UUID, summary: str = Form(...), db: Session = Depends(get_database), user: User = Depends(get_current_user), _: None = Depends(require_csrf)):
    GenerationService(db).update_summary(generation_id, user, summary)
    return RedirectResponse(f"/generation/{generation_id}?success=Rangkuman%20disimpan.", status_code=303)


@router.post("/generation/{generation_id}/edit/question/{question_id}")
def edit_question(generation_id: uuid.UUID, question_id: uuid.UUID, question: str = Form(...), answer: str = Form(...), explanation: str = Form(...), option_a: str = Form(""), option_b: str = Form(""), option_c: str = Form(""), option_d: str = Form(""), db: Session = Depends(get_database), user: User = Depends(get_current_user), _: None = Depends(require_csrf)):
    options = [{"label": label, "text": value} for label, value in zip("ABCD", (option_a, option_b, option_c, option_d))]
    GenerationService(db).update_question(generation_id, question_id, user, question=question, answer=answer, explanation=explanation, options=options)
    return RedirectResponse(f"/generation/{generation_id}?success=Soal%20disimpan.", status_code=303)


@router.post("/generation/{generation_id}/edit/blueprints")
def edit_blueprints(generation_id: uuid.UUID, question_number: list[int] = Form(...), material_topic: list[str] = Form(...), learning_objective: list[str] = Form(...), indicator: list[str] = Form(...), cognitive_level: list[str] = Form(...), difficulty: list[str] = Form(...), db: Session = Depends(get_database), user: User = Depends(get_current_user), _: None = Depends(require_csrf)):
    rows = [dict(question_number=n, material_topic=t, learning_objective=o, indicator=i, cognitive_level=c, difficulty=d) for n, t, o, i, c, d in zip(question_number, material_topic, learning_objective, indicator, cognitive_level, difficulty)]
    GenerationService(db).update_blueprints(generation_id, user, rows)
    return RedirectResponse(f"/generation/{generation_id}?success=Kisi-kisi%20disimpan.", status_code=303)


@router.get("/generation/{generation_id}/export/{export_type}")
def export_generation(generation_id: uuid.UUID, export_type: str, template: str | None = None, db: Session = Depends(get_database), user: User = Depends(get_current_user)):
    generation = GenerationService(db).detail(generation_id, user)
    template_key = {"summary": "materi", "blueprint": "kisi_kisi", "explanation": "pembahasan"}.get(export_type)
    if export_type == "questions":
        template_key = template
    if template_key not in DOCX_TEMPLATES:
        raise HTTPException(status_code=400, detail="Template export tidak valid.")
    stream = build_generation_docx(template_key, generation)
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", generation.title).strip("-.")[:60] or "generation"
    filename = "rangkuman-eksponen.docx" if export_type == "summary" else f"{template_key}-{safe_title}.docx"
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/settings", response_class=HTMLResponse)
def generation_settings_page(request: Request, db: Session = Depends(get_database), user: User = admin_required):
    rows = db.scalars(select(GenerationSetting).order_by(GenerationSetting.key)).all()
    settings = {row.key: row.value for row in rows}
    return templates.TemplateResponse(request=request, name="pages/admin/settings/index.html", context={"current_user": user, "settings": settings, "csrf": csrf_context(), "success": request.query_params.get("success"), "error": request.query_params.get("error")})


@router.post("/settings")
def update_generation_settings(generation_free_limit: int = Form(..., gt=0, le=1_000_000), generation_cost_per_generate: float = Form(..., ge=0, le=1_000_000), generation_enabled: str = Form("false"), generation_max_questions_per_generate: int = Form(..., gt=0, le=500), generation_max_material_characters: int = Form(..., gt=0, le=1_000_000), generation_max_reference_characters: int = Form(..., gt=0, le=250_000), db: Session = Depends(get_database), user: User = admin_required, _: None = Depends(require_csrf)):
    values = {"generation.free_limit": str(generation_free_limit), "generation.cost_per_generate": str(generation_cost_per_generate), "generation.enabled": "true" if generation_enabled == "true" else "false", "generation.max_questions_per_generate": str(generation_max_questions_per_generate), "generation.max_material_characters": str(generation_max_material_characters), "generation.max_reference_characters": str(generation_max_reference_characters)}
    for key, value in values.items():
        row = db.scalar(select(GenerationSetting).where(GenerationSetting.key == key))
        if row:
            row.value, row.is_active = value, True
    db.commit()
    return RedirectResponse("/settings?success=Pengaturan%20generation%20disimpan.", status_code=303)


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="pages/profile.html", context={"current_user": user, "csrf": csrf_context(), "success": request.query_params.get("success"), "error": request.query_params.get("error")})


@router.post("/profile")
def update_profile(request: Request, full_name: str = Form(...), email: str = Form(...), nip: str = Form(""), db: Session = Depends(get_database), user: User = Depends(get_current_user), _: None = Depends(require_csrf)):
    try:
        schema = UserUpdateSchema(email=email, full_name=full_name)
        if user.role == UserRole.GURU:
            if user.teacher:
                user.teacher.nip = nip.strip() or None
            else:
                user.teacher = Teacher(user_id=user.id, nip=nip.strip() or None)
        ip, agent = request_meta(request)
        AuthService(db).update_profile(user, schema, ip_address=ip, user_agent=agent)
        return RedirectResponse("/profile?success=Profil%20disimpan.", status_code=303)
    except Exception as exc:
        db.rollback()
        message = str(getattr(exc, "detail", "Profil gagal disimpan."))
        return RedirectResponse(f"/profile?error={quote(message)}", status_code=303)


@router.post("/profile/password")
def update_profile_password(request: Request, current_password: str = Form(...), new_password: str = Form(...), new_password_confirmation: str = Form(...), db: Session = Depends(get_database), user: User = Depends(get_current_user), _: None = Depends(require_csrf)):
    try:
        data = PasswordChangeSchema(current_password=current_password, new_password=new_password, new_password_confirmation=new_password_confirmation)
        ip, agent = request_meta(request)
        AuthService(db).change_password(user, data, ip_address=ip, user_agent=agent)
        return RedirectResponse("/auth/login?password_changed=1", status_code=303)
    except (ValidationError, HTTPException) as exc:
        db.rollback()
        message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else exc.detail
        return RedirectResponse(f"/profile?error={quote(str(message))}", status_code=303)
