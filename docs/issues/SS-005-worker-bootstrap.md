# SS-005 — Bootstrap worker dan lifecycle

Fase: foundation | Prioritas: P0

## Tujuan

Siapkan entry point worker yang dapat dihentikan dengan aman.

## Scope

- Gunakan modul domain backend bersama, tanpa menduplikasi aturan.
- Sediakan startup/shutdown, heartbeat, retry terbatas dan konfigurasi mode.
- Belum menghubungkan vendor atau menghasilkan sinyal.

## Acceptance criteria

- [ ] Worker dapat start/stop secara bersih.
- [ ] Heartbeat dan kegagalan tercatat tanpa kredensial.
- [ ] Retry tidak berjalan tanpa batas atau membuat efek ganda.

## Dependency

SS-004

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 8, 11.

## Branch

`chore/<issue-number>-worker-bootstrap`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
