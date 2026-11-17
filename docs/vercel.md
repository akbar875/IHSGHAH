# Deploy research dengan Vercel Services

Import repository dengan Root Directory `./` dan preset **Services**.
Gunakan Node.js Version **24.x** di Settings → Build and Deployment.
`package.json` root dan web sama-sama mengunci major 24 untuk pemilihan
runtime awal serta build service. Setelah mengubah versi, redeploy tanpa
build cache. Peringatan npm `Unknown env config "cache-dir"` berasal dari
environment build dan tidak dengan sendirinya menunjukkan kegagalan build.
Konfigurasi root `vercel.json` membangun `web` (Next.js, `apps/web`) dan
`api` (FastAPI, `services/api`, entrypoint `app:app`) secara terpisah.
API memilih Python `3.13` melalui `services/api/.python-version`, tanpa pin
patch. Ini memungkinkan `uv sync --frozen` memakai interpreter Vercel yang
tersedia; pin `3.13.18` dapat gagal pada katalog interpreter uv milik Vercel.
Rentang Python pada `pyproject.toml` dan `uv.lock` tetap membatasi versi ke 3.13.

Routing publik: `/api/*` ke API, semua path lain ke web. Prefix `/api`
tetap diterima backend; route yang tersedia antara lain `/api/v1/candidates`
dan `/api/ops/paper`. `/health`, `/ready`, dan dokumentasi OpenAPI backend
tidak diekspos oleh routing ini.

Tidak ada binding antar-service: semua fetch API saat ini dipanggil browser
dari client components. Browser memakai `/api/v1` pada origin yang sama,
bukan URL internal. Jika menambahkan fetch server-side di masa depan,
deklarasikan binding pada service pemanggil dan baca URL binding saat runtime.
Jangan gunakan binding pada build, middleware, atau `NEXT_PUBLIC_*`.

## Environment dan data

- Hapus override `NEXT_PUBLIC_API_BASE_URL` yang masih menuju localhost dari
  Vercel; default kode sudah `/api/v1`. Variabel ini dibekukan saat build.
- Atur `APP_MODE=research`, `DATABASE_URL`, `REDIS_URL`, dan
  `REDIS_NAMESPACE=saham-signal:research:` di environment Vercel.
  PostgreSQL dan Redis harus dapat dijangkau dari deployment; localhost
  dan hostname Docker lokal tidak tersedia di Vercel.
- Validasi backend mewajibkan nama database `saham_signal_research` dan DSN
  tanpa query override. Gunakan koneksi TLS melalui konfigurasi driver/provider
  yang sesuai (misalnya `PGSSLMODE=verify-full` beserta CA yang diperlukan);
  Redis TLS memakai `rediss://`. Jangan menyalin URL provider dengan query
  `sslmode` tanpa menyesuaikannya dengan validasi konfigurasi proyek.
- Atur `SESSION_SECRET` acak minimal 32 karakter, `PILOT_ACCOUNT_ID`,
  `CORS_ORIGINS=["https://<domain-deployment>"]`, dan
  `DEPLOYMENT_TLS_REQUIRED=true` untuk deployment HTTPS. Gunakan environment
  dan database terpisah untuk Preview dan Production.
- Jalankan migrasi sesuai README API sebelum memakai penyimpanan persisten.
  Sesi untuk data pribadi dan kontrol admin tetap diprovisikan sesuai `docs/SECURITY.md`.
  Daftar/detail saham harian publik tidak memerlukan sesi. Snapshot atribusi asli
  dibundel dalam `services/api/src/saham_signal/resources/idx-daily.json`, sehingga
  Vercel tidak memerlukan file `.work` lokal. Jika `EOD_SNAPSHOT_PATH` tidak menunjuk
  file yang tersedia saat startup, API memakai snapshot bawaan. Pembaruan snapshot
  memerlukan import eksplisit dan redeploy; tanggal dan status stale tetap terlihat.
- Fixture tetap nonaktif secara default. Untuk demo simulasi terotorisasi,
  ikuti `docs/market-data/market-api.md`; token fixture tidak boleh menjadi
  variabel publik. Konfigurasi ini tidak mengaktifkan feed atau trading live.

Worker kontinu tidak dideklarasikan sebagai request service. Deployment dua
service ini tidak menjalankan collector, scheduler, atau loop worker.
Telemetry dan rate limit dalam memori bersifat per-instance, bukan global.

## Verifikasi sebelum deploy

Dari root repository, dengan CLI Vercel yang mendukung Services:

```sh
vercel dev --local
```

Sediakan environment lokal backend terlebih dahulu. Buka URL yang dicetak CLI;
pastikan halaman `/` tampil dan `/api/v1/candidates` mencapai backend (tanpa
sesi harus ditolak dengan 401 saat fixture aktif, atau 503 saat fixture nonaktif,
bukan menampilkan HTML Next.js). Verifikasi sesi sah,
penyimpanan PostgreSQL, Redis dan route admin dengan akun uji terisolasi.
Jangan menaruh secret dalam `vercel.json` atau source control.

Catatan verifikasi lokal: CLI 65.16.0 mengenali kedua service, tetapi
`vercel dev --local` pada lingkungan Windows ini berhenti dengan
`DEV_SERVICE_START_FAILED: No dev server available for service "api"`.
Tes routing gabungan Vercel belum lulus; lakukan ulang pada lingkungan
deployment sebelum menganggap deployment siap digunakan. Entrypoint ASGI
dan routing API telah diperiksa terpisah.

Referensi: https://vercel.com/docs/services dan
https://vercel.com/docs/frameworks/backend/fastapi.
