# SS-013 — Feature engine point-in-time dan tekanan transaksi

Fase: B | Prioritas: P1

## Tujuan

Hitung fitur yang identik pada riset dan live.

## Scope

- Bangun fitur return/volatilitas/volume relatif/spread/depth.
- Klasifikasikan agresor dengan unknown dan cakupan klasifikasi.
- Pisahkan order-book imbalance dari buy/sell pressure.

## Acceptance criteria

- [ ] Replay dan stream menghasilkan fitur identik pada cutoff sama.
- [ ] Tidak menggunakan event sebelum available_at.
- [ ] Pressure disembunyikan jika cakupan tidak memadai.
- [ ] Tidak menampilkan jumlah investor dari data transaksi.

## Dependency

SS-009, SS-010, SS-011, SS-012

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 5, 9; FR-09; acceptance 6/10.

## Branch

`feat/<issue-number>-feature-engine`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
