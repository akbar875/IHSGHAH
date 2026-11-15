# SS-028 — Hasil inspeksi kesiapan pilot

15 November 2026 (WIB). Issue GitHub #28 cocok dengan body lokal: keputusan
G3, kesiapan recovery/pembatasan, perilaku eksperimen saat gagal gerbang,
serta persetujuan dokumentasi dan retensi. Branch: `feat/28-pilot-readiness`.

Dependency langsung #27 sudah closed saat inspeksi GitHub; bukti G2 tetap
pending dan nol kredit prospektif. #26 dan #8 masih open, G1 no-go. Catatan
SS-027 yang menyebut issue open merekam keadaan sebelumnya; tidak ada bukti
baru yang mengubah gerbang hanya karena status issue berubah.

## Pekerjaan yang tersedia untuk review

- [Keputusan G3 dan runbook](../../docs/market-data/pilot-readiness.md) menetapkan
  no-go teknis, pemilik keputusan, matriks bukti dan persetujuan, batas akses
  satu akun, canary bertahap, monitoring aktual terpisah dari paper, pemicu pause,
  rollback/recovery dan retensi. Tidak mengklaim persetujuan atau deployment.
- [Receipt no-go](SS-028-no-go.json) menyimpan status, kekurangan dan fingerprint
  bukti; hanya artefak operator, tanpa integrasi runtime/promotion.
- UI yang ada telah memuat label simulasi dan larangan transaksi nyata; tidak
  ada perubahan UI, kontrak, dependency, mode, data pribadi atau rilis produksi.

## Penilaian acceptance

| Acceptance | Hasil inspeksi |
|---|---|
| Keputusan go/no-go tertulis dengan penanggung jawab | No-go teknis terdokumentasi; akbar875 pemilik keputusan, persetujuan akhir pending |
| Recovery/rollback dan pembatasan terbukti siap | Bukti fixture SS-025/023 tersedia; drill target deployment dan canary masih pending |
| UI tetap eksperimen bila gagal gerbang | Perilaku existing dipertahankan: simulasi, entry ditahan, tanpa klaim layak transaksi nyata |
| Dokumentasi pilot dan retensi disetujui | Dokumen untuk review tersedia; approval pemilik/operator/legal belum tersedia |

Issue tidak boleh ditandai completed berdasarkan kesiapan dokumen saja.
Runbook mencantumkan bukti yang harus ditambahkan untuk menyelesaikan acceptance.
Merge, push, status closed dependency, tes sintetis dan CI bukan persetujuan G3.

## Validasi lokal

- `node scripts/check-scaffold.mjs`: lulus, termasuk tautan dokumen lokal.
- `node scripts/publish-issues.mjs`: dry run 28 issue, tanpa perubahan GitHub.
- JSON receipt diperiksa terhadap G1/G2, nol kredit, approval pending, pilot
  disabled dan 10 hash bukti UTF-8/LF: konsisten.
- Dari root, `services/api/.venv/Scripts/python.exe -m pytest
  services/api/tests/test_observation.py services/api/tests/test_market_api.py
  services/api/tests/test_security.py services/api/tests/test_operations.py
  -q -p no:cacheprovider --basetemp=.work/pytest-issue28 --maxfail=1`:
  **63 passed, 4 skipped**. Empat tes memerlukan DSN PostgreSQL disposable yang
  tidak dikonfigurasi; hasil ini tidak mengklaim drill database baru.
- Dari `apps/web`, dengan `PLAYWRIGHT_BROWSERS_PATH` menunjuk Chromium lokal,
  `node node_modules/@playwright/test/cli.js test tests/dashboard.spec.ts
  --grep 'simulation, null probabilities'`: **1 passed**. Membuktikan label
  Research/Simulasi, probabilitas unavailable dan model belum tervalidasi pada
  fixture browser. Percobaan awal tanpa path browser lokal gagal menjalankan
  browser; tidak dihitung sebagai bukti produk.
- `git diff --check`: lulus sebelum commit. Tidak ada perubahan runtime/UI
  sehingga tidak diperlukan dependency, migrasi atau deployment baru.

CI runtime pada PR memeriksa integrasi Linux/PostgreSQL/Redis secara terpisah;
hasilnya dicatat pada PR setelah run selesai, bukan diperkirakan di laporan ini.
