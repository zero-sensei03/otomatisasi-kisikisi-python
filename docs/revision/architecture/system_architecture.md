# Arsitektur sistem (source audit)

## Komponen terverifikasi

- UI server-rendered memakai Jinja2 templates, CSS/JavaScript statis, dan browser. Tidak ditemukan aplikasi SPA terpisah.
- Backend Python/FastAPI dipasang melalui router `auth`, `pages`, `generation`, `admin_users`, `audit_logs`, dan `health` pada `app/main.py`.
- Services mengatur autentikasi, generasi, user management, dan audit; repositories menjalankan query SQLAlchemy.
- Database dikonfigurasi lewat `DATABASE_URL`; `.env.example` memakai PostgreSQL + psycopg. Schema dikelola model SQLAlchemy dan Alembic. Runner tidak memeriksa database server atau migration server.
- File upload PDF/DOCX diproses di `app/integrations/material/`; path privat berasal dari `STORAGE_PATH`. Hasil dan status generasi disimpan pada model generation serta tabel pertanyaan, opsi, kisi-kisi, referensi, sesi, user, audit, dan pengaturan.
- Referensi tambahan diambil melalui HTTPX dengan validasi skema/host/alamat dan redirect manual.
- AI memakai REST HTTPX ke Gemini Interactions API. Tidak ada SDK `google-genai` pada dependency proyek yang diperiksa.
- Generation dijalankan melalui `GenerationRunner` pada `ThreadPoolExecutor` proses aplikasi (maksimum dua worker), status disimpan dan dibaca melalui endpoint progress polling. Ini bukan antrean persisten eksternal. Multi-worker web dapat menciptakan lebih dari satu executor per proses.
- Ekspor hasil tersedia melalui generator DOCX berbasis template.

## Versi dependency

Versi yang dipatok di lockfile adalah rentang minimum `pyproject.toml`; versi runtime mesin harus direkam oleh `collect_evidence.py`. Versi Python proyek >=3.12. Provider mencatat `httpx.__version__`, Python, model konfigurasi, endpoint `/v1beta/interactions`, timeout 90 detik default, dan request format JSON. Nama model default `gemini-3.1-flash-lite`, dapat berubah melalui `AI_MODEL`. Ini identifikasi konfigurasi source, bukan bukti model tersedia/aktif pada akun Google tertentu.

## Data flow

Lihat [diagram](system_architecture.mmd) dan [urutan komunikasi](communication_flow.md). Diagram hanya memuat komponen ditemukan pada source.

## Endpoint penting

| Route | Peran |
|---|---|
| `GET /health` | Health response sederhana. |
| `GET/POST /auth/login`, `GET/POST /auth/register`, `POST /auth/logout`, `GET/PATCH /auth/me`, `POST /auth/change-password` | Authentication/session dan profil API. |
| `GET /generation`, `GET /generation/create`, `POST /generation` | Riwayat, form, dan submit generation (multipart untuk file). |
| `GET /generation/{id}/progress`, `GET /generation/{id}/progress/status` | Halaman progress dan polling status terotorisasi. |
| `GET /generation/{id}`, `GET /generation/{id}/material`, `GET /generation/{id}/export/{type}` | Detail, file sumber, ekspor. |
| `POST /generation/{id}/retry`, `POST /generation/{id}/delete`, `POST /generation/{id}/edit...` | Retry generation gagal, penghapusan, dan edit hasil; perubahan menggunakan CSRF. |
| `GET/POST /settings`, `GET/POST /profile` | Settings admin dan profil. |
| `/users/*`, `/audit-logs` | Admin user management dan audit log. |

Daftar route lengkap beserta form body ada pada decorator router aktual; tabel ini menyoroti alur yang relevan untuk penelitian, bukan OpenAPI export.

## Batas arsitektur

Background task berjalan in-process; restart paksa dapat menghentikan pekerjaan. Shutdown graceful menunggu executor. Tidak terverifikasi adanya Docker Compose, Dockerfile, CI pipeline, server aktual, reverse proxy aktif, atau konfigurasi systemd di repository. README utama memuat contoh operasional VPS systemd/Nginx; semua hostname, path, service dan setting harus dicocokkan dengan server target sebelum dipakai.
