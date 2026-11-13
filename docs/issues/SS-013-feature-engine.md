# SS-013 — Feature engine point-in-time dan tekanan transaksi

Fase: B | Prioritas: P1

## Tujuan

Hitung fitur yang identik pada riset dan live.

## Scope

- Bangun fitur return/volatilitas/volume relatif/spread/depth.
- Klasifikasikan agresor dengan unknown dan cakupan klasifikasi.
- Pisahkan order-book imbalance dari buy/sell pressure.

## Acceptance criteria

- [x] Replay dan stream menghasilkan fitur identik pada cutoff sama.
- [x] Tidak menggunakan event sebelum available_at.
- [x] Pressure disembunyikan jika cakupan tidak memadai.
- [x] Tidak menampilkan jumlah investor dari data transaksi.

Bukti implementasi dan batas validasi simulasi: [feature engine](../market-data/feature-engine.md).
Validasi vendor SS-011 dan gerbang G0/G1 tetap pending; implementasi ini tidak
mengizinkan rilis live.

## Dependency

SS-009, SS-010, SS-011, SS-012

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 5, 9; FR-09; acceptance 6/10.

## Branch

`feat/<issue-number>-feature-engine`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
