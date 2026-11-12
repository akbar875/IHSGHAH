# SS-001 — ADR stack dan batas modul

Fase: foundation | Prioritas: P0

## Tujuan

Bekukan keputusan awal stack, versi runtime, dan batas modul.

## Scope

- ADR mencatat pilihan Next.js/TypeScript, FastAPI, PostgreSQL, Redis serta alternatif.
- Verifikasi versi dan lisensi dependency melalui dokumentasi resmi saat implementasi.
- Tetapkan alur konfigurasi dan isolasi research/paper/live serta keputusan akun pilot.

## Acceptance criteria

- [x] ADR berstatus Accepted oleh pemilik repo.
- [x] Versi runtime serta ownership modul terdokumentasi.
- [x] Keputusan terbuka memiliki alasan dan tindak lanjut.

## Dependency

Tidak ada.

## Hasil inspeksi dan pengerjaan

Issue GitHub: [#1](https://github.com/akbar875/IHSGHAH/issues/1), diperiksa pada 12 November 2026; scope cocok dengan body lokal ini. Repo masih scaffold dan belum memiliki keputusan stack berversi, batas dependency backend, alur konfigurasi, maupun keputusan akun pilot.

Deliverable: [ADR-0001](../decisions/0001-stack-and-module-boundaries.md) beserta pembaruan indeks ADR dan ringkasan arsitektur. Versi/lisensi upstream telah diverifikasi; runtime, ownership, alternatif, isolasi, dan keputusan terbuka telah dicatat. ADR berstatus Accepted pada 12 November 2026 berdasarkan instruksi pemilik dalam chat untuk menyelesaikan issue setelah hasil dipresentasikan dan di-push; rujukan konfirmasi dicatat di ADR. Seluruh acceptance criteria dokumentasi terpenuhi. Belum ada build/integrasi aplikasi atau kelulusan gerbang yang diklaim.

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 11, 13, 16.

## Branch

`chore/<issue-number>-architecture`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
