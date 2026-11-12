# SS-003 — Bootstrap web Next.js dan TypeScript

Fase: foundation | Prioritas: P0

## Tujuan

Siapkan aplikasi web yang bisa dijalankan tanpa fitur screener.

## Scope

- Buat app Next.js/TypeScript dengan dependency dipin dan lockfile.
- Sediakan halaman shell berlabel research/simulasi serta konfigurasi API.
- Tambahkan lint, typecheck, build, dan petunjuk setup.

## Acceptance criteria

- [x] Fresh clone dapat install dan menjalankan shell sesuai README.
- [x] Lint/typecheck/build lulus.
- [x] Tidak ada sinyal atau harga rekaan berlabel live.
- [x] Layout shell dapat digunakan pada lebar 360px.

## Dependency

SS-001, SS-002

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 4, 11.

## Branch

`chore/<issue-number>-web-bootstrap`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.

## Hasil implementasi — 12 November 2026

Dependency #1 dan #2 selesai; branch berasal dari main setelah kontrak #2 digabung. Shell Next.js/TypeScript tersedia di apps/web dengan versi exact, lockfile, konfigurasi API publik, mode tetap research/simulasi, serta lint/typecheck/build dan CI web. Tidak ada feed, harga, sinyal rekaan, atau endpoint aplikasi yang diimplementasikan.

Validasi lokal: npm ci --ignore-scripts, npm run check (lint/typecheck/build), npm audit (0 vulnerabilities), HTTP produksi 200, scaffold dan kontrak lulus. Pengujian browser pada viewport 360px: lebar konten 345px (scrollbar vertikal), tidak ada overflow horizontal; label simulasi, pembungkusan teks, dan fokus tautan lewati konten berfungsi. Console browser tanpa error/warning. Host lokal Node 22.17.0; CI menggunakan baseline 24.22.3.

Bukti: [mobile 360px](../evidence/ss-003/mobile-360.jpg) dan [desktop, termasuk fokus keyboard](../evidence/ss-003/desktop.jpg). Setup, batas konfigurasi, lisensi, override minimatch, dan tindak lanjut ESLint terdokumentasi di [panduan web](../../apps/web/README.md). Tidak ada publikasi aplikasi atau kelulusan G0/G1/G2/G3; review/merge ke main mengikuti CONTRIBUTING.md.