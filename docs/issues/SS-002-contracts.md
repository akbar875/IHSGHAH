# SS-002 — Kontrak API dan event berversi

Fase: foundation | Prioritas: P0

## Tujuan

Sepakati kontrak sebelum web dan backend dikembangkan terpisah.

## Scope

- Definisikan entitas minimum PRD dan metadata as_of/mode/kualitas/versi.
- Tentukan decimal/integer uang, unit lot, UTC, sequence, dan probability nullable.
- Spesifikasikan REST serta snapshot/delta WebSocket, error, dan kompatibilitas versi.

## Acceptance criteria

- [ ] Schema dan contoh payload tervalidasi otomatis.
- [ ] Contoh probabilitas belum tervalidasi memakai null.
- [ ] Frontend tidak menerima dokumen berita atau kredensial.
- [ ] Kontrak menyertakan Signal, Position/fill, Alert, InstrumentRule, MarketEvent dan Experiment.

## Dependency

SS-001

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 12; FR-01, FR-06, FR-08, FR-12.

## Branch

`chore/<issue-number>-contracts`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
