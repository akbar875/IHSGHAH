# Keputusan vendor gratis SS-008 — 15 November 2026

**Pilihan: Aethereal Data, hanya untuk evaluasi/riset EOD. Anggaran vendor Rp0.
Keputusan feed intraday: NO-GO; gerbang G0 tetap PENDING.**

Pemilik meminta penyelesaian issue #8 dengan vendor gratis pada 15 November 2026.
Keputusan ini menyelesaikan seleksi dan audit dengan batas biaya tersebut; tidak
mengubah kebutuhan intraday PRD, memberi izin distribusi publik, atau mengaktifkan
feed pada aplikasi. ADR-0002 mencatat pembatasan ini. Bukti teknis saat ini cukup
untuk menolak penggunaan live, bukan cukup untuk menyatakan data berkualitas live.

## Perbandingan sumber gratis

| Sumber primer, diperiksa 15 November 2026 | Temuan dan keputusan |
|---|---|
| [Aethereal: IDX Stock Prices](https://dataset.aethereal.top/datasets/idx-stock-prices) | CSV/Parquet tanpa akun; lisensi publik “Free for research and education.” Dipilih untuk evaluasi lokal karena izin riset disebutkan dan unduhan aktual berhasil. |
| [Api.co.id: API Saham Indonesia](https://api.co.id/api-saham-indonesia/) | Free 500 hit/bulan, 30 request/menit; EOD/referensi tersedia, quote/intraday paket Starter. Alternatif untuk evaluasi setelah ada akun/key dan peninjauan hak; tidak memenuhi feed intraday gratis. |
| [Invezgo: subscription](https://docs.invezgo.com/en/getting-started/subscription/) | Tabel developer dimulai Advance Rp499.900/bulan; Trial gratis pada consumer bukan bukti API gratis. Tidak dipilih berdasarkan klaim blog free-tier. |
| [GOAPI Hub](https://goapi.io/hub/) | Stock Market IDX ditawarkan mulai Free Trial. Trial tidak membuktikan gratis berkelanjutan; tidak dipilih. |
| [Twelve Data: pembaruan Juli 2026](https://twelvedata.com/news/july-2026-update) | Direktori mencakup bursa yang belum didukung. Halaman XIDX saja tidak membuktikan entitlement IDX pada paket gratis; tidak dipilih tanpa bukti akses. |

Tidak ada kandidat yang diperiksa membuktikan paket gratis berkelanjutan dengan
trade intraday, depth lima level, sequence/recovery, izin aplikasi, dan SLA yang
memenuhi kebutuhan G0 sekaligus. Ini hasil pencarian pada sumber di atas, bukan
klaim bahwa tidak mungkin ada penawaran gratis lain.

## Bukti hak dan pembatasan

ID bukti publik **SS008-FREE-20261115**: halaman produk Aethereal di atas
mengizinkan riset/edukasi dan menyediakan unduhan. Bentuknya ketentuan publik,
bukan kontrak privat. Hanya evaluasi lokal nonkomersial dalam mode research yang
dipilih. Unduhan mentah disimpan di `.work/idx-stock-prices.csv` yang diabaikan
Git; repo hanya menyimpan alat audit, hash dan hasil agregat.

| Hak/kebutuhan | Kesimpulan |
|---|---|
| Unduh dan analisis lokal untuk riset | Didukung pernyataan lisensi publik; dipakai untuk audit ini |
| Storage sementara untuk evaluasi | Salinan kerja lokal dari unduhan; bukan persetujuan arsip permanen |
| Retensi tanpa batas, backup/DR lintas pihak | Tidak dijelaskan; tidak diasumsikan diizinkan |
| Display harga/chart/book dalam aplikasi atau publik | Belum terbukti; tidak diaktifkan |
| Redistribusi, API/export ke orang lain, komersial | Belum terbukti; data mentah tidak masuk Git |
| Model training, distribusi derived data/model | Hak spesifik belum dijelaskan; tidak dipromosikan lewat keputusan ini |
| Status otorisasi upstream BEI | Belum diverifikasi; lisensi publisher bukan bukti lisensi upstream |

Jadwal pembaruan yang dipublikasikan bukan SLA kontraktual. Tidak ada jaminan
uptime/latensi. Periksa ulang lisensi sebelum setiap penggunaan baru atau bila
halaman berubah. Setelah evaluasi, salinan kerja dapat dihapus pemilik; tidak ada
job yang menyimpan ulang atau membagikannya otomatis.

## Hasil pengukuran unduhan aktual

Sumber unduhan: `https://dataset.aethereal.top/files/idx-stock-prices.csv`.
Diambil 15 November 2026; HTTP berhasil. Seluruh file diperiksa offline dengan
[audit-eod-csv.py](../../scripts/audit-eod-csv.py), bukan data fixture.
Hasil agregat juga tersedia sebagai [JSON audit](free-vendor-audit-result.json).

| Ukuran / pemeriksaan | Hasil |
|---|---:|
| Ukuran file | 28.776.712 byte |
| Record yang diperiksa (denominator) | 518.956 |
| Ticker unik | 114 |
| Tanggal unik | 6.575 |
| Rentang tanggal record | 2000-06-06 sampai 2026-11-13 |
| Record minimum/maksimum per ticker | 460 / 6.575 |
| Field hilang/lebih, tanggal invalid | 0 / 0 |
| Duplikat `(ticker,date)` | 0 |
| Urutan tanggal mundur per ticker | 0 |
| Angka invalid/nonfinite, harga <=0, volume invalid | 0 / 0 / 0 |
| Record akhir pekan | 0 |
| Volume nol | 38.850 |
| Pelanggaran `low <= open/close <= high` | **308** |
| Adjusted close berbeda dari close | 471.473 |

SHA-256:
`d73c4a0229a99aff3818442824dc2f819f9780a41b150ee0c456a1c1a4805eb6`.

Publisher mengiklankan 120 saham, sedangkan unduhan ini berisi 114 ticker unik;
selisih dicatat tanpa mengarang enam ticker yang tidak tersedia. File hanya
memuat harian dan publisher menyatakan pemilihan saham saat ini tidak memasukkan
delisting. Universe historis tidak dapat dianggap point-in-time atau bebas
survivorship bias. Adjusted close tidak boleh diperlakukan sebagai harga eksekusi.
Anomali OHLC wajib dikarantina sebelum pemakaian; tidak diperbaiki diam-diam.
Volume nol bukan otomatis record rusak ataupun bukti instrumen sedang tradable.

Dataset ini tidak menyediakan event/provider/received/available timestamps,
sequence, heartbeat, book/depth, bid/ask atau koreksi point-in-time. Latensi,
recovery feed, dan kemampuan simulasi fill intraday **NOT_ASSESSED/UNAVAILABLE**.
Audit struktur ini bukan validasi kebenaran harga terhadap bursa, kelengkapan sesi
terhadap kalender, corporate action, ataupun reproduksi kondisi pasar saat itu.

## Universe, biaya dan penggunaan

Universe evaluasi awal adalah seluruh ticker yang benar-benar ada dalam unduhan
untuk audit struktur; tidak dipakai menentukan kandidat transaksi. Subset riset
lanjutan maksimal 20 saham mengikuti aturan point-in-time ADR-0002 dan SS-009;
kelayakan itu belum dapat dibuktikan dari file ini. Biaya vendor Rp0, tanpa akun,
key, kartu kredit, langganan trial atau upgrade otomatis. Infrastruktur sendiri
tetap memiliki biaya terpisah.

Pengujian hanya offline dan tidak mengubah adapter SS-011, mode deployment,
status data UI, alert atau kebijakan kualitas SS-012. Tidak ada polling otomatis.
Sumber ini tidak boleh dimasukkan ke jalur live sebagai pengganti feed intraday.

## Reproduksi dan validasi

Dengan Python 3.13 (stdlib saja), unduh CSV ke `.work/idx-stock-prices.csv`, lalu:

```sh
python scripts/audit-eod-csv.py .work/idx-stock-prices.csv
python scripts/test_audit_eod_csv.py
```

File remote berubah seiring pembaruan; cocokkan SHA-256 sebelum membandingkan
angka dengan laporan ini. Output alat tidak mengandung record harga mentah.
Tiga test sintetis memeriksa deteksi anomali, angka nonfinite, duplikat, urutan,
tanggal, field hilang dan penolakan input kosong/schema salah. Audit tidak
memperbaiki data atau otomatis memberi PASS.

## Penyelesaian issue dan gerbang terpisah

Keputusan #8: **pilih sumber gratis untuk riset EOD; tolak penggunaan intraday
dengan bukti saat ini**. Bukti hak terbatas, evaluasi historis aktual dan gap feed,
budget/universe/kriteria, serta tinjauan tanggal efektif sudah dicatat. Feed tidak
tersedia dinilai sebagai gap, bukan diganti feed simulasi agar terlihat lulus.

G0 tetap PENDING, G1–G3 tidak berubah. Persyaratan lisensi aplikasi/upstream,
kelengkapan historis dan aturan, feed intraday/recovery, kapasitas serta uji
integrasi SS-009–012 wajib dipenuhi sebelum keputusan NO-GO dapat ditinjau ulang.
Ketentuan BEI yang efektif 1 Januari 2027 tetap harus diperiksa bila jalur data
berlisensi kelak digunakan; jangan menafsirkan pengecualian biaya non-display
sebagai izin mengambil semua data gratis.
