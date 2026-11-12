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
