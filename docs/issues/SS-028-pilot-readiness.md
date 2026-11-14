# SS-028 — Kesiapan pilot terbatas dan keputusan G3

Fase: E | Prioritas: P2

## Tujuan

Siapkan keputusan rilis terbatas berbasis bukti.

## Scope

- Tinjau G0/G1/G2, kajian distribusi/legal/hak data dan biaya.
- Siapkan canary, persetujuan rilis, rollback, akses pilot serta monitoring hasil nyata.
- Integrasi broker tetap di luar scope dan memerlukan PRD terpisah.

## Acceptance criteria

- [ ] Keputusan go/no-go G3 tertulis dengan penanggung jawab.
- [ ] Recovery/rollback dan pembatasan penggunaan terbukti siap.
- [ ] Jika gagal gerbang, UI tetap eksperimen tanpa klaim sinyal layak transaksi nyata.
- [ ] Dokumentasi pilot dan kebijakan retensi disetujui.

## Dependency

SS-027

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 10 G3, 13, 15 E.

## Branch

`feat/<issue-number>-pilot-readiness`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.

## Hasil inspeksi — 15 November 2026

[Keputusan teknis G3: no-go dan runbook pilot](../market-data/pilot-readiness.md)
serta [matriks acceptance](../../research/reports/SS-028-inspection.md) tersedia
untuk review. #27 sudah closed di GitHub, tetapi G2 masih pending dengan nol
kredit prospektif; #8/#26 masih open dan G1 no-go. Bukti recovery fixture tidak
menggantikan drill deployment/canary. Persetujuan dokumen/retensi/legal/rilis
belum tersedia; checklist penyelesaian tetap terbuka. Tidak ada aktivasi pilot.
