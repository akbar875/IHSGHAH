# SS-025 — Operasi, pemulihan dan kill switch

Inspeksi issue #25, 14 November 2026: SS-007 menyediakan CI runtime, SS-011/012
menyediakan reducer book dan recovery fail-closed, SS-022 inbox idempotent, SS-023
sesi admin serta isolasi mode. Belum tersedia kontrol lintas proses, receipt
restore, metrik operasi atau runbook rollback. Dependency #7/#11/#12/#22/#23
sudah closed; **pengadaan vendor #8/G0 masih pending** karena feed/sampel berizin
belum tersedia. Checklist contract-test vendor #11 belum terbukti walaupun issue
tersebut closed. Implementasi ini menguji operasi simulasi;
tidak membuka paper/live, mempromosikan model atau mengklaim kelulusan G0–G3.

## Kontrol dan integrasi

Migrasi `006_operations.sql` menambahkan `operation_events` append-only per mode.
Default belum diinisialisasi adalah blocked. Operator mencatat pause, drift,
rollback atau resume dengan expected revision, aktor, immutable release ID dan
referensi insiden/review. Advisory lock dan compare-and-swap mencegah operator
lama menimpa keputusan baru. API hanya memerlukan SELECT; akun operator terpisah
mendapat SELECT/INSERT. Jangan berikan UPDATE/DELETE/TRUNCATE atau credential
operator ke proses API/worker. SQL RLS memisahkan mode, dan repository memeriksa
nama database; ini tetap satu pilot owner sesuai SS-023.

`RiskInputs.operations` adalah snapshot kontrol yang ikut audit/hash replay.
Default menahan READY; runtime harus mengambil kontrol **terbaru** sebelum setiap
evaluasi/publikasi, bukan menyimpan snapshot resume sebagai konfigurasi permanen.
Simpan revision kontrol bersama command dalam transaksi reservasi. Orkestrasi
reservasi/paper live masih scope SS-026. Reducer risiko tidak mengubah posisi/fill.
Fixture SS-016 mengizinkan kontrol hanya secara eksplisit berlabel simulasi.

HTTP kandidat/detail dan WebSocket memakai kontrol yang sama, dibaca ulang tanpa
cache lintas permintaan. READY ditahan menjadi WATCH/DATA_UNHEALTHY pada proyeksi
aktif; riwayat audit tetap utuh. Inbox menonaktifkan event ENTRY_READY saat pause,
sekaligus mereset hysteresis. Alert risiko dan status posisi tetap tersedia.
Recording fill manual, termasuk BUY historis yang benar-benar terjadi, tetap
diizinkan: kill switch tidak boleh menghapus kenyataan ledger atau membuat SELL.
Kegagalan membaca kontrol menahan entry, tanpa membuat endpoint posisi bergantung
pada tabel kontrol. Browser fixture polling saat ini 15 detik; penghentian backend
tidak menjamin pembaruan tampilan real-time sampai integrasi stream SS-026.

`Operations.observe_drift(evidence)` adalah hook detektor: increment metrik drift
dan append pause drift. Tidak memilih champion, melatih model atau auto-resume.
Jika penyimpanan gagal, proses menahan entry dengan latch lokal dan meneruskan
error ke operator. Jangan restart/resume proses itu sebelum pause persisten
berhasil dicatat. Ambang detektor harus berasal dari protokol evaluasi beku dan
artefak tervalidasi SS-016; belum ada model produksi yang layak dimonitor.

## Metrik operator

`GET /api/ops/status` membutuhkan sesi admin **bertanda tangan** SS-023; fixture
token lama ditolak. Respons private/no-store memuat mode, waktu, kontrol, latch,
dan statistik proses. Tidak ada mutation endpoint publik. CLI `status` hanya
membaca kontrol persisten; metrik proses dibaca lewat endpoint proses terkait.

