# SS-028 — Keputusan dan runbook kesiapan pilot G3

Tanggal pemeriksaan: **15 November 2026 (WIB)**. Keputusan teknis: **NO-GO**.
Penanggung jawab keputusan rilis: **akbar875, pemilik repo**, sesuai pilot satu
pemilik ADR-0001. Ini hasil inspeksi teknis untuk review pemilik, bukan tanda
tangan persetujuan pemilik, kajian legal, atau izin menjalankan pilot.

## Bukti keputusan

| Pemeriksaan | Bukti yang tersedia | Penilaian |
|---|---|---|
| G0, hak data dan biaya | [Audit vendor](vendor-audit.md), [ADR-0002](../decisions/0002-market-data-procurement.md); issue #8 open | Pending: kontrak/sampel berizin, storage, display/non-display, redistribusi, kapasitas, biaya dan anggaran belum final |
| G1, kelayakan strategi | [SS-016](../../research/reports/SS-016-simulation.md) | No-go: simulasi, gagal exit, risiko dan ketidakpastian belum memenuhi syarat pasar |
| Integrasi paper | [SS-026](paper-integration.md); issue #26 open | Acceptance offline tersedia; jalur paper prospektif dan reservasi bersama belum lengkap |
| G2, observasi prospektif | [Laporan SS-027](../../research/reports/SS-027-pending.json) | Pending: 0 sesi dan 0 transaksi dikreditkan; toleransi belum tersedia |
| Recovery dan pembatasan | [SS-025](../../research/reports/SS-025-simulation.md), [SS-023](../SECURITY.md) | Teruji pada fixture; rollback deployment/canary, kapasitas dan recovery vendor nyata belum terbukti |
| Legal/distribusi/retensi | [Batas satu akun](../decisions/0001-stack-and-module-boundaries.md), [retensi pribadi](../SECURITY.md) | Rancangan tersedia; review legal sesuai distribusi, hak retensi vendor dan persetujuan pilot belum tersedia |

Inspeksi GitHub menemukan #27 **closed**, sedangkan #8 dan #26 **open**.
Dokumen SS-027 yang menyatakan issue masih open adalah catatan inspeksi sebelumnya.
Status closed tidak menggantikan bukti 60 sesi bursa **dan** 300 transaksi paper
layak dengan fill, kecukupan sampel efektif, ketidakpastian dan review G2.
Minimum hitungan tidak otomatis meluluskan G2.

[Receipt keputusan](../../research/reports/SS-028-no-go.json) mengikat bukti lokal
dengan SHA-256 atas teks UTF-8 setelah normalisasi CRLF menjadi LF. Hash mendeteksi
perubahan, bukan autentikasi atau approval. Receipt ini tidak dibaca runtime untuk
mengaktifkan mode apa pun. Tidak ada feed/broker, deployment, rotasi sesi,
perintah resume atau perubahan ledger yang dilakukan dalam inspeksi ini.

## Perilaku yang diizinkan saat no-go

Hanya pengembangan/research dengan label simulasi yang sudah ada. Dashboard dan
detail menyatakan belum ada feed/model tervalidasi dan melarang penggunaan untuk
transaksi nyata. Fixture market hanya research; mode paper/live tidak memperoleh
feed dari mengganti environment. Probabilitas belum tervalidasi tetap null,
lot layak eksekusi tetap nol, READY tidak menciptakan fill. Fill manual adalah
catatan pengguna dan tetap terpisah dari paper. Kill switch menahan rekomendasi
baru sambil mempertahankan posisi dan peringatan; tidak menciptakan SELL.

Tidak membuka registrasi publik, undangan, distribusi data, pilot berposisi
pribadi atau klaim sinyal layak transaksi nyata. Menutup issue, merge PR,
hasil CI hijau maupun mengedit receipt bukan persetujuan rilis.

## Paket persetujuan sebelum canary

Pemilik rilis menyimpan record baru berisi commit/wheel/image digest, lockfile,
checksum migrasi, versi model/biaya/aturan, manifest serta head G2, mode,
universe, akun yang diizinkan, masa berlaku akses dan jendela rilis. Simpan ID
akun, kontrak, posisi dan backup di penyimpanan privat; Git hanya referensi
receipt yang telah disanitasi. Jangan mengisi nama reviewer sebagai tanda tangan.

