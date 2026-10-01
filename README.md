# Otomatisasi Kisi-Kisi

Aplikasi web untuk membantu guru menyusun rangkuman materi, soal, pembahasan, dan kisi-kisi pembelajaran menggunakan AI. Hasil disimpan terstruktur sehingga dapat diedit kembali atau diekspor sebagai dokumen Word.

## Fitur

- Login, registrasi sesuai konfigurasi aplikasi, sesi, dan proteksi CSRF.
- Pengelolaan pengguna dan role `ADMIN` serta `GURU`.
- Pembuatan generation dari materi teks atau file PDF/DOCX.
- Referensi materi dari satu atau beberapa URL.
- Rangkuman, pilihan ganda, isian, essay, pembahasan, serta kisi-kisi.
- Edit judul dan informasi generation, rangkuman, setiap soal, dan seluruh kisi-kisi.
- Generation ulang atas data generation yang gagal.
- Kuota gratis harian yang dapat diatur admin.
- Ekspor DOCX menggunakan lima template yang tersedia.
- Riwayat generation, audit log, profil, dan pengaturan generation.

## Teknologi

- Python 3.12 atau lebih baru
- FastAPI dan Uvicorn
- PostgreSQL, SQLAlchemy, dan Alembic
- Pydantic Settings dan Jinja2
- `uv` untuk dependency dan virtual environment
- Gemini API untuk generation AI tahap pertama

## Struktur penting

```text
app/
├── core/                  # konfigurasi aplikasi, database, keamanan, dependency
├── integrations/
│   ├── ai/                # kontrak provider dan Gemini
│   ├── exports/           # pembuat dokumen DOCX
│   ├── material/          # ekstraksi PDF/DOCX
│   └── references/        # pengambilan materi dari URL
├── models/                # model SQLAlchemy
├── repositories/          # akses database
├── routers/               # route FastAPI
├── schemas/               # validasi input aplikasi
├── services/              # business logic
├── static/                # CSS, JavaScript, dan gambar
└── templates/             # halaman Jinja dan template DOCX
migrations/                # riwayat Alembic
scripts/seed_admin.py      # pembuatan akun admin awal
```

## Persiapan lokal

### 1. Pasang prasyarat

Pasang Python 3.12+, PostgreSQL, Git, dan `uv`. Ikuti petunjuk instalasi resmi untuk sistem operasi masing-masing. Pastikan service PostgreSQL berjalan.

### 2. Ambil source code dan dependency

```bash
git clone REPOSITORY_URL
cd tesis-otomatisasi-kisikisi
uv sync
```

Ganti `REPOSITORY_URL` dengan URL repository project. `uv sync` memasang dependency dari `pyproject.toml` dan `uv.lock`.

### 3. Siapkan PostgreSQL

Buat database dan user aplikasi. Contoh untuk PostgreSQL lokal:

```bash
sudo -u postgres psql
```

Kemudian di prompt `psql`:

```sql
CREATE USER kisikisi WITH PASSWORD 'GANTI_DENGAN_PASSWORD_DATABASE';
CREATE DATABASE tesis_kisikisi OWNER kisikisi;
\q
```

Jika password database mengandung karakter khusus pada URL, encode karakter tersebut sesuai format URL. Jangan menggunakan kredensial contoh di server publik.

### 4. Siapkan environment

```bash
cp .env.example .env
```

Edit `.env` dan atur minimal:

```dotenv
APP_NAME=KisiKisi AI
APP_ENV=development
DEBUG=true
SECRET_KEY=GANTI_DENGAN_SECRET_ACAK_PANJANG
DATABASE_URL=postgresql+psycopg://kisikisi:PASSWORD_DATABASE@127.0.0.1:5432/tesis_kisikisi
STORAGE_PATH=storage
MAX_UPLOAD_SIZE=10485760
TIMEZONE=Asia/Jakarta

ADMIN_EMAIL=admin@contoh.id
ADMIN_PASSWORD=GANTI_DENGAN_PASSWORD_ADMIN_KUAT
ADMIN_NAME=Administrator

AI_PROVIDER=gemini
AI_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=ISI_API_KEY_DARI_GOOGLE_AI_STUDIO
```

Buat `SECRET_KEY` acak, misalnya:

```bash
openssl rand -hex 32
```

