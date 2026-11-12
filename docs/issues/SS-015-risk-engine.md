# SS-015 — Risk engine dan state machine rencana

Fase: B | Prioritas: P0

## Tujuan

Terapkan rencana transaksi deterministik dan berversi.

## Scope

- Modelkan WATCH/READY/EXPIRED/CANCELLED terpisah dari state posisi.
- Hitung lot dari kas, budget risiko, stop/friksi dan kapasitas likuiditas.
- Validasi tick/limit/biaya, entry cutoff, deadline serta trailing yang tidak memperlebar risiko.

## Acceptance criteria

- [ ] READY tidak membuka posisi.
- [ ] Transisi idempotent dan bisa direplay.
- [ ] Boundary sizing dan risiko gabungan diuji dengan decimal/integer.
- [ ] Sinyal ditolak bila target/risiko/data tidak layak.
- [ ] Default desain PRD dicatat sebagai konfigurasi, bukan jaminan kerugian.

## Dependency

SS-009, SS-010, SS-012

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 7; FR-02/04/05; acceptance 3/5.

## Branch

`feat/<issue-number>-risk-engine`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