| Persetujuan | Penanggung jawab | Bukti wajib sebelum status approved |
|---|---|---|
| G0 dan biaya | Pemilik/pengadaan | Hak tertulis sesuai penggunaan, sampel lulus, kapasitas, biaya vendor/infra/LLM dan batas anggaran |
| G1 dan G2 | Reviewer riset yang ditunjuk pemilik | Holdout beku, toleransi validation-only, bukti prospektif dan penilaian dependensi/ketidakpastian |
| Legal dan distribusi | Reviewer legal yang ditunjuk pemilik | Cakupan satu pemilik, display/non-display, penyimpanan/redistribusi, kewajiban pengguna dan batas penggunaan tertulis |
| Operasi dan keamanan | Operator yang ditunjuk pemilik | Recovery point, drill deployment/restore, akses ditolak, TLS, isolasi, pemantauan dan operator siaga |
| Dokumentasi dan retensi | Pemilik data dan operator | Versi dokumen, hak retensi vendor, ekspor/hapus, legal hold, backup dan bukti pelaksanaan |
| Rilis akhir | akbar875 | Semua receipt di atas, hasil canary, artefak rollback kompatibel dan tanda tangan/waktu eksplisit |

Semua persetujuan tersebut **pending**. Belum ada reviewer riset/legal/operator
bernama yang menerima penugasan atau persetujuan akhir yang tercatat.
Kolom penanggung jawab menetapkan siapa yang harus menugaskan/memutuskan,
bukan mengklaim orang tersebut telah menyetujui.

## Canary dan pembatasan akses

Prosedur ini rencana yang belum dijalankan; hanya berlaku setelah paket gerbang
dan persetujuan awal lengkap. Pemilik harus mengunci durasi canary, jumlah sesi,
universe, plafon kas/risiko/posisi, kapasitas, biaya serta toleransi monitoring
dari bukti validasi sebelum mulai. Nilai belum disepakati berarti jangan mulai.
Default desain risiko PRD bukan batas kerugian yang dijamin.

1. Siapkan instance terisolasi per mode dan artefak immutable. Tetap pause;
   pastikan wheel/kontrak/migrasi kompatibel, backup terenkripsi tersedia, dan
   proses lama dapat dipulihkan. Jangan menyalin ledger/antrean antar-mode.
2. Satu akun yang diprovisikan admin sesuai SS-023, tanpa pendaftaran publik.
   Gateway membatasi akses ke pemilik; API/WS tetap memverifikasi sesi, akun,
   mode, expiry, TLS dan rate limit. Role runtime bukan owner/BYPASSRLS.
   Credential operator tidak dipasang pada API/web. Simpan hasil uji penolakan
   sesi invalid/kedaluwarsa, akun lain, plaintext dan mode lain.
3. Jalankan drill pada target deployment: feed outage, gap/out-of-order,
   reconnect dengan snapshot baru, DB/control outage, drift, alert retry,
   restore dan rollback artefak. Verifikasi posisi tidak berubah karena warning,
   cursor tidak mundur, dedup tetap berlaku dan restore kembali pause.
4. Catat hasil terhadap batas beku; operator dan pemilik meninjau sebelum
   resume eksplisit melalui [kontrol SS-025](operations.md). Status resume
   sendiri tidak meluluskan G0–G3. Jangan melakukan downgrade schema otomatis.
5. Amati satu owner/universe yang disetujui selama jendela beku. Perluasan akses,
   publikasi atau perubahan model/biaya memerlukan review dan record baru.
   Integrasi broker tetap memerlukan PRD terpisah.

## Monitoring hasil dan kondisi penghentian