`DEBUG` harus berupa `true` atau `false`, bukan nama environment seperti `release`. API key Gemini dibaca dari environment, tidak disimpan ke database. Gunakan model yang tersedia dan aktif pada Google AI Studio untuk project API key Anda. Model dapat diganti melalui `AI_MODEL` tanpa mengubah kontrak input/output AI.

Jangan commit `.env` ke Git atau mengirimkan nilainya melalui log, issue, maupun chat. `.env.example` hanya berisi contoh tanpa API key.

### 5. Buat tabel dan akun admin

Jalankan migrasi yang ada:

```bash
uv run alembic upgrade head
```

Buat admin awal dari `ADMIN_EMAIL`, `ADMIN_PASSWORD`, dan `ADMIN_NAME` di environment:

```bash
uv run python scripts/seed_admin.py
```

Script dapat dijalankan kembali; jika email admin sudah ada, akun tidak dibuat duplikat. Migration deployment menggunakan `upgrade head`; jangan membuat root migration baru.

### 6. Jalankan aplikasi lokal

```bash
uv run uvicorn app.main:app --reload
```

Buka `http://127.0.0.1:8000`. Pemeriksaan service tersedia di `/health`.

Untuk menjalankan test yang tersedia:

```bash
uv run pytest
```

## Halaman dan route utama

| URL | Fungsi |
| --- | --- |
| `/auth/login` | Login |
| `/auth/register` | Registrasi jika diaktifkan di aplikasi |
| `/dashboard` | Dashboard setelah login |
| `/generation` | Riwayat generation pengguna; admin dapat melihat semua |
| `/generation/create` | Form generation baru |
| `/generation/{id}` | Detail generation, edit, dan ekspor |
| `/settings` | Pengaturan generation untuk admin |
| `/users` | Pengelolaan pengguna untuk admin |
| `/audit-logs` | Riwayat audit untuk admin |
| `/profile` | Profil pengguna |
| `/health` | Status aplikasi |

Generation hanya dapat diubah atau dihapus oleh pemiliknya sesuai aturan aplikasi. Admin dapat melihat seluruh generation, tetapi tidak dapat mengedit atau menghapus generation milik pengguna lain.

## AI generation

Provider dipilih dari `AI_PROVIDER`. Provider yang terpasang saat ini adalah Gemini. Pengaturan utamanya:

```dotenv
AI_PROVIDER=gemini
AI_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=...
```

API key diperoleh melalui Google AI Studio. Jangan menaruh key di source code, template, atau database. Provider memvalidasi keluaran terhadap kontrak terstruktur; hasil yang tidak valid akan diminta ulang secara terbatas dan generation ditandai gagal jika tetap tidak sesuai.

Isi materi, referensi, dan jawaban AI tidak dicatat ke log aplikasi. Saat generation gagal, pengguna menerima pesan aman dan status kegagalan tersimpan di riwayat generation.

## File materi dan storage

PDF dan DOCX disimpan di direktori privat yang ditentukan `STORAGE_PATH`. Pastikan direktori tersebut dapat ditulis oleh user service aplikasi dan tidak dipasang sebagai direktori static/public oleh web server. File menggunakan nama penyimpanan acak; nama file asli hanya dipakai untuk tampilan/unduhan yang telah melewati pengecekan ownership.

Batas ukuran upload dikendalikan `MAX_UPLOAD_SIZE`. Batas panjang materi, referensi, kuota harian, jumlah soal maksimum, dan status fitur diatur oleh admin pada menu Pengaturan Generation.

## Deploy dan setup VPS Ubuntu

Panduan ini menggunakan satu VPS Ubuntu, PostgreSQL lokal, systemd, dan Nginx sebagai reverse proxy. Ganti domain, user, password, lokasi source, dan email sesuai server.

### 1. Siapkan server

