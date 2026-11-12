# SS-012 — Kualitas feed dan abstention

Fase: A | Prioritas: P0

## Tujuan

Tahan sinyal ketika input kritis tidak sehat.

## Scope

- Modelkan live/delayed/degraded/stale/disconnected dan ambang sesuai SLA.
- Pisahkan umur transaksi terakhir dari kesehatan stream.
- Bekukan entry dan kirim event gangguan posisi tanpa membuat exit dari data stale.

## Acceptance criteria

- [ ] Heartbeat sehat pada saham sepi tidak dianggap putus.
- [ ] Gap/heartbeat melewati ambang memblokir entry sampai resinkronisasi.
- [ ] Delayed tidak menghasilkan entry real-time.
- [ ] Skenario acceptance 1/2/7 PRD lulus dan audit G0 diperbarui.

## Dependency

SS-011

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 8, 10 G0; FR-02.

## Branch

`feat/<issue-number>-feed-quality`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
