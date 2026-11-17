# Evaluasi kualitas output AI (bukan functional test)

Unit/integration success hanya membuktikan alur kontrak dan persistence menggunakan mocked provider. Ia **tidak** mengukur akurasi faktual, pedagogis, atau kualitas Gemini. Tidak ada dataset gold/ground truth yang tervalidasi dalam repository; hasil kualitas belum dinilai dan tidak ada persentase accuracy yang diklaim.

## Protokol evaluasi manusia

1. Arsipkan input materi dan referensi yang benar-benar diberikan, output generation (soal, kisi-kisi, jawaban), model string, timestamp, serta generation id yang sudah dipseudonimkan. Simpan lokal/terbatas dan hapus PII.
2. Dua penilai independen (guru bidang studi dan penilai kedua) beri skor tiap kriteria pada setiap butir. Penilai melihat sumber yang sama sebagai ground truth.
3. Skala: 1 = salah/tidak didukung; 2 = banyak kekurangan; 3 = cukup namun perlu revisi; 4 = baik dengan revisi minor; 5 = tepat/kuat. Untuk kriteria yang tak berlaku, pakai N/A dan keluarkan dari denominator.
4. Catat bukti halaman/paragraf sumber untuk setiap skor 1–2. Adjudikasi beda skor >1 oleh penilai ketiga atau diskusi terdokumentasi.
5. Laporkan jumlah generation dan butir, model/config, rentang tanggal, rata-rata/median per kriteria, skor antarpenilai (weighted kappa atau ICC bila dihitung), missing/N/A, dan failure cases. Jangan gabungkan skor rubrik sebagai “akurasi” tanpa definisi.

## Rubrik per soal/kisi-kisi

| Kriteria | Pertanyaan evaluasi |
|---|---|
| Relevansi soal ke sumber | Apakah seluruh fakta yang diperlukan ada di materi/referensi terpilih? |
| Ketepatan kunci dan pembahasan | Apakah kunci paling tepat dan dapat dibuktikan; penjelasan sesuai? |
| Distraktor/kejelasan | Distraktor masuk akal, tidak ambigu, satu jawaban tepat? |
| Kesesuaian kognitif | Operasi berpikir benar-benar cocok C1–C4 pilihan; bukan hanya label? |
| Indikator dan kisi-kisi | Indikator terukur dan mewakili materi/soal yang dirujuk? |
| Konsistensi | Nomor, tipe, level, indikator, soal dan kunci cocok? |
| Groundedness / no fabrication | Tidak ada definisi/nama/tahun/teori di luar sumber? |
| Bahasa dan kelayakan | Bahasa Indonesia natural, sesuai jenjang, tidak diskriminatif? |

Skor total deskriptif = jumlah skor non-N/A / (5 × jumlah kriteria non-N/A) × 100. Laporkan juga distribusi skor per kriteria; jangan menyebut skor rubrik ini probabilitas kebenaran. Nilai antar-penilai harus dihitung sebelum adjudikasi dan sesudahnya secara terpisah.

Template kosong: `output_accuracy.csv`. Tidak ada row hasil fiktif.
