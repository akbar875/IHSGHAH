# SS-006 — Lingkungan lokal PostgreSQL dan Redis

Fase: foundation | Prioritas: P0

## Tujuan

Buat setup development yang konsisten.

## Scope

- Sediakan Compose PostgreSQL/Redis dengan healthcheck dan volume.
- Dokumentasikan env, startup, shutdown, dan reset data lokal yang eksplisit.
- Definisikan pemisahan namespace research/paper/live.

## Acceptance criteria

- [ ] Setup fresh clone dapat dinyalakan dan dicek sehat.
- [ ] Port/kredensial lokal dapat dikonfigurasi.
- [ ] API menolak readiness jika dependency penting belum siap.
- [ ] Reset tidak pernah menyasar data produksi.

## Dependency

SS-004, SS-005

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 11, 13.

## Branch

`chore/<issue-number>-local-infra`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
