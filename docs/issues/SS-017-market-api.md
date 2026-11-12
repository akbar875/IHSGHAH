# SS-017 — API kandidat, detail dan stream resinkronisasi

Fase: C | Prioritas: P1

## Tujuan

Sediakan API sesuai kontrak untuk UI dan fixture simulasi.

## Scope

- Implementasikan query kandidat/detail/depth/chart/riwayat serta stream snapshot+delta.
- Gunakan account/mode/nominal/horizon sebagai bagian cache key.
- Sediakan fixture eksplisit untuk UI tanpa memerlukan model tervalidasi.

## Acceptance criteria

- [ ] Respons menyertakan as_of/mode/kualitas/versi dan expiry.
- [ ] Reconnect mewajibkan resinkronisasi.
- [ ] Missing data tidak diganti angka rekaan.
- [ ] Endpoint kandidat memakai hasil model hanya setelah integrasi SS-016 dan gerbang sesuai mode.
- [ ] Berita internal tidak bocor ke respons.

## Dependency

SS-002, SS-004, SS-010, SS-012, SS-015

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 12; FR-01/03/07/08.

## Branch

`feat/<issue-number>-market-api`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
