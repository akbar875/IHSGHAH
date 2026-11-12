# SS-002 — Kontrak API dan event berversi

Fase: foundation | Prioritas: P0

## Tujuan

Sepakati kontrak sebelum web dan backend dikembangkan terpisah.

## Scope

- Definisikan entitas minimum PRD dan metadata as_of/mode/kualitas/versi.
- Tentukan decimal/integer uang, unit lot, UTC, sequence, dan probability nullable.
- Spesifikasikan REST serta snapshot/delta WebSocket, error, dan kompatibilitas versi.

## Acceptance criteria

- [x] Schema dan contoh payload tervalidasi otomatis.
- [x] Contoh probabilitas belum tervalidasi memakai null.
- [x] Frontend tidak menerima dokumen berita atau kredensial.
- [x] Kontrak menyertakan Signal, Position/fill, Alert, InstrumentRule, MarketEvent dan Experiment.

## Dependency

SS-001

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 12; FR-01, FR-06, FR-08, FR-12.

## Branch

`chore/<issue-number>-contracts`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.

## Hasil inspeksi dan implementasi — 12 November 2026

Issue GitHub #2 sesuai SS-002; belum ada komentar/perubahan scope saat inspeksi. SS-001 sudah closed dan ADR Accepted pada commit 47952c2; commit penerimaan disertakan karena belum tercakup di main saat branch dibuat.

Implementasi di [packages/contracts](../../packages/contracts/README.md): sumber deklaratif, JSON Schema 2020-12, OpenAPI 3.1.1, fixture simulasi, pemeriksaan Ajv/Python, dan CI. Mencakup entitas minimum PRD, metadata, unit/desimal/UTC, probabilitas nullable, REST/error/idempotency, stream snapshot/delta/reconnect, batas data publik, serta aturan versi. Branch: `codex/2-versioned-contracts`.

Validasi: `npm --prefix packages/contracts run check`, `python packages/contracts/test/check_python.py` dengan dependency pengujian, `node scripts/check-scaffold.mjs`, dry run penerbitan backlog, dan `git diff --check`. Belum merupakan implementasi endpoint, otorisasi, mesin posisi atau stream consumer; pengujian runtime/domain dan gerbang tetap issue terkait.