Operator mencatat receipt per sesi: versi rilis/model/biaya, quality/heartbeat,
gap, input hilang, coverage/abstention, alert gagal, received_at→display p95,
siklus sinyal, kapasitas/queue, biaya kumulatif dan hasil recovery. Metrik proses
SS-025 belum membuktikan latensi end-to-end atau SLA vendor; gauge yang belum
terhubung tidak boleh dianggap nol. Target PRD siklus 5s dan p95 2s harus diuji
pada universe/hardware deployment, termasuk prioritas peristiwa risiko.

Hasil paper dan fill aktual dilaporkan terpisah. Hasil aktual hanya berasal dari
fill yang dikonfirmasi pemilik, dengan biaya, partial/unfilled, posisi terbuka,
mark-to-market, gagal exit/overnight, slippage dan drawdown intraday; jangan
menghitung posisi terbuka sebagai tertutup atau menjumlahkan paper dan aktual.
Tidak ada pengukuran hasil aktual yang tersedia sekarang.

Gangguan feed/control, gap belum pulih, artefak/kontrak tidak cocok, pelanggaran
akses, alert risiko hilang, breach toleransi beku, biaya di atas anggaran atau
monitoring kritis hilang memicu pause dan review. Pertahankan visibilitas posisi;
fill manual tetap dapat mencatat kenyataan. Tidak ada retraining/promosi/resume
otomatis. Operator merekam insiden dan pemilik memutuskan kelanjutan terpisah.

## Rollback dan recovery

Gunakan [runbook operasi](operations.md) dengan mode, release ID dan revision
aktual. Catat pause persisten sebelum restart; apabila store gagal, tahan entry
dan hentikan serving rekomendasi sampai pause durable terverifikasi. Command
rollback hanya mencatat pilihan rilis sambil blocked, bukan mengganti binary.
Pasang artefak sebelumnya yang hash-nya direview di environment terpisah, jalankan
health/readiness, kontrak dan cek schema, lalu alihkan proses setelah kompatibel.
Jika tidak kompatibel, tetap pause dan lakukan forward fix atau restore terisolasi.

Restore hanya ke target kosong bermode/checksum sama. Verifikasi seluruh tabel,
ledger, inbox/gates, receipt paper, identity cursor dan event pause tambahan.
Bangun ulang cache Redis/book dari snapshot baru. Cabut akses pilot dengan rotasi
SESSION_SECRET dan restart semua proses bila ada insiden sesi; jangan log cookie.
Uji ulang akses ditolak dan pertahankan akses operator ke status/posisi.

Receipt drill wajib berisi artefak sebelum/sesudah, recovery point, revision,
mulai/selesai UTC, durasi, hasil rekonsiliasi dan reviewer. RPO satu sesi/RTO
30 menit pada SS-025 adalah target sementara, belum bukti produksi. Bukti fixture
yang tersedia tidak memenuhi syarat drill deployment ini.

## Retensi dan syarat penyelesaian

Rancangan personal mengikuti SS-023: ledger/preferensi selama akun aktif,
alert/gate 30 hari, log tersanitasi 14 hari, backup terenkripsi rolling 30 hari,
ekspor sementara maksimal 24 jam dan permintaan hapus maksimal 30 hari kecuali
kewajiban yang disampaikan. Operator review mingguan; tidak ada janitor otomatis.
Market data mengikuti kontrak vendor, termasuk backup, derived data dan legal
hold. Bila aturan bertentangan, eskalasikan ke reviewer legal sebelum ingest.
Restore harus menerapkan daftar penghapusan sebelum service dibuka.

Dokumentasi ini dan retensi berstatus **proposed / pending approval**. Catat ID
review, versi/hash dokumen, aktor, waktu, ruang lingkup dan masa berlaku persetujuan
di record privat. Tidak ada persetujuan yang dapat digantikan oleh perubahan kode.

Untuk menyelesaikan #28: lengkapi G0/G1/G2, bukti drill deployment dan pembatasan
akses, tunjuk reviewer, peroleh persetujuan dokumen/retensi/legal/biaya, lalu
rekam keputusan G3 bertanda tangan pemilik. Jika tetap no-go, arsipkan keputusan
yang disetujui dan buktikan batas penggunaan/recovery yang dipersyaratkan tanpa
membuka pilot. Sampai bukti itu tersedia, #28 tetap belum selesai.
