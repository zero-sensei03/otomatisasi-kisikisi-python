# Alur komunikasi

```mermaid
sequenceDiagram
  actor Guru
  participant Browser
  participant API as FastAPI generation router
  participant DB as SQLAlchemy/PostgreSQL
  participant Worker as GenerationRunner
  participant Extract as Extractor / Reference service
  participant Gemini as Gemini REST API
  Guru->>Browser: Isi form teks atau upload PDF/DOCX, opsional URL
  Browser->>API: POST /generation (session + CSRF)
  API->>API: Validasi schema, auth, file size/type
  API->>DB: Simpan record PENDING + progress awal
  API->>Worker: Submit bytes, nama/MIME dan schema
  API-->>Browser: Redirect ke /generation/{id}/progress
  Worker->>DB: Tandai PROCESSING
  Worker->>Extract: Ekstrak PDF/DOCX dan fetch tiap URL
  Extract-->>Worker: Konten dan status sumber
  Worker->>Gemini: HTTPX POST JSON (model, prompt, no store)
  Gemini-->>Worker: JSON response envelope
  Worker->>Worker: Validasi Pydantic + consistency/retry terbatas
  Worker->>DB: Simpan summary, questions, options, blueprint, durations
  Browser->>API: GET progress/status (polling)
  API->>DB: Baca status/progress milik user
  API-->>Browser: Status aktual dan pesan aman
  Browser->>API: GET /generation/{id}
  API->>DB: Ambil detail authorized
  API-->>Browser: HTML detail dan hasil
```

Endpoint submit merespons sebelum generation selesai; browser refresh hanya membaca status dan tidak mengirim generation baru. Isi upload dibaca sebelum background submit lalu direkonstruksi sebagai `UploadFile` worker dengan MIME. Hasil PDF/DOCX privat dilayani dengan endpoint ownership-checked.
