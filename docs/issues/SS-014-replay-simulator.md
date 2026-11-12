# SS-014 — Replay dan simulator eksekusi konservatif

Fase: B | Prioritas: P0

## Tujuan

Bangun simulasi biaya dan fill yang dapat diuji.

## Scope

- Modelkan biaya bertanggal, spread, latency, slippage, antrean, partial/unfilled dan gagal exit.
- Tetapkan asumsi konservatif jika urutan stop/TP intrabar tidak diketahui.
- Pisahkan hasil simulasi dari fill nyata dan nonaktifkan alert live.

## Acceptance criteria

- [ ] ARA tanpa penjual tidak dianggap pembelian terisi.
- [ ] ARB tanpa pembeli tidak menutup posisi otomatis.
- [ ] Satu replay deterministik dapat diulang dengan input/seed sama.
- [ ] Semua asumsi dan limit data masuk laporan.

## Dependency

SS-009, SS-010, SS-011

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 7, 10; FR-11; acceptance 4/5.

## Branch

`feat/<issue-number>-replay-simulator`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
