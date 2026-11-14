# SS-016 — Bukti implementasi simulasi dan keputusan G1

Tanggal pencatatan: 13 November 2026. **Data sepenuhnya buatan. G1: NO-GO.**
Ini merupakan uji jalur riset out-of-sample, bukan bukti performa pasar.

Protokol `SS-016-simulation-v1` memakai label maksimum 15 menit, purge 15 menit,
embargo 5 menit, biaya/aturan berversi, latensi 250 ms, slippage satu tick dan
reserve antrean 100 saham. Baseline trend adalah champion tetap; momentum,
volatilitas, trend tanpa pressure dan trend tanpa volume adalah challenger/ablation.
Seluruhnya dievaluasi pada Rp200.000 dan Rp1.000.000, tanpa pemilihan otomatis.

Split fixture Oktober 2026: train 1–7, validation 8–14, test 15–21 dan holdout
23–30, dengan pengecualian window yang melintasi batas/embargo. Kalender hanyalah
weekday buatan. Dua simbol SIMA/SIMB dan seluruh fitur merupakan simulasi.
Aturan dibekukan pada batas validation; walk-forward berikutnya tidak refit.

| Metrik holdout trend | Rp200.000 | Rp1.000.000 |
|---|---:|---:|
| Kandidat / rencana tertutup | 10 / 7 | 10 / 7 |
| Expectancy rencana tertutup bersih | Rp8.374,39 | Rp33.511,73 |
| Interval 95% bootstrap blok sesi | Rp11,03–Rp14.646,90 | −Rp26.475,10–Rp89.973,81 |
| Drawdown rencana tertutup | Rp14.613,80 | Rp102.296,60 |
| Fill saham | 90% | 72,86% |
| Coverage kandidat | 100% | 100% |
| Sisa saham gagal exit | 200 | 1.400 |
| Brier kandidat kalibrasi internal | 0,21714 | 0,21714 |
| Coverage kalibrasi pada rencana tertutup | 100% | 100% |

Ada lima sesi tertutup dalam holdout; bootstrap 1.000 draw dengan blok dua sesi
tidak menambah jumlah observasi pasar. Expectancy/drawdown di atas mengecualikan
P&L belum terealisasi, sehingga bukan estimasi portofolio. Open shares/cash flow
tetap tersedia dalam laporan lengkap. Probabilitas produk dan peluang fill tetap
null. Brier hanya menguji frekuensi bin validation terhadap label holdout tertutup.

Baseline/ablation menghasilkan metrik sama pada fixture ini karena input return,
pressure dan volume sengaja konstan. Tidak ada klaim kontribusi pressure/volume
atau superioritas salah satu aturan; pengujian terpisah memeriksa abstention saat
fitur dihapus. JSON menyimpan semua eksperimen serta breakdown champion.

Alasan no-go: G0 belum diadjudikasi, sampel sintetis sangat kecil, terdapat gagal
exit, nominal besar melampaui anggaran drawdown Rp50.000 dan interval expectancy
memuat nilai negatif. Tidak ada bukti risiko portofolio, kelayakan universe pasar,
atau persetujuan rilis. Hasil tetap eksperimen dan tidak mempromosikan model.

[Artefak metrik dan fingerprint](SS-016-simulation.json) mencatat hash protokol,
dataset, konteks referensi/biaya dan full report. `full_report_hash` merujuk
laporan `Study.run` lengkap sebelum dipangkas, bukan hash file ringkasan ini.
Cara reproduksi dan batas integrasi terdapat dalam
[panduan evaluasi](../../docs/market-data/baseline-evaluation.md).

Reproduksi 14 November 2026 (SS-025): snapshot kontrol operasi eksplisit kini ikut
fingerprint input risiko. Hash protokol/dataset/laporan diperbarui; seluruh metrik
eksekusi pada eksperimen tetap sama, G1 tetap no-go. Bukan holdout pasar baru.
