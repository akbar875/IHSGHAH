# SS-004 — Bootstrap API FastAPI modular

Fase: foundation | Prioritas: P0

## Tujuan

Siapkan fondasi API tanpa logika sinyal.

## Scope

- Buat Python package modular, konfigurasi tervalidasi dan dependency terkunci.
- Tambahkan health/readiness dan error contract.
- Tetapkan struktur domain, application, adapter, serta konfigurasi CORS eksplisit.

## Acceptance criteria

- [ ] Fresh clone dapat menjalankan API menurut dokumentasi.
- [ ] Health dan readiness membedakan proses hidup dari dependency siap.
- [ ] Pemeriksaan lint/type dan smoke API lulus.
- [ ] Mode tidak valid ditolak saat startup.

## Dependency

SS-001, SS-002

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 11, 12, 13.

## Branch

`chore/<issue-number>-api-bootstrap`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
