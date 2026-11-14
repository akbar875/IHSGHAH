# IHSGHAH — Saham Signal

Aplikasi web analisis saham intraday BEI untuk membantu keputusan manual dan paper trading. Sumber kebutuhan produk: [PRD Saham Signal](docs/PRD-Saham-Signal.md).

**Status: fondasi, shell web research, API fixture dan worker.** Shell Next.js tersedia lokal melalui [setup web](apps/web/README.md), FastAPI melalui [setup API](services/api/README.md). API market tersedia sebagai simulasi research; belum ada feed pasar atau model produksi tervalidasi maupun bukti profit. Fitur sistem dikerjakan melalui issue dan branch terpisah. Eksekusi broker otomatis berada di luar cakupan MVP.

## Mulai dari sini

Prasyarat scaffolding: Git dan Node.js 22 atau lebih baru. Belum diperlukan instalasi dependency npm/Python, database, atau akun vendor.

```sh
git clone https://github.com/akbar875/IHSGHAH.git
cd IHSGHAH
node scripts/check-scaffold.mjs
node scripts/publish-issues.mjs
```

Perintah terakhir hanya menampilkan rencana issue (dry run). Untuk menerbitkan backlog ke GitHub, lihat [panduan backlog](docs/issues/README.md). Jalankan shell web dengan Node.js 24.22.3: `cd apps/web`, `npm ci --ignore-scripts`, lalu `npm run dev`. Lihat [panduan web](apps/web/README.md) untuk konfigurasi dan verifikasi. Bootstrap backend mengikuti issue service terkait.

## Struktur repo

```text
apps/web/              Shell research Next.js + TypeScript
services/api/          Bootstrap FastAPI modular, health/readiness dan konfigurasi
services/worker/       Panduan lifecycle worker; job bisnis menyusul
packages/contracts/   Kontrak API/event v1 dan fixture simulasi
infra/                Compose PostgreSQL/Redis lokal dengan isolasi mode
research/             Protokol, eksperimen, dan evaluasi strategi
tests/                Skenario integrasi dan acceptance lintas service
docs/                 PRD, arsitektur, keputusan, dan backlog
.github/              Template issue/PR dan CI scaffolding
scripts/              Validasi scaffold dan penerbitan issue
```

## Urutan pengembangan

SS-022 menyediakan [alert in-app dan deduplikasi persisten](docs/market-data/in-app-alerts.md):
inbox `/alerts`, prioritas risiko/data, hysteresis/cooldown, retry/reconnect tanpa
salinan serta batas pengiriman offline. Alert exit tidak membuat fill jual; replay
dan simulasi tidak masuk jalur live. Lingkungan tetap research dan G0–G3 belum lulus.

SS-021 menyediakan [pencatatan fill dan posisi manual](docs/market-data/manual-positions.md):
ledger PostgreSQL append-only per akun/mode, BUY/SELL parsial, basis biaya dan PnL
Decimal, rencana atas lot aktual, exit pending serta peringatan overnight. Chart
dan permintaan exit tidak membuat fill; catatan manual terpisah dari hasil simulasi.
Halaman `/positions` tetap lingkungan research tanpa broker/feed live. G0–G3 belum lulus.

SS-020 menyediakan [watchlist dan pengaturan pribadi](docs/market-data/watchlist-settings.md):
penyimpanan PostgreSQL per akun/mode, profil risiko dan biaya bertanggal berlabel
asumsi pengguna, validasi serta perhitungan ulang budget simulasi. Kontrak v1 lama
dipertahankan; lot layak eksekusi tetap nol sampai feed/model tervalidasi.

SS-019 menyediakan [detail saham, chart dan order book](docs/market-data/stock-detail.md):
candle/volume, entry/stop/TP/expiry, proyeksi putus-putus bertingkat cakupan,
horizon tetap saat interval berubah, snapshot book konsisten, pressure/cakupan
dan layout sentuh 360px. Data tetap simulasi; proyeksi/pressure belum tersedia
pada fixture API dan tidak diganti angka buatan. G0/G1 belum lulus.

SS-018 menyediakan [dashboard kandidat](docs/market-data/dashboard.md): input nominal,
pencarian/filter aktif, rencana entry/stop/target dan waktu WIB, validasi kontrak,
keadaan loading/kosong/gangguan, serta tampilan mobile 360px. Query nominal diisolasi
per permintaan; fixture tetap simulasi tanpa ranking atau probabilitas tervalidasi.

