# SS-007 — CI runtime dan quality checks

Fase: foundation | Prioritas: P0

## Tujuan

Tambahkan pemeriksaan aplikasi pada CI setelah bootstrap.

## Scope

- Jalankan lint/typecheck/build web serta lint/type/smoke backend.
- Gunakan dependency terkunci dan service DB/cache bila diperlukan.
- Pertahankan validasi scaffold dan minimalkan permission workflow.

## Acceptance criteria

- [x] PR gagal bila pemeriksaan runtime yang relevan gagal.
- [x] CI dapat berjalan tanpa rahasia vendor.
- [x] Perintah lokal dan CI didokumentasikan.
- [x] Fixture diberi label simulasi.

## Dependency

SS-003, SS-004, SS-005, SS-006

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 13, 14.

## Branch

`chore/<issue-number>-runtime-ci`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.

## Implementasi

Workflow Runtime CI memanggil lima reusable workflow dan menggabungkan hasilnya
melalui `Runtime quality gate`. Backend membangun wheel dan menjalankan smoke API/
worker dari environment runtime terpisah dengan dependency terkunci. Workflow tanpa
secret vendor memakai permission `contents: read`. Perintah lokal, batas simulasi,
integrasi DB/cache, dan required status check tersedia di
[panduan CI runtime](../RUNTIME-CI.md). Branch: `codex/7-runtime-ci`.
