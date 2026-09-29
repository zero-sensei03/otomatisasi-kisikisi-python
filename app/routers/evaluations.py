from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import (
    get_csrf_token,
    validate_csrf_token,
)
from app.models import (
    ClassRoom,
    EvaluationStatus,
    Subject,
    Teacher,
    User,
    UserRole,
)
from app.schemas.evaluation import (
    EvaluationCreate,
    EvaluationStatus as _EvaluationStatus,
    EvaluationUpdate,
)
from app.services.evaluation import EvaluationService


router = APIRouter(
    prefix="/evaluations",
    tags=["Evaluations"],
)


def get_subjects(
    db: Session,
    active_only: bool = False,
) -> list[Subject]:
    statement = select(Subject)

    if active_only:
        statement = statement.where(
            Subject.is_active.is_(True)
        )

    statement = statement.order_by(
        Subject.name.asc()
    )

    return list(
        db.scalars(statement).all()
    )


def get_classes(
    db: Session,
    active_only: bool = False,
) -> list[ClassRoom]:
    statement = select(ClassRoom)

    if active_only:
        statement = statement.where(
            ClassRoom.is_active.is_(True)
        )

    statement = statement.order_by(
        ClassRoom.grade_level.asc(),
        ClassRoom.name.asc(),
    )

    return list(
        db.scalars(statement).all()
    )


def get_teachers(
    db: Session,
) -> list[Teacher]:
    statement = (
        select(Teacher)
        .join(Teacher.user)
        .where(User.is_active.is_(True))
        .order_by(User.full_name.asc())
    )

    return list(
        db.scalars(statement).all()
    )


def get_filter_context(
    db: Session,
) -> dict:
    return {
        "subjects": get_subjects(db),
        "classes": get_classes(db),
    }


def parse_optional_int(
    value: str | None,
) -> int | None:
    """
    Mengubah query parameter integer yang kosong
    menjadi None.

    Contoh:
        None -> None
        "" -> None
        "   " -> None
        "5" -> 5
    """
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def parse_optional_status(
    value: str | None,
) -> EvaluationStatus | None:
    """
    Mengubah query parameter status yang kosong
    menjadi None.

    Contoh:
        None -> None
        "" -> None
        "DRAFT" -> EvaluationStatus.DRAFT
    """
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    try:
        return EvaluationStatus(value)
    except ValueError:
        return None


@router.get(
    "",
    response_class=HTMLResponse,
)
def index(
    request: Request,
    search: str | None = Query(
        default=None,
    ),
    subject_id: str | None = Query(
        default=None,
    ),
    class_id: str | None = Query(
        default=None,
    ),
    semester: str | None = Query(
        default=None,
    ),
    academic_year: str | None = Query(
        default=None,
    ),
    evaluation_status: str | None = Query(
        default=None,
        alias="status",
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    per_page: int = Query(
        default=10,
        ge=5,
        le=100,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    service = EvaluationService(db)

    normalized_subject_id = parse_optional_int(
        subject_id
    )

    normalized_class_id = parse_optional_int(
        class_id
    )

    normalized_status = parse_optional_status(
        evaluation_status
    )

    normalized_search = (
        search.strip()
        if search and search.strip()
        else None
    )

    normalized_semester = (
        semester.strip()
        if semester and semester.strip()
        else None
    )

    normalized_academic_year = (
        academic_year.strip()
        if academic_year and academic_year.strip()
        else None
    )

    pagination = service.paginate(
        current_user=current_user,
        search=normalized_search,
        subject_id=normalized_subject_id,
        class_id=normalized_class_id,
        semester=normalized_semester,
        academic_year=normalized_academic_year,
        status=normalized_status,
        page=page,
        per_page=per_page,
    )

    filters = {
        "search": normalized_search or "",
        "subject_id": normalized_subject_id,
        "class_id": normalized_class_id,
        "semester": normalized_semester or "",
        "academic_year": normalized_academic_year or "",
        "status": (
            normalized_status.value
            if normalized_status
            else ""
        ),
        "per_page": per_page,
    }

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="evaluations/index.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "evaluations": pagination["items"],
            "pagination": pagination,
            "filters": filters,
            "subjects": get_subjects(db),
            "classes": get_classes(db),
            "statuses": list(
                EvaluationStatus
            ),
        },
    )


@router.get(
    "/create",
    response_class=HTMLResponse,
)
def create_form(
    request: Request,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    teachers = []

    if current_user.role == UserRole.ADMIN:
        teachers = get_teachers(db)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="evaluations/create.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "subjects": get_subjects(
                db,
                active_only=True,
            ),
            "classes": get_classes(
                db,
                active_only=True,
            ),
            "teachers": teachers,
            "statuses": list(
                EvaluationStatus
            ),
            "error": None,
            "form": {},
        },
    )