SS-017 menyediakan [API market dan stream resinkronisasi](docs/market-data/market-api.md)
untuk UI: kandidat, detail, depth, chart dan riwayat dengan kontrak v1 serta snapshot/delta.
Fixture research diaktifkan eksplisit, memakai sesi lokal dan label simulasi;
reconnect wajib snapshot baru. Model produksi/paper/live tetap tidak tersedia sebelum
integrasi artefak SS-016 dan bukti gerbang terkait. G0/G1 belum lulus.

SS-016 menyediakan [baseline, ranking nominal dan evaluasi holdout](docs/market-data/baseline-evaluation.md):
protokol/hash beku, purge/embargo, kalibrasi validation-only, replay per nominal,
metrik OOS, breakdown dan audit champion/challenger/ablation. [Laporan simulasi](research/reports/SS-016-simulation.md)
mencatat G1 **no-go / experiment**; probabilitas produk tetap null dan tidak ada
auto-promotion. Bukti vendor G0 serta risiko portofolio masih diperlukan.

SS-015 menyediakan [risk engine dan state rencana](docs/market-data/risk-engine.md):
sizing Decimal/integer dari kas, risiko dan likuiditas; state WATCH/READY/EXPIRED/
CANCELLED yang idempotent dan bisa direplay; validasi biaya/level/tenggat serta
trailing tanpa memperlebar risiko. READY tidak membuka posisi. Default risiko
adalah konfigurasi desain, bukan jaminan kerugian; G0/G1 tetap pending.

SS-014 menyediakan [replay dan simulator eksekusi konservatif](docs/market-data/replay-simulator.md):
biaya bertanggal, latensi, spread/slippage, antrean, partial/unfilled, stop-before-TP
dan gagal exit dengan laporan deterministik berlabel simulasi. Tidak ada alert live;
validasi vendor serta G0/G1 tetap pending.

SS-013 menyediakan [feature engine point-in-time](docs/market-data/feature-engine.md):
return, volatilitas, volume relatif jam WIB, spread/depth dan komposisi antrean,
serta pressure transaksi dengan unknown dan cakupan klasifikasi. Replay dan stream
memakai reducer yang sama, teruji simulasi; validasi vendor dan G0/G1 tetap pending.

SS-012 menyediakan [kualitas feed dan abstention](docs/market-data/feed-quality.md):
timeout heartbeat, status feed, pengaman entry sampai resnapshot dan warning
posisi tanpa exit dari data tidak sehat. Acceptance PRD 1/2/7 teruji simulasi;
SLA final dan bukti vendor belum tersedia sehingga **G0 tetap pending**.

Fondasi parsial SS-011 tersedia dalam [adapter feed](docs/market-data/feed-adapter.md):
normalisasi fixture, dedup/koreksi sesi dan recovery book teruji simulasi.
Belum ada feed vendor atau contract test sampel berizin; issue #11 dan G0 tetap
pending. Candle belum memiliki envelope persistensi dalam kontrak v1.

SS-010 menyediakan [penyimpanan point-in-time dan audit append-only](docs/PERSISTENCE.md):
migrasi PostgreSQL, snapshot berversi, deduplikasi transaksi, Decimal untuk
pembukuan, dan isolasi akun/mode. Kebijakan retensi berizin serta gerbang G0 tetap
memerlukan bukti terpisah; belum ada feed atau endpoint bisnis.

SS-009 menyediakan [lookup aturan instrumen dan kalender point-in-time](docs/market-data/instrument-rules.md)
untuk backend/replay: lot, fraksi, limit harian, sesi, suspensi dan aksi korporasi
berversi. Referensi kosong/tidak lengkap menahan entry; fixture hanya simulasi.
Belum ada master instrumen produksi atau feed berizin dan G0 tetap pending.

Audit SS-008 tersedia dalam [perbandingan vendor dan hak data](docs/market-data/vendor-audit.md),
[ADR-0002](docs/decisions/0002-market-data-procurement.md), dan
[protokol penawaran/sampel](docs/market-data/vendor-evaluation.md). Prioritas pencarian
adalah IQ Plus, dengan ICE sebagai pembanding dan RTI sebagai alternatif lokal.
Belum ada kontrak, sampel berizin, atau anggaran disetujui; **G0 tetap pending**.

