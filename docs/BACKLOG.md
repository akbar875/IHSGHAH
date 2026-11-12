# Backlog implementasi

Scaffolding dokumentasi/struktur disiapkan pada branch `chore/project-scaffolding`. Sistem belum diimplementasikan. Setiap item berikut adalah satu scope issue/branch; nomor GitHub ditentukan saat penerbitan, bukan dari ID SS.

| ID | Pekerjaan | Fase | Prioritas | Dependency |
|---|---|---|---|---|
| [SS-001](issues/SS-001-architecture.md) | ADR stack dan batas modul | foundation | P0 | — |
| [SS-002](issues/SS-002-contracts.md) | Kontrak API dan event berversi | foundation | P0 | SS-001 |
| [SS-003](issues/SS-003-web-bootstrap.md) | Bootstrap web Next.js dan TypeScript | foundation | P0 | SS-001, SS-002 |
| [SS-004](issues/SS-004-api-bootstrap.md) | Bootstrap API FastAPI modular | foundation | P0 | SS-001, SS-002 |
| [SS-005](issues/SS-005-worker-bootstrap.md) | Bootstrap worker dan lifecycle | foundation | P0 | SS-004 |
| [SS-006](issues/SS-006-local-infra.md) | Lingkungan lokal PostgreSQL dan Redis | foundation | P0 | SS-004, SS-005 |
| [SS-007](issues/SS-007-runtime-ci.md) | CI runtime dan quality checks | foundation | P0 | SS-003, SS-004, SS-005, SS-006 |
| [SS-008](issues/SS-008-data-vendor.md) | Seleksi vendor dan audit hak data G0 | A | P0 | SS-001 |
| [SS-009](issues/SS-009-instrument-rules.md) | Aturan instrumen dan kalender berversi | A | P0 | SS-002, SS-004, SS-008 |
| [SS-010](issues/SS-010-persistence.md) | Penyimpanan point-in-time dan audit append-only | A | P0 | SS-002, SS-006 |
| [SS-011](issues/SS-011-market-adapter.md) | Adapter feed dan normalisasi | A | P0 | SS-005, SS-008, SS-009, SS-010 |
| [SS-012](issues/SS-012-feed-quality.md) | Kualitas feed dan abstention | A | P0 | SS-011 |
| [SS-013](issues/SS-013-feature-engine.md) | Feature engine point-in-time dan tekanan transaksi | B | P1 | SS-009, SS-010, SS-011, SS-012 |
| [SS-014](issues/SS-014-replay-simulator.md) | Replay dan simulator eksekusi konservatif | B | P0 | SS-009, SS-010, SS-011 |
| [SS-015](issues/SS-015-risk-engine.md) | Risk engine dan state machine rencana | B | P0 | SS-009, SS-010, SS-012 |
| [SS-016](issues/SS-016-baseline-evaluation.md) | Baseline, ranking nominal dan protokol holdout G1 | B | P0 | SS-013, SS-014, SS-015 |
| [SS-017](issues/SS-017-market-api.md) | API kandidat, detail dan stream resinkronisasi | C | P1 | SS-002, SS-004, SS-010, SS-012, SS-015 |
| [SS-018](issues/SS-018-screener-dashboard.md) | Dashboard kandidat dan keadaan kosong | C | P1 | SS-003, SS-017 |
| [SS-019](issues/SS-019-stock-detail.md) | Detail saham, chart dan order book | C | P1 | SS-018 |
| [SS-020](issues/SS-020-watchlist-settings.md) | Watchlist dan konfigurasi risiko pengguna | C | P1 | SS-010, SS-017, SS-018 |
| [SS-021](issues/SS-021-manual-positions.md) | Pencatatan fill dan pemantauan posisi parsial | C | P0 | SS-015, SS-017, SS-020 |
| [SS-022](issues/SS-022-in-app-alerts.md) | Alert in-app dan deduplikasi event | C | P1 | SS-005, SS-012, SS-015, SS-021 |
| [SS-023](issues/SS-023-security-isolation.md) | Keamanan, autentikasi dan isolasi akun | C | P0 | SS-004, SS-010, SS-017 |
| [SS-024](issues/SS-024-internal-news.md) | Informasi resmi dan berita internal | B | P1 | SS-008, SS-010, SS-013, SS-023 |
| [SS-025](issues/SS-025-operations.md) | Observabilitas, recovery dan kill switch | D | P0 | SS-007, SS-011, SS-012, SS-022, SS-023 |
| [SS-026](issues/SS-026-paper-integration.md) | Acceptance terpadu dan integrasi paper live | D | P0 | SS-016, SS-019, SS-020, SS-021, SS-022, SS-023, SS-025 |
| [SS-027](issues/SS-027-paper-observation.md) | Observasi prospektif dan laporan G2 | D | P0 | SS-026 |
| [SS-028](issues/SS-028-pilot-readiness.md) | Kesiapan pilot terbatas dan keputusan G3 | E | P2 | SS-027 |

## Cara memilih issue

Mulai dari SS-001, lalu SS-002. Setelah kontrak disepakati, bootstrap web dan backend dapat dikerjakan pada branch terpisah. SS-008 dapat berjalan setelah keputusan fondasi; fitur UI dapat memakai fixture berlabel setelah kontrak/API siap. SS-024 adalah jalur informasi internal tambahan dan tidak wajib memaksakan berita sebagai fitur ranking bila ablation tidak mendukungnya.

## Gerbang

- G0: bukti hak/kualitas data dari SS-008 sampai SS-012, termasuk aturan dan penyimpanan terkait.
- G1: replay/risiko/baseline dan laporan holdout SS-013 sampai SS-016.
- G2: integrasi/operasi SS-025/026 lalu observasi SS-027; minimum jumlah sesi/transaksi tidak otomatis berarti lolos.
- G3: keputusan pilot SS-028 setelah semua gerbang serta kajian distribusi terpenuhi.

Urutan dependency menentukan kesiapan implementasi, bukan persetujuan menyalakan sinyal live. Acceptance criteria lengkap tersedia pada setiap body issue dan [PRD](PRD-Saham-Signal.md). Penerbitan idempotent dijelaskan di [panduan issue](issues/README.md).
