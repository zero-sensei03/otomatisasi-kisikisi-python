import logging
import re
import sys

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.routers import admin_users, audit_logs, auth, generation, health, pages

settings = get_settings()
templates = Jinja2Templates(directory="app/templates")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class CredentialRedactingFormatter(logging.Formatter):
    _credential_patterns = (
        re.compile(r"(?i)([\w+.-]+://[^:/\s@]+:)[^@\s]+(@)"),
        re.compile(r"(?i)([\"']?(?:x-goog-api-key|api[_ -]?key|password|passwd|secret|token|authorization)[\"']?\s*[:=]\s*[\"']?)[^\"',}\s]+"),
        re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    )

    def format(self, record):
        message = super().format(record)
        message = self._credential_patterns[0].sub(r"\1[REDACTED]\2", message)
        message = self._credential_patterns[1].sub(r"\1[REDACTED]", message)
        return self._credential_patterns[2].sub("[REDACTED]", message)

# Uvicorn/systemd logging configurations vary. Attach app logs to stdout
# explicitly so generation stage events reliably appear in journalctl.
application_logger = logging.getLogger("app")
application_logger.setLevel(logging.INFO)
application_logger.propagate = False
if not any(getattr(handler, "_kisikisi_app_handler", False) for handler in application_logger.handlers):
    app_handler = logging.StreamHandler(sys.stdout)
    app_handler.setFormatter(CredentialRedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    app_handler._kisikisi_app_handler = True
    application_logger.addHandler(app_handler)

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
async def handle_unexpected_error(request: Request, exc: Exception):
    generation_match = re.search(r"/generation/([0-9a-fA-F-]{36})(?:/|$)", request.url.path)
    logger.exception(
        "Unhandled request exception method=%s path=%s generation_id=%s exception_type=%s",
        request.method,
        request.url.path,
        generation_match.group(1) if generation_match else "none",
        type(exc).__name__,
    )
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
