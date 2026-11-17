# Reviewer 11 — System Replicability

## Temuan

Reviewer menyatakan informasi technical development belum cukup untuk memungkinkan peneliti lain mereplikasi sistem. Dokumen ini merangkum komponen aktual, versi runtime yang direkam, konfigurasi yang diperlukan, dan batas informasi host yang belum tersedia.

## Teknologi yang digunakan

| Lapisan | Teknologi aktual |
|---|---|
| Bahasa | Python; project mensyaratkan `>=3.12`. Versi runtime dicatat di `reports/summary/environment.json`. |
| Web framework | FastAPI. Versi dependency/runtime dicatat pada evidence. |
| UI | Jinja2 server-rendered templates, HTML/CSS/JavaScript statis; tidak ditemukan SPA terpisah. |
| ORM / migration | SQLAlchemy dan Alembic. |
| Database production | PostgreSQL melalui driver psycopg; `.env.example` memakai URL `postgresql+psycopg`. Versi PostgreSQL server belum diketahui. |
| AI | Google Gemini REST API melalui HTTPX, bukan Google SDK. Endpoint `https://generativelanguage.googleapis.com/v1beta/interactions`. |
| Testing | pytest dan pytest-cov; runner membuat hasil JUnit dan coverage HTML/JSON/XML/CSV/TXT. |
| Dependency management | `uv`, `pyproject.toml`, `uv.lock`. |

Pada evidence lokal, model runtime yang terbaca dari konfigurasi adalah `gemini-3.5-flash-lite`, timeout 90 detik. Model dapat berbeda di server melalui `AI_MODEL`; ini konfigurasi yang terbaca, bukan bukti request live atau jaminan ketersediaan model pada akun tersebut. `.env.example` memiliki nilai default berbeda (`gemini-3.1-flash-lite`). Laporan hanya mencatat apakah API key tersedia, bukan nilainya.

## Prosedur replikasi

1. Siapkan Python 3.12+, `uv`, dan Git.
2. Clone repository lalu pasang dependency aplikasi sesuai lockfile dengan `uv sync --frozen --no-dev`.
3. Konfigurasikan `.env` server dengan PostgreSQL, secret key, storage, dan nilai AI. Jangan masukkan `.env` ke Git atau laporan.
4. Jangan menjalankan migration sebagai bagian dari revision tests. Migration production mengikuti prosedur release dan backup tersendiri.
5. `git pull` mengambil dokumentasi dan script revision; hanya output report, screenshot aktual, dan evidence manual dikecualikan Git.
6. Jalankan tes dalam environment testing terpisah. Fixture memaksa SQLite in-memory dan layanan AI dimock; test tidak menggunakan PostgreSQL production maupun melakukan request Gemini.
7. Simpan `environment.json`, JUnit, coverage, benchmark, commit id, dirty-worktree status, dan timestamp sebagai metadata replikasi.

Implementasi dan konfigurasi yang bisa direplikasi ada di `pyproject.toml`, `uv.lock`, `.env.example`, `app/core/config.py`, `app/integrations/ai/settings.py`, dan `app/integrations/ai/gemini_provider.py`.

## Batas replikasi

Server produksi aktual tidak dapat diinspeksi dari checkout ini. Versi PostgreSQL server, OS, service manager, hostname/path, resource mesin, firewall, dan availability model Gemini harus dicatat oleh operator server. Generation berjalan dalam executor in-process; tidak ditemukan queue broker eksternal. Variasi materi, model, konfigurasi dan provider dapat mengubah isi maupun latency hasil AI.
