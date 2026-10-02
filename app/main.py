import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException

from app.core.config import get_settings
from app.routers import auth, health, pages, admin_users, audit_logs, generation

settings = get_settings()
templates = Jinja2Templates(directory="app/templates")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    # Use the application's safe error page instead of exposing tracebacks.
    debug=False,
)

app.state.settings = settings


def accepts_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "").lower()


async def render_error(request: Request, status_code: int, message: str, *, headers=None):
    if status_code == 401 and accepts_html(request):
        return RedirectResponse("/auth/login", status_code=303)
    if accepts_html(request):
        return templates.TemplateResponse(
            request=request,
            name="pages/error.html",
            context={"current_user": None, "status_code": status_code, "message": message},
            status_code=status_code,
            headers=headers,
        )
    return JSONResponse({"detail": message}, status_code=status_code, headers=headers)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    default_messages = {
        400: "Permintaan tidak dapat diproses.",
        401: "Silakan masuk untuk melanjutkan.",
        403: "Anda tidak memiliki izin untuk membuka halaman ini.",
        404: "Halaman atau data yang diminta tidak ditemukan.",
        405: "Metode permintaan ini tidak didukung.",
        422: "Data yang dikirim belum valid.",
    }
    message = exc.detail if isinstance(exc.detail, str) else default_messages.get(exc.status_code, "Permintaan tidak dapat diproses.")
    return await render_error(request, exc.status_code, message, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, _exc: RequestValidationError):
    if request.url.path == "/generation":
        logger.warning("generation stage=request_validation event=failed error_count=%s", len(_exc.errors()))
    return await render_error(request, 422, "Data yang dikirim belum valid. Periksa kembali isian Anda.")


@app.exception_handler(AppException)
async def handle_app_error(request: Request, exc: AppException):
    return await render_error(request, exc.status_code, exc.message)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, _exc: Exception):
    return await render_error(request, 500, "Terjadi kesalahan pada server. Silakan coba kembali.")

app.mount(
    "/static",
    StaticFiles(
        directory="app/static"
    ),
    name="static",
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(admin_users.router)
app.include_router(audit_logs.router)
app.include_router(generation.router)
