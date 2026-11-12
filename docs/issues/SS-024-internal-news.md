# SS-024 — Informasi resmi dan berita internal

Fase: B | Prioritas: P1

## Tujuan

Tambahkan jalur informasi point-in-time bila sumber berizin tersedia.

## Scope

- Ingest berizin, deduplikasi, pemetaan emiten, kredibilitas dan first-available timestamp.
- Batasi penggunaan LLM untuk ekstraksi/ringkasan internal.
- Ukur kontribusi melalui ablation terhadap baseline
-  jalur ini tidak menghambat feed pasar.

## Acceptance criteria

- [ ] Backtest tidak memakai berita sebelum available_at.
- [ ] Konten eksternal diperlakukan data tidak tepercaya.
- [ ] Harga/sizing/biaya tetap deterministik.
- [ ] Berita tidak dikirim ke UI pengguna.
- [ ] Jika tidak memberi manfaat terukur, fitur berita tidak dipaksakan ke ranking.

## Dependency

SS-008, SS-010, SS-013, SS-023

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 8, 9, 10; acceptance 6.

## Branch

`feat/<issue-number>-internal-news`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
