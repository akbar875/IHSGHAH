# SS-016 — Baseline, ranking nominal dan protokol holdout G1

Fase: B | Prioritas: P0

## Tujuan

Evaluasi baseline sebelum klaim sinyal layak transaksi.

## Scope

- Bekukan split, label, purge/embargo, kebijakan risiko dan holdout akhir.
- Uji baseline trend/momentum/volatilitas serta kalibrasi probabilitas.
- Ranking hasil bersih memperhitungkan nominal, friksi, risiko dan fill.
- Catat eksperimen, regime/liquidity breakdown, ablation dan champion/challenger.

## Acceptance criteria

- [ ] Laporan out-of-sample mencakup expectancy, drawdown, fill, calibration dan coverage.
- [ ] Probabilitas tanpa bukti kalibrasi tetap null.
- [ ] Perubahan nominal tidak memakai cache pengguna/nominal lain.
- [ ] G1 dicatat go/no-go dengan bukti
- [ ]  kegagalan tetap berstatus eksperimen.
- [ ] Tidak ada auto-promotion hasil training.

## Dependency

SS-013, SS-014, SS-015

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 9, 10 G1; FR-01/03.

## Branch

`feat/<issue-number>-baseline-evaluation`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
