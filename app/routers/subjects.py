from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.core.security import get_csrf_token, validate_csrf_token
from app.core.database import get_db
from app.models import User
from app.schemas.subject import SubjectCreate, SubjectUpdate
from app.services.subject import SubjectService


router = APIRouter(
    prefix="/subjects",
    tags=["Subjects"],
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
    service = SubjectService(db)

    subjects = service.get_all()

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="subjects/index.html",
        context={
            "current_user": current_user,
            "subjects": subjects,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.get(
    "/create",
    response_class=HTMLResponse,
)
def create_page(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="subjects/create.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post(
    "/create",
)
def create(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    description: str | None = Form(None),
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = SubjectService(db)

    try:
        service.create(
            SubjectCreate(
                code=code,
                name=name,
                description=description,
            )
        )

    except ValueError as exc:
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="subjects/create.html",
            context={
                "current_user": current_user,
                "csrf_token": get_csrf_token(request),
                "error": str(exc),
                "form": {
                    "code": code,
                    "name": name,
                    "description": description or "",
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url="/subjects",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/{subject_id}/edit",
    response_class=HTMLResponse,
)
def edit_page(
    subject_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = SubjectService(db)

    subject = service.get_by_id(subject_id)

    if not subject:
        return RedirectResponse(
            url="/subjects",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="subjects/edit.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "subject": subject,
        },
    )


@router.post(
    "/{subject_id}/edit",
)
def edit(
    subject_id: int,
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    description: str | None = Form(None),
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = SubjectService(db)

    try:
        subject = service.update(
            subject_id,
            SubjectUpdate(
                code=code,
                name=name,
                description=description,
            ),
        )

    except ValueError as exc:
        subject = service.get_by_id(subject_id)

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="subjects/edit.html",
            context={
                "current_user": current_user,
                "csrf_token": get_csrf_token(request),
                "subject": subject,
                "error": str(exc),
                "form": {
                    "code": code,
                    "name": name,
                    "description": description or "",
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/subjects",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{subject_id}/toggle-active",
)
def toggle_active(
    subject_id: int,
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = SubjectService(db)

    subject = service.get_by_id(subject_id)

    if not subject:
        return RedirectResponse(
            url="/subjects",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        service.set_active(
            subject_id,
            not subject.is_active,
        )

    except ValueError:
        pass

    return RedirectResponse(
        url="/subjects",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{subject_id}/delete",
)
def delete(
    subject_id: int,
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = SubjectService(db)

    try:
        service.delete(subject_id)

    except ValueError:
        pass

    return RedirectResponse(
        url="/subjects",
        status_code=status.HTTP_303_SEE_OTHER,
    )