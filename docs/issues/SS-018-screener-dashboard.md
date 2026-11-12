# SS-018 — Dashboard kandidat dan keadaan kosong

Fase: C | Prioritas: P1

## Tujuan

Bangun dashboard minimalis sesuai PRD.

## Scope

- Tampilkan ranking, nominal, status sesi/data, entry/stop/target/horizon.
- Tambahkan pencarian dan filter kandidat aktif.
- Dukung loading, kosong, pasar tutup, delayed, stale, model belum tervalidasi dan disconnected.

## Acceptance criteria

- [ ] Fixture simulasi selalu berlabel.
- [ ] Probability null tampil Tidak tersedia.
- [ ] Perubahan nominal memicu permintaan ulang yang tepat.
- [ ] Angka inti terbaca pada lebar 360px.
- [ ] Tidak ada feed berita atau detail model internal.

## Dependency

SS-003, SS-017

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 4 A/C; FR-01/03; acceptance 12.

## Branch

`feat/<issue-number>-screener-dashboard`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
