# SS-021 — Pencatatan fill dan pemantauan posisi parsial

Fase: C | Prioritas: P0

## Tujuan

Pantau posisi nyata berdasarkan konfirmasi pengguna.

## Scope

- Catat beli/jual aktual dengan harga rata-rata, lot, biaya, waktu dan idempotency key.
- Hitung ulang rencana atas jumlah nyata dan dukung partial exit.
- Sediakan OPEN/PARTIAL/EXIT_REQUESTED/CLOSED dan peringatan overnight.

## Acceptance criteria

- [ ] Sentuhan harga chart tidak membuka posisi nyata.
- [ ] Partial fill tidak memakai seluruh nominal rencana.
- [ ] Stop terpicu tanpa fill jual tetap menyisakan posisi terbuka.
- [ ] Duplicate submit tidak menggandakan posisi/fill.
- [ ] Hasil nyata dan simulasi tetap terpisah.

## Dependency

SS-015, SS-017, SS-020

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 3, 7, 12; FR-06; acceptance 5/8.

## Branch

`feat/<issue-number>-manual-positions`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
