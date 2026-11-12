# SS-019 — Detail saham, chart dan order book

Fase: C | Prioritas: P1

## Tujuan

Tampilkan rencana dan data pasar dengan pemisahan aktual/proyeksi.

## Scope

- Pilih chart library dengan lisensi yang sesuai.
- Render candle/volume, entry/stop/TP/expiry dan proyeksi bertingkat cakupan.
- Render book 5 tingkat jika tersedia, snapshot age, spread, pressure/cakupan.

## Acceptance criteria

- [ ] Proyeksi putus-putus dan latar berbeda dari riwayat aktual.
- [ ] Pergantian interval tidak mengganti horizon diam-diam.
- [ ] Book tidak mencampur versi dan depth terbatas berlabel.
- [ ] Data yang tidak tersedia tidak disintesis.
- [ ] Chart dapat disentuh dan book tidak menutupi rencana pada 360px.

## Dependency

SS-018

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 4 B, 5; FR-07/08/09; acceptance 7/9/10/12.

## Branch

`feat/<issue-number>-stock-detail`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
