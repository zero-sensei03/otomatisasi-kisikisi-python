from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import (
    get_current_user,
    get_current_user_optional,
)
from app.models.user import User


router = APIRouter(
    tags=["Pages"]
)

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get(
    "/",
    response_class=HTMLResponse,
)
def home(
    current_user: User | None = Depends(get_current_user_optional),
):
    destination = "/dashboard" if current_user else "/auth/login"
    return RedirectResponse(destination, status_code=303)


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
def dashboard(
    request: Request,
    current_user: User = Depends(
        get_current_user
    ),
):
    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard.html",
        context={
            "title": "Dashboard",
            "current_user": current_user,
        },
    )

@router.get(
    "/ui-showcase",
    response_class=HTMLResponse,
)
def ui_showcase(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/ui-showcase.html",
        context={
            "page_title": "UI Showcase",
        },
    )
