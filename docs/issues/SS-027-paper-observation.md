# SS-027 — Observasi prospektif dan laporan G2

Fase: D | Prioritas: P0

## Tujuan

Kumpulkan bukti prospektif tanpa menganggap batas minimum sebagai bukti otomatis.

## Scope

- Amati minimum awal 60 sesi bursa dan 300 transaksi simulasi layak eksekusi, mana yang lebih lama.
- Ukur sampel efektif, kalibrasi/fill/drawdown terhadap toleransi yang dikunci.
- Catat versi model, biaya, asumsi dan kondisi pasar
-  tidak mengubah holdout diam-diam.

## Acceptance criteria

- [ ] Laporan menunjukkan durasi/jumlah observasi dan dependensi antarsinyal.
- [ ] Kriteria yang dibekukan dinilai dengan ketidakpastian.
- [ ] Jika bukti tidak cukup, G2 tetap pending/no-go.
- [ ] Model tidak otomatis dipromosikan.

## Dependency

SS-026

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 10 G2, 15 D.

## Branch

`feat/<issue-number>-paper-observation`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
