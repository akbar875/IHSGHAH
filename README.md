# IHSGHAH — Saham Signal

Aplikasi web analisis saham intraday BEI untuk membantu keputusan manual dan paper trading. Sumber kebutuhan produk: [PRD Saham Signal](docs/PRD-Saham-Signal.md).

**Status: fondasi dan shell web research.** Shell Next.js tersedia lokal melalui [setup web](apps/web/README.md). Belum ada backend berjalan, feed pasar, model, sinyal, backtest, atau bukti profit. Fitur sistem dikerjakan melalui issue dan branch terpisah. Eksekusi broker otomatis berada di luar cakupan MVP.

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
services/api/          FastAPI modular monolith (rencana)
services/worker/       Ingest, analisis, replay, dan alert (rencana)
packages/contracts/   Kontrak API/event v1 dan fixture simulasi
infra/                Lingkungan lokal dan deployment (rencana)
research/             Protokol, eksperimen, dan evaluasi strategi
tests/                Skenario integrasi dan acceptance lintas service
docs/                 PRD, arsitektur, keputusan, dan backlog
.github/              Template issue/PR dan CI scaffolding
scripts/              Validasi scaffold dan penerbitan issue
```

## Urutan pengembangan

1. Fondasi: keputusan arsitektur, kontrak, bootstrap web/API/worker, lingkungan lokal, dan CI runtime.
2. Fase A: vendor dan hak data, referensi instrumen, penyimpanan point-in-time, adapter, dan kualitas feed (G0).
3. Fase B: fitur, replay/fill/biaya, kebijakan risiko, baseline, dan evaluasi holdout (G1).
4. Fase C: dashboard, chart/detail, watchlist, posisi manual, notifikasi, dan keamanan.
5. Fase D/E: integrasi paper live, observabilitas/recovery, observasi prospektif (G2), dan pilot terbatas (G3).

UI boleh dikembangkan memakai fixture yang diberi label simulasi setelah kontrak disepakati. Dependency implementasi bukan izin melompati gerbang validasi. Lihat [backlog dan dependency](docs/BACKLOG.md) serta [arsitektur](docs/ARCHITECTURE.md).

Fondasi issue #1 ditetapkan dalam [ADR-0001](docs/decisions/0001-stack-and-module-boundaries.md): baseline stack/versi/lisensi, batas modul, konfigurasi, isolasi research/paper/live, dan pilot satu akun. Status Accepted pada 12 November 2026; belum ada dependency aplikasi yang dipasang. Prasyarat Node.js 22 di atas berlaku untuk pemeriksaan scaffold; baseline runtime aplikasi dan CI bootstrap mengikuti ADR yang telah diterima.

## Alur issue → branch → PR

Kontrak SS-002 tersedia di [packages/contracts](packages/contracts/README.md): JSON Schema 2020-12, OpenAPI 3.1.1, REST dan stream snapshot/delta. Jalankan `npm ci --ignore-scripts --prefix packages/contracts` lalu `npm --prefix packages/contracts run check`; validasi lintas bahasa Python dan petunjuk unit/versioning tersedia di panduan kontrak. Belum ada endpoint aplikasi yang berjalan.

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
