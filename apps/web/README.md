# Web — dashboard dan detail research SS-018/019

SS-020 menambahkan `/settings` untuk watchlist dan profil nominal/risiko/biaya
bertanggal. Data disimpan per akun/mode melalui API dan PostgreSQL; form biaya
awal kosong, selalu berlabel asumsi pengguna. Jalankan migrasi API sebelum
menggunakan halaman ini. Lihat [panduan pengaturan](../../docs/market-data/watchlist-settings.md).

Dashboard Next.js App Router + TypeScript untuk research, selalu berlabel
**Research / Simulasi**. Menampilkan kandidat simulasi dari API #17, input nominal,
pencarian/filter aktif, rencana entry/stop/target/horizon dan kondisi data.
Belum ada feed pasar, model tervalidasi atau autentikasi pilot; G0/G1/G2/G3 belum lulus.

Klik ticker untuk membuka detail saham (`/stocks/TEST`), rencana, chart candle/volume,
interval 1m/5m/15m, proyeksi bila tersedia/tervalidasi, book dan pressure. Horizon
tidak berubah saat mengganti interval. Book diganti sebagai snapshot penuh, maksimal
lima tingkat tiap sisi dan berlabel saat terbatas. Library Lightweight Charts 5.2.0
berlisensi Apache-2.0 dengan atribusi TradingView pada halaman.
Lihat [panduan detail dan batas simulasi](../../docs/market-data/stock-detail.md).

## Setup

Gunakan Node.js **24.22.3** sesuai `.nvmrc`/CI. Node 22.13+ kompatibel untuk pemeriksaan
lokal. Dari root:

```sh
cd apps/web
npm ci --ignore-scripts
npm run dev
```

Buka http://127.0.0.1:3000. API yang tidak tersedia menampilkan keadaan kosong aman
dan tombol Coba lagi. Untuk kandidat TEST, ikuti [setup fixture dan sesi API](../../docs/market-data/market-api.md).
Tidak ada token yang dibundel atau sesi yang dibuat otomatis. Gunakan hostname sama
untuk web/API agar cookie sesi tersedia. `dev`/`start` bind loopback.

## Konfigurasi publik

Salin `.env.example` ke `.env.local` di apps/web bila perlu.

| Nama | Default | Pemakaian |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | Base URL fetch kandidat; credentials include, tanpa cache |

Jika web dibuka pada 127.0.0.1, gunakan `http://127.0.0.1:8000/api/v1` untuk API.
URL harus HTTP(S), tanpa credential, query atau fragment. Jangan masukkan secret pada
`NEXT_PUBLIC_*`; konfigurasi publik dibekukan saat build. Mode UI tetap research dan
hanya menerima respons research/simulation berkontrak 1.0.0. Pengaturan APP_MODE
backend tidak mengaktifkan paper/live pada UI.

## Pemeriksaan

```sh
npm run contracts       # Regenerasi tipe/schema publik dari kontrak canonical
npm run check           # Generated drift, ESLint, TypeScript, production build
npx playwright install chromium
npm test                # Chromium terhadap build produksi, port 3100
npm start               # Smoke manual setelah build
```

Tidak memerlukan backend atau data vendor untuk test browser: respons HTTP dimock
dengan fixture simulasi publik. [Runtime CI](../../docs/RUNTIME-CI.md) menjalankan
pemeriksaan web dan browser. Screenshot test lokal tersimpan di `.work` root repo.
Periksa desktop dan 360px: angka inti terbaca, tidak ada horizontal overflow, label
simulasi terlihat, navigasi keyboard dan label kontrol tersedia.

[Penjelasan dashboard dan batas implementasi](../../docs/market-data/dashboard.md)
mencakup polling, expiry, nominal dan kondisi data. Ajv2020/ajv-formats memvalidasi
schema SS-002; json-schema-to-typescript menghasilkan tipe. Tidak ada kontrak domain
yang ditulis ulang manual. Perubahan nominal hanya memilih skenario fixture, belum
membuktikan ranking/sizing produksi.

## Dependency

Inbox `/alerts` dijelaskan pada [panduan SS-022](../../docs/market-data/in-app-alerts.md).
Daftar simulasi dipoll setiap 5 detik dengan deduplikasi, prioritas risiko/data,
pesan exit tanpa fill jual, dan keadaan offline/reconnect. Push belum tersedia.

Versi langsung exact dan transitif terkunci di package-lock.json. Next.js 16.4.6,
React/React DOM 19.3.1, TypeScript 6.0.3 mengikuti ADR-0001. ESLint tetap 9.39.5 karena
peer eslint-plugin-react belum mendukung ESLint 10. Override minimatch 11.0.1 pada
typescript-estree dipertahankan. Ajv 8.20.0, ajv-formats 3.0.1,
json-schema-to-typescript 15.0.4 dan Playwright 1.58.2 berlisensi MIT/MIT/MIT/Apache-2.0.
Hak penggunaan data pasar serta lisensi kode repo tetap keputusan terpisah.
