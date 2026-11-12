# SS-009 — Aturan instrumen dan kalender berversi

Fase: A | Prioritas: P0

## Tujuan

Sediakan referensi perdagangan point-in-time.

## Scope

- Modelkan board, lot, tick, limit, sesi, suspensi dan aksi korporasi bertanggal efektif.
- Gunakan sumber otoritatif vendor/BEI yang diverifikasi saat implementasi.
- Tolak aturan belum didukung daripada menebak.

## Acceptance criteria

- [ ] Lookup memakai tanggal berlaku dan zona waktu yang benar.
- [ ] Boundary fraksi/sesi dan perubahan aturan diuji.
- [ ] Instrumen tersuspensi atau board belum didukung tidak lolos entry.

## Dependency

SS-002, SS-004, SS-008

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 6 FR-02/05, 8, 10.

## Branch

`feat/<issue-number>-instrument-rules`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
