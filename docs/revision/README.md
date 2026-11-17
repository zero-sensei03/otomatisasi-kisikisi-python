# Ghiai.site — Paket Revisi Penelitian

Dokumentasi, konfigurasi, source script, dan runner paket ini dilacak Git. Hanya output di `reports/`, screenshot aktual, dan evidence manual diabaikan Git. Dengan demikian `git pull` membawa dokumentasi dan automasi, sedangkan hasil setiap run tetap lokal/server dan dapat diunduh terpisah. Jangan memasukkan data pribadi atau credential ke evidence.

## Status bukti

Dokumentasi teknis dirangkum dari source pada checkout saat paket dibuat. Hasil otomatis hanya dinyatakan setelah runner dijalankan. Benchmark default menggunakan parser PDF lokal dan input sintetis deterministik, bukan Gemini/API dan bukan beban produksi. Evaluasi kualitas AI dan screenshot aplikasi memerlukan hasil nyata serta peninjau/manual login sehingga belum tersedia otomatis; template disediakan dan hasil kosong tidak dianggap lulus.

## Jalankan

```bash
bash docs/revision/run_revision.sh
```

Mode tersedia: `all` (default), `tests`, `coverage`, `performance`, `report`. Artefak ditulis di `docs/revision/reports/`. Script memakai pytest fixture yang memaksa SQLite in-memory bagi test; tidak menjalankan migration, tidak menghubungi Gemini, dan tidak mengubah database production. Lihat `architecture/`, `technical/`, dan `testing/` untuk batasan dan metodologi.

## Hasil run tidak dilacak Git

Folder output otomatis dibuat oleh runner dan tidak di-commit. Setelah `git pull`, script tetap tersedia. Jika hasil perlu disimpan ke komputer lokal, transfer hanya folder `reports/` dari host ke komputer lokal dengan `rsync`; tidak perlu menyalin script atau dokumentasi secara manual.

### Alur server setelah `git pull`

`git pull` memperbarui source, README, dokumentasi dan script revision. Hasil run tetap dikecualikan Git. Di server, cukup jalankan:

```bash
# Dari direktori project di server; path boleh relatif atau absolut.
bash docs/revision/run_revision.sh
```

Runner otomatis menggunakan virtualenv project jika sudah berisi pytest, pytest-cov, dan coverage. Jika dependency test belum ada, runner menggunakan/menyiapkan `.venv-revision/` terpisah lalu meminta `uv sync --frozen --group dev`; virtualenv production tidak diubah. Sinkronisasi pertama mungkin memerlukan akses package registry. Anda dapat menentukan lokasi virtualenv di luar project/dekat path privat server dengan `REVISION_VENV=/ABS/PATH/REVISION_VENV`. Atau berikan interpreter yang sudah siap lewat `REVISION_PYTHON=/ABS/PATH/REVISION_VENV/bin/python`.

```bash
# Opsional, bila venv revision ingin diletakkan di luar project:
REVISION_VENV=/srv/kisikisi/revision-venv bash docs/revision/run_revision.sh
```

Tidak ada transfer folder revision manual lagi. Tetap gunakan user yang boleh menulis ke project dan laporan, serta jangan menyimpan secret ke log. `uv sync` hanya menyiapkan dependency di environment testing dan tidak menjalankan migration. Jika server tidak dapat mengakses package registry, siapkan venv revision dari wheel/cache yang disetujui operator dan set `REVISION_PYTHON`.

Mode `all` (default) memeriksa Python/dependency/config, menjalankan unit, integration dan seluruh test, coverage, benchmark PDF sintetis lokal, lalu menyusun laporan. `tests` menjalankan suite; `coverage` menjalankan suite dengan coverage; `performance` hanya benchmark parser lokal; `report` membangun dashboard dan ZIP dari artefak yang sudah ada. Tidak ada migration, request Gemini live, atau load test production. Jika exit code gagal, lihat log di `reports/summary/` dan periksa hasil yang gagal; runner tetap mengumpulkan laporan bila memungkinkan.

Ambil report kembali ke komputer lokal:

```bash
rsync -av USER@SERVER:/ABSOLUTE/PATH/PROJECT/docs/revision/reports/ docs/revision/reports/
```

Buka `docs/revision/reports/coverage/coverage_summary.html` di browser lokal. Gunakan **Print / Save as PDF** untuk menyimpan PDF; ZIP tersedia di `reports/revision_reports.zip`. Tinjau artefak sebelum membagikan dan pastikan tidak berisi data pengguna atau rahasia.

## Reviewer checklist

| Nomor | Aspek reviewer | File bukti/status |
|---:|---|---|
| 1 | System Architecture | `architecture/system_architecture.md`, `system_architecture.mmd`, `communication_flow.md` |
| 2 | Tidak ada temuan pada daftar reviewer | — |
| 3 | AI Technology | `technical/ai_technology.md`; konfigurasi runtime dari `reports/summary/environment.json`, bukan bukti API live |
| 4 | Prompt Engineering | `technical/prompt_engineering.md` |
| 5 | Document Processing | `technical/document_processing.md` |
| 6 | Black Box Testing | `testing/black_box_testing.md`, `testing/test_scenarios.csv`, hasil run di `reports/black_box/` |
| 7 | Output Accuracy | `testing/output_accuracy.md` dan template CSV; belum ada evaluasi manusia/ground truth |
| 8 | System Performance | `testing/performance_testing.md`, hasil parser lokal di `reports/performance/`; bukan benchmark server |
| 9 | System Security | `technical/system_security.md`; audit source, bukan pentest |
| 10 | User Interface | `screenshots/README.md`; screenshot aktual belum dikumpulkan |
| 11 | System Replicability | `technical/system_replicability.md` |
| 12 | Testing Documentation | `testing/TESTING_EVIDENCE.md`, `reports/summary/`, `reports/coverage/` |
| 13 | Tidak ada temuan pada daftar reviewer | — |
| 14 | Tidak ada temuan pada daftar reviewer | — |
