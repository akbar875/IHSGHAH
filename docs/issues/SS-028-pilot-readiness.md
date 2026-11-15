# SS-028 — Kesiapan pilot terbatas dan keputusan G3

Fase: E | Prioritas: P2

## Tujuan

Siapkan keputusan rilis terbatas berbasis bukti.

## Scope

- Tinjau G0/G1/G2, kajian distribusi/legal/hak data dan biaya.
- Siapkan canary, persetujuan rilis, rollback, akses pilot serta monitoring hasil nyata.
- Integrasi broker tetap di luar scope dan memerlukan PRD terpisah.

## Acceptance criteria

- [x] Keputusan go/no-go G3 tertulis dengan penanggung jawab.
- [x] Recovery/rollback dan pembatasan penggunaan terbukti siap.
- [x] Jika gagal gerbang, UI tetap eksperimen tanpa klaim sinyal layak transaksi nyata.
- [x] Dokumentasi pilot dan kebijakan retensi disetujui.

## Dependency

SS-027

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 10 G3, 13, 15 E.

## Branch

`feat/<issue-number>-pilot-readiness`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.

## Hasil inspeksi awal — 15 November 2026

[Keputusan teknis G3: no-go dan runbook pilot](../market-data/pilot-readiness.md)
serta [matriks acceptance](../../research/reports/SS-028-inspection.md) tersedia
untuk review. #27 sudah closed di GitHub, tetapi G2 masih pending dengan nol
kredit prospektif. #8 kini closed melalui PR #58 dengan sumber EOD riset gratis;
G0 intraday tetap pending, #26 masih open dan G1 no-go. Bukti recovery fixture tidak
menggantikan drill deployment/canary. Persetujuan dokumen/retensi/legal/rilis
belum tersedia; checklist penyelesaian tetap terbuka. Tidak ada aktivasi pilot.

Checkbox keputusan mencatat keputusan teknis no-go dengan akbar875 sebagai
penanggung jawab rilis, bukan tanda tangan approval pilot. Checkbox UI mengikuti
bukti tes browser pada laporan inspeksi; dua acceptance lain tetap terbuka sampai
bukti drill deployment dan persetujuan dokumen/retensi tersedia.

## Tindak lanjut setelah merge #26

Pemilik memilih **research lokal; pilot tetap no-go**. PR #60 sudah merged pada
`3fc4268` sebelum finalisasi #28. [Paket review lokal](../../research/reports/SS-028-local-review.md)
menilai recovery dan pembatasan akses pada cakupan tersebut: 81 tes backend
memakai PostgreSQL nyata tanpa skip dan dua tes browser lulus. Checkbox kedua
hanya mengkualifikasi kontrol rollback/pause, restore serta pembatasan lokal;
tidak membuktikan rollback binary/schema atau deployment pilot. Persyaratan pilot
tetap berlaku jika cakupan diperluas; tidak ada gerbang pasar yang diluluskan.

Paket research lokal diterima melalui delegasi pemilik untuk menentukan default
best practice (“berikan best practice yang auto”) setelah paket commit `80b8029`
dan CI lulus tersedia. Agen menetapkan **SS028-local-retention-v1** dari default
SS-023 dan prinsip minimisasi/proteksi/retensi OWASP. Acceptance terakhir berlaku
pada dokumen penutupan **research lokal/no-go** tersebut; persetujuan legal dan
rilis pilot tetap pending. Lihat record delegasi pada paket review lokal.
