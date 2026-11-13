# SS-008 — Seleksi vendor dan audit hak data G0

Fase: A | Prioritas: P0

## Tujuan

Putuskan kelayakan akses data sebelum integrasi pasar.

## Scope

- Bandingkan kemampuan feed/historis, depth, timestamp, sequence, SLA dan biaya.
- Konfirmasi hak storage, display/non-display, analisis dan redistribusi.
- Tetapkan universe pilot, anggaran dan kriteria kualitas melalui ADR.

## Acceptance criteria

- [ ] Bukti hak data dan keputusan vendor tercatat tanpa kontrak rahasia di repo.
- [ ] Sample feed/historis dinilai dan gap kemampuan dicatat.
- [ ] Aturan efektif lintas tanggal dan kebutuhan pembaruan kontrak ditinjau.
- [ ] G0 tetap pending bila bukti belum cukup.

## Dependency

SS-001

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 8, 10 G0, 15 A, 16.

## Branch

`feat/<issue-number>-data-vendor`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.

## Hasil inspeksi — 13 November 2026

[Audit vendor](../market-data/vendor-audit.md), [ADR-0002 Proposed](../decisions/0002-market-data-procurement.md),
dan [protokol penawaran/evaluasi](../market-data/vendor-evaluation.md) tersedia.
Prioritas pencarian: IQ Plus SCF; pembanding ICE, alternatif lokal RTI.
Pemilik belum memiliki vendor, sampel berizin, atau anggaran. Hak spesifik aplikasi,
keputusan vendor final, dan pengukuran sampel belum terpenuhi; acceptance terkait
tetap belum dicentang. G0 **pending**. Gunakan `Refs #8` pada PR tahap audit agar
merge dokumentasi tidak menutup issue sebelum bukti eksternal dilengkapi.
