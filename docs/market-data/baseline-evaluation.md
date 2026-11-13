# Baseline, ranking nominal dan holdout SS-016

Modul internal `saham_signal.application.evaluation` menyambungkan snapshot fitur
SS-013, sizing SS-015 dan replay SS-014. Seluruh hasil berstatus **experiment**.
Tidak ada endpoint bisnis, alert, promosi model, atau transaksi nyata.

## Protokol sebelum evaluasi

`Protocol` immutable membekukan identitas/hash dataset, konteks aturan/biaya,
versi kode, bukti universe historis, train/validation/test, holdout akhir,
label horizon, purge/embargo, seluruh baseline/ablation, champion, grid nominal,
kebijakan risiko/eksekusi, anggaran drawdown, dukungan kalibrasi, toleransi Brier,
jumlah sesi dan bootstrap blok beserta seed. Hash berubah bila parameter berubah.
Ambang fixture adalah desain demonstrasi, bukan ambang G1 yang disetujui.

Setiap `Case` berisi `FeatureSnapshot` point-in-time, spesifikasi/assessment risiko,
frame replay, akhir label, regime dan kategori likuiditas. Snapshot harus tepat
pada waktu keputusan; pemanggil membangunnya melalui FeatureEngine dan jurnal
SS-010, dengan revisi `available_at` yang benar. Engine tidak dapat membuktikan
keaslian snapshot buatan pemanggil. Hash konteks menyegel snapshot referensi
point-in-time pada keputusan/frame dan semua jadwal biaya.

Split bersifat kronologis dan half-open. Seluruh window fitur mulai sesudah
embargo awal fold. Waktu keputusan ditambah purge dan akhir label harus berada
sebelum batas akhir fold. Purge minimal sepanjang horizon label. Kasus di sekitar
batas dikeluarkan dan ID-nya dicatat; tidak dipindah ke fold lain. Test dimulai
setelah protokol dibekukan; holdout terpisah dan hanya dievaluasi setelah lengkap.
Label: target sebelum stop, bar ambigu memilih stop, gagal exit tetap tersensor.
Tidak ada label menang berdasarkan sentuhan harga tanpa volume eksekusi.

`Study.run` mengonsumsi holdout satu kali per instance, sebelum eksekusi, dan
mengembalikan receipt/hash audit. **Guard ini berada di memori.** Pemanggil wajib
merekam protokol sebelum membuka holdout dan menyimpan receipt consumed secara
atomik pada jurnal eksperimen SS-010, termasuk kegagalan. Rekonstruksi instance
bukan izin memakai ulang holdout. Dataset akhir yang sudah dibuka tidak boleh
menjadi bahan tuning; protokol baru memerlukan holdout prospektif baru. Modul ini
belum menyediakan orkestrator riset multi-proses atau durable lock tersendiri.

## Baseline, kalibrasi dan ranking

Tiga aturan long-only sederhana: trend (return/volatilitas), momentum (ditambah
volume relatif), dan volatilitas rendah dengan return positif. Pressure/volume
menjadi filter yang dapat dihapus pada ablation yang sudah dibekukan. Input
wajib yang hilang memicu abstention. Score 0–2 adalah kekuatan aturan, bukan
persentase peluang. Tidak ada training tersembunyi atau pemilihan hasil terbaik
otomatis. Champion/challenger ditetapkan dalam protokol.

Frekuensi target per bin dipasang hanya pada validation, untuk nominal yang
sama dan hanya posisi yang terisi serta sepenuhnya keluar. Dukungan minimal per
bin wajib terpenuhi. `research_probability` merupakan kandidat kalibrasi internal;
test/holdout mengukur Brier, reliability dan coverage tanpa refit. Observasi
walk-forward per sesi test/holdout memakai aturan dan kalibrator tetap. Field
produk `probability` dan `fill_probability` selalu null karena belum ada
persetujuan bukti kalibrasi produksi. Model fill/proyeksi belum tersedia.

Setiap nominal menghitung ulang kas bebas, lot integer, risiko, biaya bertanggal
dan kapasitas likuiditas, kemudian menjalankan replay sendiri. Tidak ada cache
lintas nominal/akun. Satu Study hanya menerima satu akun; `rank` menolak scope
campuran. Ranking per timestamp memakai reward target bersih dibagi risiko stop,
kemudian reward bersih, dengan kapasitas saham hasil sizing. Reward ini bersyarat
target tereksekusi. `expected_net_idr` tetap null tanpa model probabilitas/fill
tervalidasi; rasio tersebut tidak boleh ditampilkan sebagai expected return.
Ranking tidak memakai hasil fill atau P&L masa depan dari replay.

## Laporan dan keputusan G1

Laporan mencatat semua baseline/nominal dan fold, input/replay hash, split yang
dikeluarkan, peringkat, walk-forward, expectancy bersih, distribusi kerugian,
tail loss, drawdown rencana terealisasi, turnover, fill share rate, waktu ke fill
pertama, entry slippage, precision bersih positif, target-before-stop,
coverage/abstention serta Brier/reliability. Breakdown holdout tersedia menurut
regime, likuiditas, simbol, sesi, horizon; ukuran posisi terpisah per eksperimen.

Interval expectancy memakai moving-block bootstrap sesi berurutan, membawa
seluruh observasi dalam sesi; seed tetap. Sampel/sesi yang tidak cukup menghasilkan
null. Jumlah draw bootstrap bukan jumlah observasi pasar independen. Ukuran blok
dan anggaran risiko harus disetujui dari validasi sebelum holdout nyata.

Kasus adalah **rencana hipotetis independen**, bukan portofolio bersama: saldo
tidak digulirkan antar-kasus. Expectancy, precision dan calibration dikondisikan
pada rencana yang sepenuhnya keluar. Drawdown adalah urutan receipt rencana
tertutup, tanpa mark-to-market. Unfilled tetap dihitung dalam fill/coverage;
partial/failure tidak dibuang dari laporan, open shares dan cash flow negatifnya
dipertahankan. Ada open shares akan menggagalkan check G1. Metrik closed-plan
yang positif tidak cukup membuktikan kelayakan portofolio.

Keputusan selalu dicatat **no-go / experiment** pada boundary ini, termasuk
jika seluruh check statistik lolos. Check meliputi batas bawah interval positif,
anggaran drawdown, tidak ada failed exit, calibration dan diversifikasi antar
simbol/sesi/regime. Bukti G0, backtest portofolio dengan risiko gabungan, kecukupan
sampel efektif serta peninjauan rilis independen masih diperlukan. Tidak ada
fungsi yang mempromosikan model. Pelulusan G1 nyata memerlukan keputusan terpisah
berdasarkan bukti tersebut; issue implementasi SS-016 selesai bukan berarti G1 go.

## Reproduksi simulasi

Pada `services/api`, setelah setup sesuai README API:

```sh
uv run --locked python -m saham_signal.adapters.evaluation_simulation
uv run --locked pytest tests/test_evaluation.py
```

CLI mencetak JSON ringkasan reproducible, termasuk breakdown. `Study.run`
mengembalikan detail seluruh baris, ranking, walk-forward dan audit replay.
Fixture sengaja menciptakan fitur, harga, kalender weekday dan dua simbol fiktif;
bukan sampel vendor atau validasi kalender BEI. Laporan ringkas yang direkam ada
di [hasil simulasi](../../research/reports/SS-016-simulation.md). Tidak ada data
pasar berlisensi, artefak model besar, atau posisi pengguna dalam fixture.
