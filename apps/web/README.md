# Web — SS-003

Shell Next.js App Router + TypeScript untuk lokal, berlabel **Research / Simulasi**. Belum ada screener, feed, harga, sinyal, autentikasi, atau panggilan API. Tidak membutuhkan backend, database, akun vendor, atau file environment. Dashboard/detail mengikuti SS-018/019; belum ada kelulusan G0/G1/G2/G3.

## Setup dari fresh clone

Gunakan Node.js **24.22.3** (baseline ADR, `.nvmrc`, dan CI) serta npm bawaan Node. Node 22.13+ juga kompatibel untuk pemeriksaan lokal; rentang engine bukan pengganti baseline deployment. Dari root repo:

```sh
cd apps/web
npm ci --ignore-scripts
npm run dev
```

Buka http://127.0.0.1:3000. Hentikan dengan Ctrl+C. `dev` dan `start` bind loopback; shell belum boleh dipublikasikan sebagai pilot berisi data pribadi. Font sistem/CSS lokal tidak membutuhkan unduhan font saat build.

```sh
npm run lint
npm run typecheck
npm run build
npm start
```

`npm run check` menjalankan lint, typecheck, lalu build. Typecheck memakai `next typegen` sehingga dapat berjalan sebelum build pertama. [Web checks](../../.github/workflows/web.yml) menguji fresh install dan ketiganya pada Node 24.22.3. Smoke test produksi: jalankan `npm start` setelah build dan periksa `/`.

## Konfigurasi publik

Opsional: salin `.env.example` menjadi `.env.local` di **apps/web**, bukan root repo.

| Nama | Default | Pemakaian |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | Base URL publik integrasi API berikutnya; belum melakukan fetch/health check |

Konfigurasi terpusat di [config.ts](src/lib/config.ts). URL harus HTTP(S), tanpa username/password, query, atau fragment. URL invalid menggagalkan build/render. Jangan masukkan token atau DSN pada `NEXT_PUBLIC_*`; nilainya dapat masuk bundle browser. Konfigurasi publik dibekukan saat build: rebuild setelah mengubah `.env.local`. URL konfigurasi tidak membuktikan API tersedia.

Mode shell tetap `research`, asal data `simulation`, zona tampilan `Asia/Jakarta`; belum ada timestamp pasar. `APP_MODE` backend tidak mengaktifkan paper/live pada shell. Integrasi berikutnya harus mengambil mode otoritatif dari server dan memvalidasi metadata kontrak.

## Kontrak dan dependency

[Kontrak v1](../../packages/contracts/README.md) tetap sumber tunggal. Shell belum menerima payload sehingga belum membutuhkan SDK, generator tipe, validator runtime, atau salinan interface domain. Integrasi SS-017/018 wajib memilih generator tipe dari schema yang sama serta Ajv2020 untuk validasi runtime; jangan menulis ulang kontrak manual.

Versi langsung exact dan dependency transitif terkunci dalam `package-lock.json`. Next.js 16.4.6, React/React DOM 19.3.1, dan TypeScript 6.0.3 mengikuti ADR-0001. ESLint 9.39.5 dipilih untuk kompatibilitas peer plugin Next (ESLint 10 memicu konflik peer). Tooling: eslint-config-next 16.4.6, @types/node 24.19.2, @types/react dan @types/react-dom 19.3.0. Next/React/ESLint/paket tipe berlisensi MIT, TypeScript Apache-2.0; lisensi transitif tercatat dalam lockfile. Hak data pasar dan lisensi kode repo tetap keputusan terpisah.

Rujukan resmi: [instalasi Next](https://nextjs.org/docs/app/getting-started/installation), [ESLint Next](https://nextjs.org/docs/app/api-reference/config/eslint), [Next](https://registry.npmjs.org/next/16.4.6), [React](https://registry.npmjs.org/react/19.3.1), [TypeScript](https://registry.npmjs.org/typescript/6.0.3), [ESLint](https://registry.npmjs.org/eslint/9.39.5).

## Pemeriksaan tampilan

Periksa `/` pada viewport 360px dan desktop: label simulasi tampak, status menjadi dua kolom di mobile, teks membungkus tanpa scroll horizontal, dan tautan lewati konten dapat difokuskan dengan keyboard. Tidak ada kontrol transaksi atau navigasi fitur yang belum tersedia.

Override terbatas minimatch 11.0.1 (BlueOak-1.0.0) pada typescript-estree menutup [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249); kompatibilitas diperiksa melalui lint/typecheck/build. ESLint 9 sudah berstatus end-of-support dari upstream, tetapi plugin React bawaan konfigurasi Next saat ini masih mensyaratkan ESLint <=9. Gunakan patch terakhir 9.39.5 dengan audit bersih; migrasi tooling pada SS-007 saat peer plugin mendukung ESLint 10.

Pemeriksaan SS-007 terhadap dependency terkunci masih menemukan peer ESLint sampai
`^9.7` pada `eslint-plugin-react`; versi ESLint tetap 9.39.5. Upgrade mayor menunggu
dukungan peer. Web checks kini dipanggil oleh [Runtime CI](../../docs/RUNTIME-CI.md)
dan hasilnya wajib lulus pada `Runtime quality gate`.
