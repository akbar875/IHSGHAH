# SS-026 — Acceptance terpadu dan integrasi paper live

Fase: D | Prioritas: P0

## Tujuan

Satukan alur MVP tanpa melompati validasi data/model.

## Scope

- Jalankan 12 skenario acceptance PRD lintas service.
- Integrasikan feed, baseline, risiko, web, posisi dan alert dalam namespace paper.
- Kunci toleransi calibration/fill/drawdown dan rencana observasi sebelum G2.

## Acceptance criteria

- [x] Seluruh skenario PRD 14 memiliki hasil dan bukti.
- [ ] G0 dan G1 memiliki keputusan lulus sebelum paper live berkualitas sinyal.
- [x] Paper dan actual fill dipisahkan dalam laporan.
- [x] Kegagalan acceptance kritis menahan kemajuan.

Bukti dan batas: [implementasi acceptance terpadu](../market-data/paper-acceptance.md).
Hasil 12 skenario adalah kualifikasi sintetik backend/browser. Ledger aktual
dibaca terpisah dari replay; guard menahan setiap kegagalan kritis. Mekanisme
review G0/G1 tersedia dan teruji, tetapi keputusan lulus nyata belum tersedia:
#8/G0 pending dan SS-016 G1 no-go. Checkbox kedua tetap terbuka; paper live tidak aktif.

## Dependency

SS-016, SS-019, SS-020, SS-021, SS-022, SS-023, SS-025

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 14, 15 D; FR-01 sampai FR-12.

## Branch

`feat/<issue-number>-paper-integration`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
