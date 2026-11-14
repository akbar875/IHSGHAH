# SS-026 — Bukti kualifikasi offline

Semua input adalah simulasi. Laporan ini bukan bukti profitabilitas, feed vendor,
paper live atau kelulusan G0/G1/G2/G3. Dependency implementasi #16/#19/#20/#21/
#22/#23/#25 closed pada inspeksi GitHub; #8/G0 open dan SS-016 G1 no-go.

Receipt [12 skenario](SS-026-acceptance.json) merujuk hasil pytest dan Playwright
yang benar-benar dijalankan; hash masing-masing file hasil disimpan. `revision_kind`
`worktree-base` berarti hasil lokal dari worktree perubahan di atas commit dasar,
bukan pengujian kode commit dasar itu sendiri. CI menghasilkan receipt tersendiri
yang terikat SHA checkout dalam artifact `paper-acceptance-<run_id>`.

| PRD 14 | Hasil sintetik | Bukti utama |
|---|---|---|
| 1 Feed putus | Lulus | warning tanpa fill exit, retry sink |
| 2 Saham sepi | Lulus | heartbeat sehat, umur trade lama dipertahankan |
| 3 Nominal/likuiditas | Lulus | batas kas, biaya, risiko dan kapasitas |
| 4 ARA tanpa penjual | Lulus | replay unfilled |
| 5 ARB tanpa pembeli | Lulus | posisi tetap terbuka |
| 6 Berita terlambat | Lulus | available_at dan mapping point-in-time |
| 7 Reconnect/out-of-order | Lulus | resnapshot reducer dan penggantian book browser |
| 8 Partial fill | Lulus | lot nyata, partial exit dan cost basis |
| 9 Riwayat/proyeksi | Lulus | salinan riwayat/cache dan expiry proyeksi browser |
| 10 Tekanan transaksi | Lulus | unknown, coverage dan pemisahan dari book |
| 11 Versi/dedup | Lulus | inbox PostgreSQL, retry/restore paper, pipeline dan web |
| 12 Mobile 360px | Lulus | layout sentuh, chart dan tanpa overflow |

Hasil lokal: 298 tes backend berhasil, satu tes SIGTERM Linux dilewati di Windows;
56 tes browser berhasil. Ruff lint/format, mypy, kontrak web, ESLint, TypeScript
dan build Next.js lulus. Dua kasus tambahan pipeline menahan exit dari candle
sebelum entry atau heartbeat yang kedaluwarsa; harga pecahan ditolak tanpa rounding.
Verifier receipt juga diuji dengan bukti skenario missing/skipped dan crash browser;
ketiganya menahan acceptance. Perubahan terakhir pada validator halaman diuji ulang
dengan tiga tes halaman; suite lengkap dijalankan lagi di CI.

[Receipt pipeline](SS-026-simulation.json) menghubungkan feed → fitur → baseline
→ risiko → replay pada akun `simulation-account` di paper. Skenario menghasilkan
600 saham beli dan 600 saham jual simulasi; posisi akhir nol. Nilai ini hanya
hasil fixture, bukan estimasi pasar. Fill aktual **excluded**, bukan diisi nol
sebagai kesimpulan tentang akun pengguna. Policy alert satu pengamatan tetap
null akibat hysteresis; tidak ada pengiriman inbox atau alert live dari replay.

Persistensi nyata PostgreSQL menguji empat retry bersamaan menghasilkan satu
receipt, RLS akun lain, trigger UPDATE/DELETE/TRUNCATE, hash tamper dan restore
ke schema kosong. Backup mencakup tabel paper, kemudian restore tetap pause.
Browser memakai respons mock; uji PostgreSQL/API dan browser merupakan bukti
komponen, bukan pengukuran feed berizin sampai tampilan dalam satu jalur produksi.

Screenshot laporan: [360px](../../docs/screenshots/SS-026-mobile.png) dan
[desktop](../../docs/screenshots/SS-026-desktop.png).

**Keputusan: paper live/G2 blocked.** Ketiga toleransi dan validation_ref masih
null; manifest belum layak digunakan untuk observasi. Tidak ada sesi atau
transaksi prospektif yang dikreditkan. Minimum 60 sesi DAN 300 transaksi layak
eksekusi serta review sampel efektif tetap wajib. Scope prospektif #26 tetap open
sampai bukti G0/G1 lulus, toleransi dibekukan, adapter/reservasi modal/publikasi
paper terintegrasi dan acceptance E2E terkait tersedia.