@router.post("/create")
def create(
    request: Request,
    subject_id: int = Form(...),
    class_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    semester: str = Form(...),
    academic_year: str = Form(...),
    status_value: EvaluationStatus = Form(
        EvaluationStatus.DRAFT,
        alias="status",
    ),
    teacher_id: int | None = Form(
        default=None
    ),
    csrf_token: str = Form(...),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    if current_user.role == UserRole.GURU:
        if not current_user.teacher:
            raise ValueError(
                "Akun guru belum memiliki data guru."
            )

        teacher_id = current_user.teacher.id

    elif current_user.role == UserRole.ADMIN:
        if not teacher_id:
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="evaluations/create.html",
                context={
                    "current_user": current_user,
                    "csrf_token": csrf_token,
                    "subjects": get_subjects(
                        db,
                        active_only=True,
                    ),
                    "classes": get_classes(
                        db,
                        active_only=True,
                    ),
                    "teachers": get_teachers(db),
                    "statuses": list(
                        EvaluationStatus
                    ),
                    "error": "Guru wajib dipilih.",
                    "form": {
                        "subject_id": subject_id,
                        "class_id": class_id,
                        "name": name,
                        "description": description,
                        "semester": semester,
                        "academic_year": academic_year,
                        "status": status_value.value,
                        "teacher_id": teacher_id,
                    },
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    service = EvaluationService(db)

    try:
        service.create(
            EvaluationCreate(
                teacher_id=teacher_id,
                subject_id=subject_id,
                class_id=class_id,
                name=name,
                description=description,
                semester=semester,
                academic_year=academic_year,
                status=status_value,
            ),
            current_user=current_user,
        )

    except ValueError as exc:
        teachers = []

        if current_user.role == UserRole.ADMIN:
            teachers = get_teachers(db)

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="evaluations/create.html",
            context={
                "current_user": current_user,
                "csrf_token": csrf_token,
                "subjects": get_subjects(
                    db,
                    active_only=True,
                ),
                "classes": get_classes(
                    db,
                    active_only=True,
                ),
                "teachers": teachers,
                "statuses": list(
                    EvaluationStatus
                ),
                "error": str(exc),
                "form": {
                    "subject_id": subject_id,
                    "class_id": class_id,
                    "name": name,
                    "description": description,
                    "semester": semester,
                    "academic_year": academic_year,
                    "status": status_value.value,
                    "teacher_id": teacher_id,
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        "/evaluations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/{evaluation_id}",
    response_class=HTMLResponse,
)
def detail(
    evaluation_id: int,
    request: Request,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    service = EvaluationService(db)

    try:
        evaluation = service.get_by_id(
            evaluation_id,
            current_user,
        )

    except ValueError:
        return RedirectResponse(
            "/evaluations",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="evaluations/detail.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "evaluation": evaluation,
        },
    )


@router.get(
    "/{evaluation_id}/edit",
    response_class=HTMLResponse,
)
def edit_form(
    evaluation_id: int,
    request: Request,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    service = EvaluationService(db)

    try:
        evaluation = service.get_by_id(
            evaluation_id,
            current_user,
        )

    except ValueError:
        return RedirectResponse(
            "/evaluations",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    teachers = []

    if current_user.role == UserRole.ADMIN:
        teachers = get_teachers(db)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="evaluations/edit.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "evaluation": evaluation,
            "subjects": get_subjects(
                db,
                active_only=True,
            ),
            "classes": get_classes(
                db,
                active_only=True,
            ),
            "teachers": teachers,
            "statuses": list(
                EvaluationStatus
            ),
            "error": None,
            "form": {},
        },
    )


@router.post(
    "/{evaluation_id}/edit",
)
def edit(
    evaluation_id: int,
    request: Request,
    subject_id: int = Form(...),
    class_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    semester: str = Form(...),
    academic_year: str = Form(...),
    status_value: EvaluationStatus = Form(
        EvaluationStatus.DRAFT,
        alias="status",
    ),
    csrf_token: str = Form(...),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = EvaluationService(db)

    try:
        service.update(
            evaluation_id,
            EvaluationUpdate(
                subject_id=subject_id,
                class_id=class_id,
                name=name,
                description=description,
                semester=semester,
                academic_year=academic_year,
                status=status_value,
            ),
            current_user=current_user,
        )

    except ValueError as exc:
        try:
            evaluation = service.get_by_id(
                evaluation_id,
                current_user,
            )

        except ValueError:
            return RedirectResponse(
                "/evaluations",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        teachers = []

        if current_user.role == UserRole.ADMIN:
            teachers = get_teachers(db)

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="evaluations/edit.html",
            context={
                "current_user": current_user,
                "csrf_token": csrf_token,
                "evaluation": evaluation,
                "subjects": get_subjects(
                    db,
                    active_only=True,
                ),
                "classes": get_classes(
                    db,
                    active_only=True,
                ),
                "teachers": teachers,
                "statuses": list(
                    EvaluationStatus
                ),
                "error": str(exc),
                "form": {
                    "subject_id": subject_id,
                    "class_id": class_id,
                    "name": name,
                    "description": description,
                    "semester": semester,
                    "academic_year": academic_year,
                    "status": status_value.value,
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        f"/evaluations/{evaluation_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{evaluation_id}/status",
)
def change_status(
    evaluation_id: int,
    request: Request,
    status_value: EvaluationStatus = Form(
        ...,
        alias="status",
    ),
    csrf_token: str = Form(...),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = EvaluationService(db)

    try:
        service.set_status(
            evaluation_id,
            status_value,
            current_user,
        )

    except ValueError:
        pass

    return RedirectResponse(
        "/evaluations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{evaluation_id}/delete",
)
def delete(
    evaluation_id: int,
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = EvaluationService(db)

    try:
        service.delete(
            evaluation_id,
            current_user,
        )

    except ValueError:
        pass

    return RedirectResponse(
        "/evaluations",
        status_code=status.HTTP_303_SEE_OTHER,
    )