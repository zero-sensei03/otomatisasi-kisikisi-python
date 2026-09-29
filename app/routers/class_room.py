from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.core.security import validate_csrf_token
from app.core.database import get_db
from app.models import User
from app.schemas.class_room import (
    ClassRoomCreate,
    ClassRoomUpdate,
)
from app.services.class_room import ClassRoomService
from app.core.security import get_csrf_token

router = APIRouter(
    prefix="/classes",
    tags=["Classes"],
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
    service = ClassRoomService(db)

    class_rooms = service.get_all()

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="class_rooms/index.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "class_rooms": class_rooms,
        },
    )


@router.get(
    "/create",
    response_class=HTMLResponse,
)
def create_form(
    request: Request,
    current_user: User = Depends(require_admin),
):

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="class_rooms/create.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "error": None,
        },
    )


@router.post("/create")
def create(
    request: Request,
    name: str = Form(...),
    grade_level: str = Form(...),
    description: str | None = Form(None),
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = ClassRoomService(db)

    try:
        service.create(
            ClassRoomCreate(
                name=name,
                grade_level=grade_level,
                description=description,
            )
        )

    except ValueError as exc:
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="class_rooms/create.html",
            context={
                "current_user": current_user,
                "csrf_token": csrf_token,
                "error": str(exc),
                "form": {
                    "name": name,
                    "grade_level": grade_level,
                    "description": description or "",
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        "/classes",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/{class_room_id}/edit",
    response_class=HTMLResponse,
)
def edit_form(
    class_room_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):

    service = ClassRoomService(db)

    class_room = service.get_by_id(
        class_room_id
    )

    if not class_room:
        return RedirectResponse(
            "/classes",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="class_rooms/edit.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
            "class_room": class_room,
            "error": None,
        },
    )


@router.post("/{class_room_id}/edit")
def edit(
    class_room_id: int,
    request: Request,
    name: str = Form(...),
    grade_level: str = Form(...),
    description: str | None = Form(None),
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = ClassRoomService(db)

    try:
        service.update(
            class_room_id,
            ClassRoomUpdate(
                name=name,
                grade_level=grade_level,
                description=description,
            ),
        )

    except ValueError as exc:
        class_room = service.get_by_id(
            class_room_id
        )

        if not class_room:
            return RedirectResponse(
                "/classes",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="class_rooms/edit.html",
            context={
                "current_user": current_user,
                "csrf_token": csrf_token,
                "class_room": class_room,
                "error": str(exc),
                "form": {
                    "name": name,
                    "grade_level": grade_level,
                    "description": description or "",
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        "/classes",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{class_room_id}/toggle-active")
def toggle_active(
    class_room_id: int,
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = ClassRoomService(db)

    class_room = service.get_by_id(
        class_room_id
    )

    if class_room:
        service.set_active(
            class_room_id,
            not class_room.is_active,
        )

    return RedirectResponse(
        "/classes",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{class_room_id}/delete")
def delete(
    class_room_id: int,
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    service = ClassRoomService(db)

    try:
        service.delete(class_room_id)

    except ValueError:
        pass

    return RedirectResponse(
        "/classes",
        status_code=status.HTTP_303_SEE_OTHER,
    )