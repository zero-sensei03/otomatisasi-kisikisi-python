from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.routers import auth, health, pages, admin_users, audit_logs

settings = get_settings()

configure_logging()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.state.settings = settings

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