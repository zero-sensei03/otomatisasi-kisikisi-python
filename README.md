# Otomatisasi Kisi Kisi

Sistem otomatisasi penyusunan kisi-kisi dan soal berbasis AI
sebagai pendukung evaluasi pembelajaran.


## Technology Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- Pydantic
- Jinja2
- HTMX
- Vanilla JavaScript
- CSS
- uv


## Development

Create virtual environment:

```bash
uv venv
```

Activate:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
uv sync
```

Run application:

```bash
uv run uvicorn app.main:app --reload
```

Run tests:

```bash
uv run pytest
```

Health Check

```bash
GET /health
```

Karena `uv init` dan `uv add` akan mengelola dependency secara otomatis, **jangan menulis dependency manual dua kali**.

Setelah seluruh command di atas selesai, bagian dependency akan dikelola oleh `uv`.

Verifikasi:

```bash
uv lock
```