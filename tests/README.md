# Testing

Test menggunakan `pytest` dan `pytest-cov`, yang sudah terdaftar di dependency group
`dev`. Siapkan environment dengan `uv sync --group dev`. Test tidak memerlukan API key
Gemini atau koneksi internet untuk skenario yang memakai mock.

`tests/conftest.py` menetapkan `DATABASE_URL=sqlite://` sebelum aplikasi diimpor agar
engine yang dibuat saat import tidak menunjuk ke PostgreSQL dari `.env`. Unit tests
menggunakan fake session/monkeypatch; API test memakai dependency override. Tidak ada
test yang mengirim request generation berbayar ke Gemini.

## Menjalankan test

```bash
uv run pytest tests/unit -v
uv run pytest tests/integration -v
uv run pytest tests/ -v
```

## Coverage

```bash
uv run pytest tests/ --cov=app --cov-report=term-missing
uv run pytest tests/ --cov=app --cov-report=html
uv run pytest tests/ --cov=app --cov-report=xml
```

Report HTML berada di `htmlcov/index.html`; report XML di `coverage.xml`. Report terminal
dan HTML menunjukkan coverage package, file, dan baris yang belum diuji.

## Menulis test baru

- Tempatkan unit tests validasi/business logic di `tests/unit/`, API tests di
  `tests/integration/`, dan gunakan fixture bersama dari `tests/conftest.py`.
- Gunakan pola Arrange, Act, Assert. Assert hasil/status aktual dan satu perilaku utama
  per test.
- Mock filesystem/network/Gemini/session jika integrasi eksternal bukan fokus test.
- Gunakan `monkeypatch` atau `unittest.mock`; jangan menggunakan API key nyata.
- Jangan mengarahkan test ke database development. Jika menambah akses database, gunakan
  database sementara khusus test dan pastikan fixture membersihkan data.