| Nama | Makna / sumber | Tindakan awal pilot |
|---|---|---|
| `internal_p95_seconds` | HTTP internal, rolling nearest-rank 2048 sampel terakhir | >2s: pause, periksa DB/queue; ini bukan received_at-to-display |
| `http_requests`, `http_failed` | Semua HTTP, termasuk penolakan; failed = exception/5xx | Telusuri request ID tersanitasi; jangan log cookie/body |
| `feed_gap` | Jumlah assessment yang melihat SEQUENCE_GAP | Pause dan snapshot baru; bukan jumlah unik outage |
| `feed_lag_seconds` | Umur heartbeat terakhir saat assessment | >10s: SS-012 degraded; 30s stale, 60s disconnected |
| `missing_input` | Assessment bermasalah atau kontrol gagal dibaca | Abstention sampai input lengkap dan recovery tervalidasi |
| `alert_failed` | Kegagalan refresh inbox PostgreSQL | Retry key yang sama, periksa DB; jangan membuat event ID baru |
| `drift` | Panggilan hook drift dalam proses ini | Review/abstention, evaluasi terpisah; tanpa auto-promotion |
| `active_candidates` | Jumlah kandidat pada pembacaan terbaru | Bandingkan universe dan coverage |
| `queue_depth`, `capacity_fraction` | Gauge hook worker/collector | Pilot: queue >100 atau kapasitas >0,8 memerlukan investigasi |
| `cost_idr` | Gauge estimasi biaya kumulatif oleh collector operator | Bandingkan anggaran vendor/infra yang disetujui |

Feed ingestor menerima optional `operations` untuk menerbitkan assessment ke
telemetry; poll SS-012 tetap wajib walaupun tidak ada pesan. Gauge kapasitas,
queue dan biaya diisi `telemetry.gauge(name, value)` oleh collector yang memiliki
bukti; nilainya **null** sampai ada pengukuran. Tidak ada harga vendor, kapasitas,
biaya nol atau drift sehat yang direka. Nilai proses bukan agregat cluster,
reset saat restart dan gauge menggambarkan pengukuran terakhir, bukan freshness
guarantee; collector harus dipoll operator. Gunakan satu writer per ingestor dan
ambil metrik setiap proses API/worker yang berjalan. API tidak mengirim data
pasar/private payload ke layanan observabilitas eksternal.

## Runbook insiden dan rollback

Perintah dijalankan dari environment backend, dengan APP_MODE, DATABASE_URL dan
credential **operator** yang benar. Jangan taruh DSN/secret di argv/log/issue.

```sh
python -m saham_signal.operations status
python -m saham_signal.operations control pause --expected-revision 0 --release <sha-aktif> --evidence <incident-id> --actor <operator>
python -m saham_signal.operations control drift --expected-revision 1 --release <sha-aktif> --evidence <evaluation-receipt-hash> --actor <operator>
python -m saham_signal.operations control rollback --expected-revision 2 --release <sha-sebelumnya-disetujui> --evidence <incident-id> --actor <operator>
```

1. Baca revision aktual; pause sebelum tindakan pemulihan. Jika database mati,
   entry otomatis ditahan; pertahankan ledger/status gangguan, jangan isi harga
   pengganti. Persist pause segera saat database pulih.
2. Feed gap/outage: hentikan entry, panggil reconnect, tolak delta/cursor lama,
   tunggu heartbeat sehat dan snapshot baru dari connection aktif. Jangan
   gabungkan book sebelum/sesudah gangguan. Poll quiet symbols tetap berjalan.
3. Alert gagal: retry source key/channel yang sama. Inbox, gates dan ledger
   harus dipulihkan pada recovery point yang sama; jangan kosongkan gates untuk
   mempercepat pengiriman. Risk warning tidak dianggap fill exit.
4. Rollback: command di atas mencatat **pilihan rilis dan tetap blocked**. Operator
   menghentikan proses serving, mengambil wheel/commit sebelumnya yang hash-nya
   sudah disetujui, memasangnya ke environment terpisah dari lockfile rilis itu,
   lalu menjalankan smoke health/readiness dan pemeriksaan kontrak/migrasi.
   Alihkan proses ke artefak itu hanya jika kompatibel dengan schema saat ini.
   CLI tidak mengeksekusi shell dari field release/evidence dan tidak melakukan
   downgrade schema. Jika rilis lama tidak kompatibel: tetap pause, lakukan
   forward fix atau restore ke instance terpisah; jangan hapus ledger/migrasi.
5. Cocokkan posisi/fill, checksum migrasi, inbox/gates dan origin/mode. Catat
   durasi gangguan, control revision, versi artefak, hasil recovery dan review.
6. Resume hanya setelah evaluasi, hak data, gerbang dan canary disetujui. Gunakan
   revision terbaru dan bukti review; `resume` tidak meluluskan gerbang lainnya.
   Kegagalan canary memicu pause/rollback kembali, bukan auto-promotion.

