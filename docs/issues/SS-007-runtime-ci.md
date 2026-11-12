# SS-007 — CI runtime dan quality checks

Fase: foundation | Prioritas: P0

## Tujuan

Tambahkan pemeriksaan aplikasi pada CI setelah bootstrap.

## Scope

- Jalankan lint/typecheck/build web serta lint/type/smoke backend.
- Gunakan dependency terkunci dan service DB/cache bila diperlukan.
- Pertahankan validasi scaffold dan minimalkan permission workflow.

## Acceptance criteria

- [ ] PR gagal bila pemeriksaan runtime yang relevan gagal.
- [ ] CI dapat berjalan tanpa rahasia vendor.
- [ ] Perintah lokal dan CI didokumentasikan.
- [ ] Fixture diberi label simulasi.

## Dependency

SS-003, SS-004, SS-005, SS-006

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 13, 14.

## Branch

`chore/<issue-number>-runtime-ci`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
