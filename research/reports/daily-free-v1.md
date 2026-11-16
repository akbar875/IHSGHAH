# Hasil validasi harian gratis — 16 November 2026

**Studi selesai; keputusan G1: NO-GO.** Scope harian disetujui pemilik pada
16 November 2026. G0 meloloskan file untuk riset offline terbatas, tetapi belum
meloloskan rilis sinyal. Tidak ada sinyal produk atau paper live yang diaktifkan.

## Protokol dan bukti

[Protokol](../protocols/daily-free-v1.json) dibekukan pada commit `0635d23`;
kode studi dan tes dibekukan pada `dd021f6`, sebelum eksekusi. Champion momentum20
ditetapkan sebelum hasil dibuka. Tidak ada pemilihan ulang parameter/baseline
untuk membuat holdout terlihat lulus. Holdout yang sudah dibuka tidak boleh
digunakan untuk tuning lalu disebut pengujian baru.

[Receipt agregat](daily-free-v1.json) mencatat SHA-256 protokol, source, kode dan
laporan lokal lengkap, waktu run, denominator, semua fold/baseline, stress biaya,
kalibrasi dan keputusan. Sumber: [Aethereal IDX Stock Features](https://dataset.aethereal.top/datasets/idx-stock-features),
CC BY 4.0; hasil ini transformasi agregat dengan atribusi. Sebanyak **303.743**
record diperiksa/dipakai, **0** ditolak menurut importer, **114** ticker tersedia.
Raw CSV dan baris exposure studi tetap di `.work`, bukan di Git atau browser.

Baseline aturan tetap tidak membutuhkan training parameter. Validation
2021–2022 (93 siklus) hanya memasang probabilitas riset konstan dari frekuensi
siklus bersih positif. Test 2023–2024 (89 siklus) dan holdout 2025–13 November
2026 (83 siklus) tidak melakukan refit. Setelah purge/warmup dan batas horizon,
keputusan holdout pertama 12 Februari 2025, exit terakhir 12 November 2026.
Setiap fold memulai modal terpisah; return antarfold tidak disambung.

Sinyal memakai fitur setelah close, entry close sesi berikutnya, return posisi
baru dihitung mulai sesi setelah entry. Lima sesi holding kemudian full exit;
slot kosong tetap cash. Portofolio modal awal Rp50 juta, lima slot, bobot awal
sama dan nilai posisi dibatasi 1% avg traded value 20 hari pada saat keputusan.
Tidak ada pembelian berdasarkan ranking harga masa depan. Return posisi hilang
mematikan studi, bukan menghilangkan posisi dari denominator.

Biaya asumsi sebelum run: beli 0,15%, jual 0,25%, slippage 0,10% per sisi;
stress menggandakan seluruh biaya/slippage. Ini skenario riset, bukan tarif broker
yang terverifikasi. Drawdown memakai MTM setiap sesi, bukan hanya exit.

## Hasil setelah biaya asumsi

| Baseline | Validation kumulatif | Test kumulatif | Holdout kumulatif | Drawdown holdout | Holdout biaya 2× |
|---|---:|---:|---:|---:|---:|
| Cash | 0,00% | 0,00% | 0,00% | 0,00% | 0,00% |
| Lima saham paling likuid, bobot sama | −37,34% | −58,68% | −51,66% | 60,97% | −70,65% |
| Momentum20 — champion dibekukan | +115,19% | −2,83% | **−25,46%** | **64,83%** | −54,53% |
| Low-vol dengan momentum positif | −40,10% | −21,18% | −27,91% | 36,97% | −56,06% |

Untuk momentum20, mean return **per siklus lima sesi** adalah −0,1392%; interval
95% moving-block bootstrap **[−1,8527%; +1,5335%]**. Ini bukan CI atas return
kumulatif atau expectancy transaksi individual. Bootstrap 5.000 draw memakai
blok empat siklus; draw tidak menambah jumlah observasi pasar. Batas bawah tidak
positif. Drawdown melebihi anggaran 20%. Brier 0,25706 melebihi batas 0,25.
Mean siklus 2025 positif, tetapi 2026 negatif; kedua regime tidak positif.
Jumlah siklus dan diversifikasi lolos, tetapi tidak menghapus kegagalan lain.
Cash tidak dianggap model menang: tidak berinvestasi dan expectancy-nya nol.

## G0 dan keterbatasan yang berdiri sendiri

| Bukti G0 harian | Keputusan |
|---|---|
| Atribusi/lisensi publisher, biaya Rp0 | PASS untuk file riset offline terbatas |
| SHA/schema/identitas/tanggal/angka/konsistensi struktural | PASS menurut aturan importer |
| Publikasi historis point-in-time | NOT_ASSESSED; download hari ini bukan jurnal publikasi masa lalu |
| Universe historis termasuk saham yang keluar/delisting | NOT_ASSESSED; file memakai pilihan saham publisher sekarang |
| Corporate action, kalender/aturan efektif, harga independen bursa | NOT_ASSESSED |
| Biaya broker dan fill eksekutabel | NOT_ASSESSED; fractional adjusted exposure/full-fill hanyalah asumsi |

Retur adjusted penyedia dibulatkan; belum dihitung ulang dari riwayat corporate
action independen. Kalender memakai tanggal yang teramati pada source. Semua
exposure bersifat fractional; lot, tick, suspensi, auction dan antrean belum
dimodelkan. Bias survivor dan keterbatasan availability tidak hilang karena
split kronologis. Semua ini membatasi interpretasi hasil, bahkan jika suatu
baseline kelak terlihat positif. Lisensi publisher tidak menyertifikasi harga
atau hak upstream BEI. Kelulusan file riset tidak memenuhi G0 rilis sinyal.

`paper_fills` dan `actual_fills` pada receipt keduanya kosong. Exposure hipotetis
tidak dimasukkan ke ledger fill. Model/probabilitas produk tetap belum dipromosikan.
Tidak ada klaim model terlatih, profit terverifikasi, atau kelulusan G2.

## Penggunaan dan tindak lanjut

Dari root repo, memakai environment backend sesuai README:

```sh
python -m saham_signal.daily_study --input .work/idx-stock-features.csv --protocol research/protocols/daily-free-v1.json --receipt .work/daily-free-v1-consumed.json --output .work/daily-free-v1-full.json
```

File CSV harus memiliki hash yang dibekukan. CLI membuat receipt eksklusif
**sebelum** parsing/evaluasi; kegagalan tetap mengonsumsi run. Perlindungan berlaku
pada path lokal itu, bukan registry global: operator dilarang menghapus receipt
atau mengganti path untuk mengklaim holdout baru. Run aktual sudah dijalankan;
command di atas adalah catatan reproduksi, bukan instruksi mengulang tuning.
CI hanya menguji data sintetis, tidak mengunduh atau membuka holdout pasar.

Untuk mencoba strategi baru, tulis protokol baru berdasarkan train/validation
yang sah dan gunakan holdout prospektif yang belum dibuka. Lengkapi bukti data
point-in-time/universe serta model biaya/eksekusi sebelum menilai rilis. Tidak
ada jaminan strategi berikutnya akan lulus. Checklist **G0 dan G1 lulus** tetap
belum terpenuhi; yang selesai adalah perubahan scope dan studi dengan hasil nyata.