```sh
python -m saham_signal.operations control resume --expected-revision 3 --release <sha-direview> --evidence <release-approval-id> --actor <operator>
```

## Backup dan restore

Backup logical v1 untuk ukuran pilot mencakup sembilan tabel aplikasi: journal,
retention_policy, preferences, manual ledger, inbox, hysteresis gates, internal
news, kontrol operasi dan receipt paper SS-026. Satu transaksi repeatable-read read-only mengambil
snapshot konsisten; owner/BYPASSRLS wajib agar tidak diam-diam kehilangan akun.
Manifest mencatat mode, migration checksums, waktu UTC dan SHA-256 konten. JSON
mempertahankan string Decimal dan integer cursor. Ini bukan backup role, secret,
cluster PostgreSQL, Redis atau recovery WAL. Redis hanya cache: bangun ulang dengan
namespace mode dan resnapshot; jangan restore cursor/book cache lama.

File mengandung data pribadi/berlisensi. Simpan di direktori terenkripsi di luar
Git dengan ACL operator, sesuai retensi/legal hold SS-010/023. POSIX mode 0600
disetel, Windows mewarisi ACL direktori; batasi ACL sebelum membuat file. Gunakan
nama recovery point baru; file yang sudah ada ditolak. SHA mendeteksi korupsi,
bukan autentikasi: hanya restore artefak tepercaya yang receipt-nya terpisah.

```sh
python -m saham_signal.operations backup <encrypted-directory>/recovery-point.json
# Siapkan instance/schema target kosong dengan database saham_signal_<mode>.
# Muat konfigurasi target dan jalankan python -m saham_signal.migrate di sana.
# Atur RESTORE_DATABASE_URL pada environment operator ke target, bukan sumber.
python -m saham_signal.operations restore <encrypted-directory>/recovery-point.json --confirm-empty-target empty:saham_signal_research
```

Restore hanya menerima mode dan checksums migrasi identik, sembilan tabel kosong,
serta konfirmasi nama database. Access-exclusive locks mencegah race emptiness;
insert seluruh baris dalam satu transaksi, pertahankan PK/idempotency key dan
atur ulang identity cursor di atas high-water mark. Tidak ada DROP/TRUNCATE,
perubahan sumber atau overwrite database berisi. Restore menambahkan **pause**
baru walaupun backup berstatus resume. Migrasi harus disiapkan terpisah; kegagalan
restore tidak menghapus schema kosong tersebut. Jangan aktifkan target sebelum
verifikasi posisi/inbox, resnapshot feed, smoke artefak dan review operator.

Target desain sementara: backup sebelum perubahan rilis dan sesudah sesi paper,
retensi mengikuti persetujuan (bukan TTL otomatis); RPO satu sesi dan RTO 30 menit
adalah sasaran operator yang **belum dibuktikan** pada ukuran data/vendor nyata.
Untuk histori besar gunakan backup PostgreSQL/WAL dengan prosedur hak data
terpisah; logical v1 ini memuat snapshot di memori.

## Bukti dan reproduksi

[Receipt SS-025](../../research/reports/SS-025-simulation.md) mendefinisikan beban,
hasil pengukuran dan batas pengujian. Backend CI menjalankan PostgreSQL nyata,
uji race/restart, restore, timeout, reconnect, dedup, drift serta stress komponen.
Browser CI mengukur 100 kartu/20 snapshot, termasuk dua animation frame setelah
DOM terbarui. Artefak JSON CI disimpan 14 hari tanpa backup private/DSN.

```sh
# PERSISTENCE_TEST_DSN harus database research development disposable.
# OPERATIONS_REPORT dan OPERATIONS_RESTORE_REPORT opsional: file receipt nonsensitif.
python -m pytest tests/test_operations.py tests/test_feed_quality.py tests/test_alerts.py
# Dari apps/web sesudah npm run build:
npm test -- tests/operations-load.spec.ts
```

Hash SS-016 dan SS-024 diperbarui karena snapshot kontrol menjadi input audit;
metrik eksekusi/ablation sebelumnya tetap sama. Tidak ada evaluasi pasar baru
atau pembukaan ulang holdout nyata. Target 5s siklus dan p95 2s diuji terpisah
pada komponen dan browser simulasi; integrasi feed→server→stream→display,
prioritas peristiwa kritis, deployment/canary dan SLA vendor nyata wajib
dibuktikan di SS-026/G0/G2 sebelum paper/pilot dipakai.
