# SS-011 — Adapter feed dan normalisasi

Fase: A | Prioritas: P0

## Tujuan

Hubungkan feed yang disetujui melalui adapter terisolasi.

## Scope

- Normalisasi trade, candle, book dan heartbeat ke kontrak bersama.
- Tangani duplicate, out-of-order, koreksi, sequence gap dan reconnect.
- Pisahkan fixture/replay dari feed vendor.

## Acceptance criteria

- [ ] Contract test sample vendor lulus.
- [ ] Gap book memicu snapshot ulang sebelum delta dilanjutkan.
- [ ] Timestamp sumber dan availability tidak hilang.
- [ ] Tidak mengalihkan feed dengan semantik berbeda secara diam-diam.

## Dependency

SS-005, SS-008, SS-009, SS-010

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 8; FR-08; acceptance 2/7.

## Branch

`feat/<issue-number>-market-adapter`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