1. Fondasi: keputusan arsitektur, kontrak, bootstrap web/API/worker, lingkungan lokal, dan CI runtime.
2. Fase A: vendor dan hak data, referensi instrumen, penyimpanan point-in-time, adapter, dan kualitas feed (G0).
3. Fase B: fitur, replay/fill/biaya, kebijakan risiko, baseline, dan evaluasi holdout (G1).
4. Fase C: dashboard, chart/detail, watchlist, posisi manual, notifikasi, dan keamanan.
5. Fase D/E: integrasi paper live, observabilitas/recovery, observasi prospektif (G2), dan pilot terbatas (G3).

UI boleh dikembangkan memakai fixture yang diberi label simulasi setelah kontrak disepakati. Dependency implementasi bukan izin melompati gerbang validasi. Lihat [backlog dan dependency](docs/BACKLOG.md) serta [arsitektur](docs/ARCHITECTURE.md).

Fondasi issue #1 ditetapkan dalam [ADR-0001](docs/decisions/0001-stack-and-module-boundaries.md): baseline stack/versi/lisensi, batas modul, konfigurasi, isolasi research/paper/live, dan pilot satu akun. Status Accepted pada 12 November 2026; belum ada dependency aplikasi yang dipasang. Prasyarat Node.js 22 di atas berlaku untuk pemeriksaan scaffold; baseline runtime aplikasi dan CI bootstrap mengikuti ADR yang telah diterima.

## Alur issue → branch → PR

[CI runtime SS-007](docs/RUNTIME-CI.md) menjalankan scaffold, kontrak, web,
backend API/worker dan integrasi PostgreSQL/Redis pada setiap push/PR. Job
`Runtime quality gate` memerlukan semua pemeriksaan lulus. Panduan mencantumkan
perintah lokal, smoke wheel terpasang, serta pengaturan required check untuk `main`.

Kontrak SS-002 tersedia di [packages/contracts](packages/contracts/README.md): JSON Schema 2020-12, OpenAPI 3.1.1, REST dan stream snapshot/delta. Jalankan `npm ci --ignore-scripts --prefix packages/contracts` lalu `npm --prefix packages/contracts run check`; validasi lintas bahasa Python dan petunjuk unit/versioning tersedia di panduan kontrak. Bootstrap SS-004 menyediakan `/health` dan `/ready`; endpoint bisnis belum diimplementasikan. Setup API memakai uv 0.13.7, Python 3.13.18 dan `uv sync --locked` pada `services/api`.

SS-006 menyediakan [PostgreSQL/Redis lokal](infra/README.md): dengan Docker Desktop
Linux/Engine lokal aktif, jalankan `node scripts/local-infra.mjs up research`
dari root. Healthcheck, volume persisten, port/password yang dapat dikonfigurasi,
instance terpisah per mode, shutdown dan reset lokal eksplisit tersedia dalam panduan.
Default API/worker cocok dengan Compose; `/ready` menolak dependency yang belum sehat.

```sh
git switch main
git pull --ff-only
git switch -c feat/123-market-data-adapter
# kerjakan scope satu issue, jalankan pemeriksaan yang relevan
git push -u origin feat/123-market-data-adapter
```

Gunakan nomor issue GitHub sebenarnya; ID `SS-xxx` adalah identitas backlog, bukan nomor GitHub. Isi PR dengan `Closes #123`, bukti validasi, dan keterbatasan. Detail ada di [CONTRIBUTING.md](CONTRIBUTING.md).

## Prinsip produk

- Modular monolith + worker; hindari microservices untuk pilot awal.
- Simpan waktu UTC, tampilkan Asia/Jakarta; gunakan `available_at` untuk riset point-in-time.
- Pisahkan research, paper, dan live. Data simulasi tidak boleh mengaktifkan alert live.
- Probabilitas yang belum tervalidasi bernilai null; jangan mengisi angka rekaan.
- READY tidak membuka posisi. Posisi nyata hanya berasal dari fill yang dicatat pengguna.
- Data kritis tidak sehat menahan entry; posisi yang gagal exit tetap terbuka.
- Tidak ada feed berita atau detail model internal pada UI pengguna.

## Lisensi

Lisensi kode belum ditentukan pemilik repo. Hak penggunaan data pasar mengikuti kontrak vendor yang dipilih; tidak otomatis mengikuti lisensi kode.
