# SS-010 — Penyimpanan point-in-time dan audit append-only

Fase: A | Prioritas: P0

## Tujuan

Bangun schema dan migrasi untuk data serta audit yang dapat direplay.

## Scope

- Simpan timestamp lengkap, sequence, snapshot sinyal, fill/posisi dan eksperimen.
- Tambahkan migrasi, indeks, retensi dan isolasi akun/mode.
- Sediakan audit versi append-only dan idempotency key.

## Acceptance criteria

- [ ] Migrasi dapat diterapkan dari database kosong.
- [ ] Pengujian membuktikan duplicate event tidak menggandakan efek.
- [ ] Pembukuan memakai presisi tetap.
- [ ] Perubahan sinyal tidak menimpa versi historis.

## Dependency

SS-002, SS-006

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 8, 12; FR-12.

## Branch

`feat/<issue-number>-persistence`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
