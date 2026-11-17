# Audit keamanan berbasis source

Audit ini membaca source/configuration; bukan pentest, audit server, atau jaminan keamanan.

| Area | Implementasi yang ditemukan | Batas / tindak lanjut |
|---|---|---|
| Authentication | Session cookie, sesi DB, expiry, user active; password Argon2 (`time_cost=3`, `memory_cost=65536`, parallelism 4). | Pastikan production menggunakan HTTPS dan secret kuat/rotasi. |
| Authorization | Depends current user/role; service detail membatasi owner, admin policy, file download lewat ownership. | Tambah integration ASGI tests unauthorized/IDOR end-to-end. |
| CSRF | Form token signed HMAC SHA-256 dan per-route dependency. | Audit konfigurasi cookie/browser terhadap deployment aktual. |
| Input/schema | Pydantic/FastAPI forms dan validasi generation; cognitive C1-C4 aktif. | Validasi input bukan validasi semantik AI. |
| Upload/path | Ext/MIME/size, private storage, random path and size limits; extractor bounded. | MIME dapat dipalsukan; parser PDF minimalis; periksa permissions/mount server dan archive resource limits. |
| URL / SSRF | HTTP(S), deny local/non-global DNS/IP, credentials, manual redirect revalidation, timeout/size cap, peer check, `trust_env=False`. | Resolver/egress firewall server tetap penting; lakukan pentest DNS rebinding/IPv6 di deployment. |
| SQL | SQLAlchemy bound expressions, `hide_parameters=True`. | Belum dilakukan dynamic SQL injection pentest. |
| Secrets | `.env` settings, key tidak dalam database; redacting logger. | Jangan kirim `.env`; cek permission dan secrets management server. `config.py` punya default admin credentials development; production wajib override. |
| Error/log | Error page aman, stack trace di server log; daily file mode 0600/dir 0700 dan redaction formatter. | Log retention/rotation dan disk monitoring server perlu dikonfigurasi/verifikasi. |
| CORS/TLS | Tidak ada explicit CORS middleware ditemukan; Uvicorn config bukan bukti TLS. | Nginx/TLS hanya contoh README, bukan server aktif yang diverifikasi. |
| Data privacy | Gemini payload menetapkan `store=false`; upload area private; materi tidak semestinya dicatat penuh. | Retensi DB/file/backup dan kebijakan Google API bergantung akun/terms; belum diverifikasi. |

Jangan menyimpulkan seluruh sistem aman dari unit test. Sebelum deployment, verifikasi HTTPS, firewall, database network, permission `.env`/storage/log, backup access, dependency audit, dan uji akses lintas user.
