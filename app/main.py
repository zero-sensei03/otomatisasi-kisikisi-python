import logging
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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


class DailyFileHandler(logging.Handler):
    """Write each record to a private file named by its local calendar day."""

    def __init__(self, directory: Path, timezone_name: str):
        super().__init__(logging.INFO)
        self.directory = directory
        self.timezone = ZoneInfo(timezone_name)
        self.current_day = None
        self.stream = None
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.directory.chmod(0o700)

    def emit(self, record):
        try:
            day = datetime.now(self.timezone).date().isoformat()
            if day != self.current_day:
                if self.stream is not None:
                    self.stream.close()
                path = self.directory / f"{day}.log"
                descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
                os.fchmod(descriptor, 0o600)
                self.stream = os.fdopen(descriptor, "a", encoding="utf-8")
                self.current_day = day
            self.stream.write(f"{self.format(record)}\n")
            self.stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        self.acquire()
        try:
            if self.stream is not None:
                self.stream.close()
                self.stream = None
            super().close()
        finally:
            self.release()


def configure_application_logging() -> None:
    file_handler = next(
        (handler for handler in logging.getLogger().handlers if getattr(handler, "_kisikisi_daily_handler", False)),
        None,
    )
    if file_handler is None:
        file_handler = DailyFileHandler(Path("logs"), settings.timezone)
        file_handler.setFormatter(
            CredentialRedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        file_handler._kisikisi_daily_handler = True

    root_logger = logging.getLogger()
    for handler in tuple(root_logger.handlers):
        root_logger.removeHandler(handler)
        if getattr(handler, "_kisikisi_daily_handler", False):
            continue
        handler.close()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    # Uvicorn installs its own console handlers before importing this module.
    # Clear them so application, access, and server logs all go through the file.
    for logger_name in ("app", "uvicorn", "uvicorn.error", "uvicorn.access"):
        named_logger = logging.getLogger(logger_name)
        for handler in tuple(named_logger.handlers):
            named_logger.removeHandler(handler)
            handler.close()
        named_logger.setLevel(logging.INFO)
        named_logger.propagate = True


configure_application_logging()
logging.getLogger("httpx").setLevel(logging.WARNING)

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
