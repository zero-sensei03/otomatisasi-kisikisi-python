# Environment/configuration checklist

Values documented from `pyproject.toml`, `.env.example`, and settings classes. This file intentionally contains no credentials.

| Variable | Purpose | Default/source |
|---|---|---|
| `APP_ENV`, `DEBUG`, `APP_NAME` | App environment/display/debug | `Settings`; production should set DEBUG=false. |
| `SECRET_KEY` | Signed CSRF and session security | Required; provide a unique random production value. |
| `DATABASE_URL` | SQLAlchemy connection | Required; sample PostgreSQL+psycopg in `.env.example`. |
| `STORAGE_PATH`, `MAX_UPLOAD_SIZE` | Private uploaded material location and byte limit | storage, 10 MiB default. |
| `SESSION_COOKIE_NAME`, `SESSION_MAX_AGE`, `CSRF_COOKIE_NAME`, `CSRF_MAX_AGE` | Session/CSRF settings | See `.env.example`. |
| `AI_PROVIDER`, `AI_MODEL`, `GEMINI_API_KEY`, `AI_TIMEOUT_SECONDS` | Gemini REST configuration | gemini, gemini-3.1-flash-lite, secret unset, 90s. |
| `TIMEZONE` | Daily log date | Asia/Jakarta sample. |

The revision runner sets only `DATABASE_URL=sqlite://`, `SECRET_KEY=revision-test-only`, and `DEBUG=false` for test processes; `tests/conftest.py` resets DB to in-memory SQLite before app imports. Never reuse production environment for tests. The runner does not parse or expose `.env` contents.
