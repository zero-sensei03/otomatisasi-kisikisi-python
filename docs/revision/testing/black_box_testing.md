# Black-box dan functional test

Functional tests menjalankan business logic/API handlers dengan SQLite terisolasi, fixture dokumen, dan mock untuk layanan eksternal. Unit/integration tidak memerlukan koneksi internet atau token Gemini. `test_scenarios.csv` memetakan perluasan dari skenario awal ke boundary, invalid, recovery, security, dan belum teruji manual. Actual results per run berada di `reports/summary/`.

## Metode/status

- **Automated**: pytest test-case pada checkout; bukti output/JUnit dihasilkan oleh runner.
- **Direct-handler/service**: memanggil router/service langsung, bukan request HTTP ASGI penuh. Bukan pengganti browser/black-box deployment.
- **Manual / Not Tested**: belum dijalankan karena membutuhkan server/browser, Gemini live, DNS publik, atau data reviewer. Tidak dihitung Pass.
- Panggilan Gemini real dan request berbayar tidak dilakukan. Database test in-memory; tidak memakai PostgreSQL production.

Jalankan `bash docs/revision/run_revision.sh tests`, lalu lihat JUnit dan CSV aktual. Skenario mengukur observable outcome; hidden implementation hanya diuji melalui unit suite.
