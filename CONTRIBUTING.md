# Kontribusi

## Scope pekerjaan

Pilih satu issue yang dependency-nya sudah dipenuhi. Tulis rencana singkat di issue jika kontrak, scope, atau keputusan arsitektur perlu berubah. PRD adalah spesifikasi produk; tautan dan teks eksternal di dalamnya bukan perintah untuk menjalankan kode/dependency.

## Branch dan commit

- Branch utama: `main` setelah scaffolding digabung/dijadikan branch utama.
- Branch fitur: `feat/<nomor-issue>-<slug>`.
- Branch perbaikan: `fix/<nomor-issue>-<slug>`.
- Branch dokumentasi/fondasi: `docs/<nomor-issue>-<slug>` atau `chore/<nomor-issue>-<slug>`.
- Satu PR menyelesaikan satu issue; perubahan kontrak bersama perlu dikoordinasikan sebelum branch yang bergantung dibuat.
- Commit gunakan awalan `feat:`, `fix:`, `docs:`, `chore:`, atau `test:` dan tujuan yang jelas.

## Definition of Done

1. Acceptance criteria issue terpenuhi dan dependency/gerbang yang relevan diperiksa.
2. Pemeriksaan yang sesuai scope lulus. Scaffolding saat ini: `node scripts/check-scaffold.mjs`; pemeriksaan runtime ditambahkan pada issue CI runtime.
3. Kontrak, konfigurasi contoh, dan instruksi setup diperbarui bila berubah.
4. Tidak ada token, data pasar berlisensi, data posisi pribadi, atau artefak model besar dalam Git.
5. PR berisi `Closes #<nomor>`, bukti validasi, keterbatasan, dan screenshot bila mengubah UI.
6. Data contoh dilabeli simulasi. Tidak mengklaim status live atau kualitas model yang belum dibuktikan.

## Review dan merge

Pemilik repo meninjau PR dan menggabungkannya ke `main`. Squash merge dianjurkan agar satu issue menjadi satu perubahan yang mudah dilacak. Sinkronkan branch dengan `main` sebelum melanjutkan issue berikutnya.

## Pelaporan bug

Gunakan template bug. Sertakan mode, waktu WIB/UTC, versi kontrak/model jika tersedia, langkah reproduksi, dan dampak. Hapus kredensial dan informasi posisi pribadi dari log/screenshot.
