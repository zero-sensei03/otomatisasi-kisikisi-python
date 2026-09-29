from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates

from app.core.config import settings
from app.routers import auth, dashboard, users, subjects, class_room, learning_outcomes, evaluations


BASE_DIR = Path(__file__).resolve().parent


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)


app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age,
    same_site="lax",
    https_only=False,
)


app.mount(
    "/static",
    StaticFiles(
        directory=BASE_DIR / "static",
    ),
    name="static",
)

templates = Jinja2Templates(
    directory=BASE_DIR / "templates",
)

app.state.templates = templates


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(subjects.router)
app.include_router(class_room.router)
app.include_router(learning_outcomes.router)
app.include_router(evaluations.router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "application": settings.app_name,
    }
