# IHSGHAH — Saham Signal

Aplikasi web analisis saham intraday BEI untuk membantu keputusan manual dan paper trading. Sumber kebutuhan produk: [PRD Saham Signal](docs/PRD-Saham-Signal.md).

**Status: scaffolding dan perencanaan.** Belum ada aplikasi berjalan, feed pasar, model, sinyal, backtest, atau bukti profit. Fitur sistem dikerjakan melalui issue dan branch terpisah. Eksekusi broker otomatis berada di luar cakupan MVP.

## Mulai dari sini

Prasyarat scaffolding: Git dan Node.js 22 atau lebih baru. Belum diperlukan instalasi dependency npm/Python, database, atau akun vendor.

```sh
git clone https://github.com/akbar875/IHSGHAH.git
cd IHSGHAH
node scripts/check-scaffold.mjs
node scripts/publish-issues.mjs
```

Perintah terakhir hanya menampilkan rencana issue (dry run). Untuk menerbitkan backlog ke GitHub, lihat [panduan backlog](docs/issues/README.md). Setup aplikasi, dependency yang dipin, dan perintah development akan ditambahkan melalui issue bootstrap masing-masing service.

## Struktur repo

```text
apps/web/              Next.js + TypeScript (rencana)
services/api/          FastAPI modular monolith (rencana)
services/worker/       Ingest, analisis, replay, dan alert (rencana)
packages/contracts/   Kontrak API/event lintas service (rencana)
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

Fondasi issue #1 disiapkan dalam [ADR-0001](docs/decisions/0001-stack-and-module-boundaries.md): baseline stack/versi/lisensi, batas modul, konfigurasi, isolasi research/paper/live, dan usulan pilot satu akun. Status masih Proposed sampai pemilik repo menerima; belum ada dependency aplikasi yang dipasang. Prasyarat Node.js 22 di atas berlaku untuk pemeriksaan scaffold; baseline runtime aplikasi dan CI bootstrap mengikuti ADR setelah diterima.

## Alur issue → branch → PR

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
