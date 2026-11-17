# Evaluasi performa

`scripts/run_performance.py` mengukur waktu ekstraksi PDF lokal pada fixture sintetik yang dibentuk deterministik dan menulis setiap sampel CSV/JSON beserta environment. Ini benchmark mikro untuk parser saja. Ia tidak mengukur upload HTTP, OCR, URL live, DB PostgreSQL, Gemini/network, total generation, atau server. Fixture sintetis bukan dokumen representatif.

Sample count dan statistik min/max/mean/median/p95 tersedia setelah runner. P95 ditandai deskriptif dan tidak layak untuk inferensi ketika sampel kecil. Tidak ada angka baseline yang dihardcode. Spesifikasi host dikumpulkan dari OS/Python; jika tak tersedia ditulis null. Pengujian server/live model belum dilakukan.

Untuk evaluasi yang representatif, jalankan pada staging non-production, kumpulkan beberapa PDF/DOCX yang diizinkan/pseudonim, ukur upload/extract/reference/AI/total dengan timestamps service yang tersedia, minimal 30 observasi per kondisi untuk p95, konfigurasikan concurrency rendah, catat resource server, model dan kondisi jaringan. Hindari load test agresif di production dan jangan masukkan isi dokumen ke report.