Masuk ke VPS melalui SSH, lalu pasang komponen dasar:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git curl ca-certificates build-essential libpq-dev postgresql postgresql-contrib nginx
```

Pasang `uv` menggunakan petunjuk resmi `uv` untuk Linux dan Python 3.12 menggunakan paket Python yang didukung versi Ubuntu Anda. Periksa:

```bash
python3 --version
uv --version
uv python install 3.12
sudo systemctl status postgresql --no-pager
```

Buat user sistem untuk menjalankan aplikasi:

```bash
sudo adduser --system --group --home /srv/kisikisi kisikisi
```

### 2. Siapkan database production

```bash
sudo -u postgres psql
```

```sql
CREATE USER kisikisi WITH PASSWORD 'PASSWORD_DATABASE_YANG_KUAT';
CREATE DATABASE tesis_kisikisi OWNER kisikisi;
\q
```

Batasi akses database untuk loopback/local host jika database berada di VPS yang sama. Jangan membuka port PostgreSQL ke internet.

### 3. Pasang source dan dependency

```bash
sudo -u kisikisi git clone REPOSITORY_URL /srv/kisikisi/app
cd /srv/kisikisi/app
sudo -u kisikisi uv sync --frozen --no-dev
```

Perintah `uv` harus tersedia untuk user service. Jika `uv` dipasang hanya di akun SSH pribadi, pasang ulang ke lokasi bersama yang aman atau gunakan path executable `uv` yang diketahui user service.

Siapkan direktori privat untuk file upload:

```bash
sudo install -d -o kisikisi -g kisikisi -m 700 /var/lib/kisikisi/storage
sudo install -d -o kisikisi -g kisikisi -m 700 /var/lib/kisikisi/storage/generation_private
```

### 4. Simpan konfigurasi production

Buat file `.env` di direktori aplikasi. File ini diabaikan Git dan hanya dapat dibaca user service:

```bash
sudo -u kisikisi install -m 600 /dev/null /srv/kisikisi/app/.env
sudo -u kisikisi nano /srv/kisikisi/app/.env
```

Isi dengan nilai milik server:

```dotenv
APP_NAME=KisiKisi AI
APP_ENV=production
DEBUG=false
SECRET_KEY=HASIL_OPENSSL_RAND_HEX_32
DATABASE_URL=postgresql+psycopg://kisikisi:PASSWORD_DATABASE@127.0.0.1:5432/tesis_kisikisi
STORAGE_PATH=/var/lib/kisikisi/storage
MAX_UPLOAD_SIZE=10485760
TIMEZONE=Asia/Jakarta
SESSION_COOKIE_NAME=kisikisi_session
SESSION_MAX_AGE=28800
CSRF_COOKIE_NAME=kisikisi_csrf
CSRF_MAX_AGE=3600
ADMIN_EMAIL=admin@domain-anda.id
ADMIN_PASSWORD=PASSWORD_ADMIN_KUAT
ADMIN_NAME=Administrator
AI_PROVIDER=gemini
AI_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=API_KEY_GEMINI_MILIK_SERVER
```

Hasilkan secret dengan `openssl rand -hex 32`. Pastikan `DATABASE_URL` benar dan password yang mengandung karakter khusus sudah di-URL-encode. File `.env` tidak boleh dapat dibaca user lain.

### 5. Terapkan migration dan buat admin

Karena konfigurasi dibaca dari `.env` di direktori kerja project, jalankan migration dan seed sebagai user aplikasi:

```bash
sudo -u kisikisi bash -lc 'cd /srv/kisikisi/app && .venv/bin/alembic upgrade head && .venv/bin/python scripts/seed_admin.py'
```

Jangan menaruh secret langsung sebagai argumen command karena dapat tertinggal di shell history. Setelah masuk, ganti password sementara jika Anda menggunakannya.

### 6. Daftarkan systemd service

Buat unit service:

```bash
sudo nano /etc/systemd/system/kisikisi.service
```

Isi:

```ini
[Unit]
Description=Otomatisasi Kisi-Kisi Web
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=kisikisi
Group=kisikisi
WorkingDirectory=/srv/kisikisi/app
ExecStart=/srv/kisikisi/app/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --no-access-log --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=5
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/kisikisi/storage

[Install]
WantedBy=multi-user.target
```

Aktifkan service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kisikisi
sudo systemctl status kisikisi --no-pager
curl http://127.0.0.1:8000/health
```

Jika path `uvicorn` berbeda, cek dengan `sudo -u kisikisi /srv/kisikisi/app/.venv/bin/python -m uvicorn --version`. Sesuaikan `ExecStart` berdasarkan virtual environment project. Bila menggunakan worker lebih dari satu, pastikan resource VPS cukup.

### 7. Pasang Nginx

Buat konfigurasi site, ganti `app.domain-anda.id` dengan domain yang DNS A/AAAA-nya mengarah ke VPS:

```bash
sudo nano /etc/nginx/sites-available/kisikisi
```

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name app.domain-anda.id;

    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }
}
```

Aktifkan dan periksa konfigurasi:

```bash
sudo ln -s /etc/nginx/sites-available/kisikisi /etc/nginx/sites-enabled/kisikisi
sudo nginx -t
sudo systemctl reload nginx
```

Jika symlink sudah ada, jangan buat symlink duplikat. Atur firewall agar hanya membuka SSH, HTTP, dan HTTPS; port aplikasi `8000` dan PostgreSQL tidak perlu terbuka ke internet. Aktifkan UFW setelah memastikan akses SSH diizinkan:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

### 8. Aktifkan HTTPS

Setelah DNS domain mengarah ke server dan port 80/443 dapat diakses, pasang sertifikat TLS dari penyedia sertifikat yang Anda pilih. Untuk Certbot pada Ubuntu:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d app.domain-anda.id
sudo certbot renew --dry-run
```

Uji login, pembuatan generation, unduhan DOCX, file materi, dan endpoint `/health` melalui HTTPS setelah konfigurasi selesai.

## Operasional VPS

### Periksa dan restart service

```bash
sudo systemctl status kisikisi --no-pager
sudo systemctl restart kisikisi
sudo systemctl restart nginx
```

Service dijalankan tanpa access log Uvicorn. Untuk melihat pesan startup atau error runtime yang dikeluarkan server:

```bash
sudo journalctl -u kisikisi -n 100 --no-pager
sudo journalctl -u kisikisi -f
```

Log yang pernah memuat request/response AI sudah dihapus; prompt, isi materi, hasil model, API key, dan isi dokumen tidak dicatat ke console aplikasi.

### Perbarui aplikasi

```bash
cd /srv/kisikisi/app
sudo -u kisikisi git pull
sudo -u kisikisi uv sync --frozen --no-dev
sudo systemctl stop kisikisi
# Terapkan migration baru bila release memerlukannya:
sudo -u kisikisi uv run alembic upgrade head
sudo systemctl start kisikisi
sudo systemctl status kisikisi --no-pager
```

Lakukan backup database dan storage privat sebelum perubahan release besar. Gunakan migration yang sudah tercatat di repository; jangan menghapus migration yang sudah pernah dijalankan.

### Backup database

Contoh dump PostgreSQL terkompresi:

```bash
sudo -u postgres pg_dump -Fc tesis_kisikisi > /lokasi-backup/tesis_kisikisi.dump
```

Simpan backup di lokasi terpisah dari VPS dan atur masa retensi. Storage upload ada di `/var/lib/kisikisi/storage`; backup terpisah jika file sumber perlu dipertahankan. Uji prosedur restore secara berkala.

## Troubleshooting

- **`ValidationError` untuk `DEBUG`**: pastikan `DEBUG=true` atau `DEBUG=false`, bukan `development`, `production`, atau `release`.
- **Koneksi database gagal**: cek `DATABASE_URL`, service PostgreSQL, nama database, password, dan hak akses user.
- **Tabel belum ada**: jalankan `uv run alembic upgrade head` dengan environment database yang benar.
- **Generation gagal**: cek `AI_PROVIDER`, `AI_MODEL`, API key Gemini, status kuota, konektivitas keluar HTTPS, dan ketersediaan model/API di Google AI Studio. Detail sensitif provider tidak ditampilkan ke pengguna.
- **Upload gagal**: cek `MAX_UPLOAD_SIZE`, `client_max_body_size` Nginx, serta permission `STORAGE_PATH` dan `generation_private`.
- **Service tidak mulai**: cek status systemd, lokasi virtual environment, `WorkingDirectory`, file environment, dan koneksi database.
- **Akun admin awal**: periksa `ADMIN_EMAIL` dan environment yang dipakai saat menjalankan `scripts/seed_admin.py`.

## Keamanan konfigurasi

- Gunakan `DEBUG=false` di production.
- Gunakan secret, password database, password admin, dan API key yang kuat dan unik.
- Jangan commit `.env`, file database, upload privat, maupun secret ke repository.
- Batasi permission file environment dan direktori upload.
- Jangan expose Uvicorn atau PostgreSQL secara langsung ke internet; gunakan reverse proxy HTTPS.
- Putar API key jika pernah terekspos dan perbarui nilai environment service.
