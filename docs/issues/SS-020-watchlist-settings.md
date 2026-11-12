# SS-020 — Watchlist dan konfigurasi risiko pengguna

Fase: C | Prioritas: P1

## Tujuan

Simpan watchlist, nominal, biaya broker dan batas risiko per akun.

## Scope

- Bangun API dan UI pengaturan serta watchlist.
- Validasi konfigurasi biaya bertanggal dan budget risiko.
- Propagasikan perubahan ke kalkulasi/cache milik pengguna.

## Acceptance criteria

- [ ] Watchlist pengguna terisolasi.
- [ ] Input nominal/biaya/risiko tidak valid ditolak.
- [ ] Perubahan pengaturan menghitung ulang kelayakan sesuai kontrak.
- [ ] Tidak ada tarif broker asumsi yang disajikan sebagai terverifikasi.

## Dependency

SS-010, SS-017, SS-018

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 3, 12, 13; FR-03.

## Branch

`feat/<issue-number>-watchlist-settings`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
