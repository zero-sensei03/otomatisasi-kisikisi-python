from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.security import get_csrf_token, validate_csrf_token
from app.models import User
from app.models import Subject
from app.schemas.learning_outcome import (
    LearningOutcomeCreate,
    LearningOutcomeUpdate,
)
from app.services.learning_outcome import (
    LearningOutcomeService,
)


router = APIRouter(
    prefix="/learning-outcomes",
    tags=["Learning Outcomes"],
)


@router.get(
    "",
    response_class=HTMLResponse,
)
def index(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = LearningOutcomeService(db)

    learning_outcomes = service.get_all()

    subjects = list(
        db.query(Subject)
        .order_by(Subject.name.asc())
        .all()
    )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="learning_outcomes/index.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "learning_outcomes": learning_outcomes,
            "subjects": subjects,
        },
    )


@router.get(
    "/create",
    response_class=HTMLResponse,
)
def create_form(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    subjects = list(
        db.query(Subject)
        .filter(
            Subject.is_active.is_(True)
        )
        .order_by(Subject.name.asc())
        .all()
    )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="learning_outcomes/create.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "subjects": subjects,
            "error": None,
        },
    )


@router.post("/create")
def create(
    request: Request,
    subject_id: int = Form(...),
    code: str = Form(...),
    description: str = Form(...),
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = LearningOutcomeService(db)

    try:
        service.create(
            LearningOutcomeCreate(
                subject_id=subject_id,
                code=code,
                description=description,
            )
        )

    except ValueError as exc:
        subjects = list(
            db.query(Subject)
            .filter(
                Subject.is_active.is_(True)
            )
            .order_by(Subject.name.asc())
            .all()
        )

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="learning_outcomes/create.html",
            context={
                "current_user": current_user,
                "csrf_token": csrf_token,
                "subjects": subjects,
                "error": str(exc),
                "form": {
                    "subject_id": subject_id,
                    "code": code,
                    "description": description,
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        "/learning-outcomes",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/{learning_outcome_id}/edit",
    response_class=HTMLResponse,
)
def edit_form(
    learning_outcome_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = LearningOutcomeService(db)

    learning_outcome = service.get_by_id(
        learning_outcome_id
    )

    if not learning_outcome:
        return RedirectResponse(
            "/learning-outcomes",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    subjects = list(
        db.query(Subject)
        .filter(
            Subject.is_active.is_(True)
        )
        .order_by(Subject.name.asc())
        .all()
    )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="learning_outcomes/edit.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "learning_outcome": learning_outcome,
            "subjects": subjects,
            "error": None,
        },
    )


@router.post("/{learning_outcome_id}/edit")
def edit(
    learning_outcome_id: int,
    request: Request,
    subject_id: int = Form(...),
    code: str = Form(...),
    description: str = Form(...),
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = LearningOutcomeService(db)

    try:
        service.update(
            learning_outcome_id,
            LearningOutcomeUpdate(
                subject_id=subject_id,
                code=code,
                description=description,
            ),
        )

    except ValueError as exc:
        learning_outcome = service.get_by_id(
            learning_outcome_id
        )

        if not learning_outcome:
            return RedirectResponse(
                "/learning-outcomes",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        subjects = list(
            db.query(Subject)
            .filter(
                Subject.is_active.is_(True)
            )
            .order_by(Subject.name.asc())
            .all()
        )

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="learning_outcomes/edit.html",
            context={
                "current_user": current_user,
                "csrf_token": csrf_token,
                "learning_outcome": learning_outcome,
                "subjects": subjects,
                "error": str(exc),
                "form": {
                    "subject_id": subject_id,
                    "code": code,
                    "description": description,
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        "/learning-outcomes",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{learning_outcome_id}/toggle-active")
def toggle_active(
    learning_outcome_id: int,
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = LearningOutcomeService(db)

    learning_outcome = service.get_by_id(
        learning_outcome_id
    )

    if learning_outcome:
        service.set_active(
            learning_outcome_id,
            not learning_outcome.is_active,
        )

    return RedirectResponse(
        "/learning-outcomes",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{learning_outcome_id}/delete")
def delete(
    learning_outcome_id: int,
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = LearningOutcomeService(db)

    try:
        service.delete(
            learning_outcome_id
        )

    except ValueError:
        pass

    return RedirectResponse(
        "/learning-outcomes",
        status_code=status.HTTP_303_SEE_OTHER,
    )