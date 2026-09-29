from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.core.dependencies import get_current_user
from app.core.security import get_csrf_token
from app.models import User


router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates",
)


@router.get("/dashboard")
def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/index.html",
        context={
            "current_user": current_user,
            "csrf_token": get_csrf_token(request),
        },
    )
