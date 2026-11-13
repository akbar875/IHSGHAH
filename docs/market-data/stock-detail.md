# Detail saham, chart dan order book — SS-019

Klik ticker dashboard untuk membuka `/stocks/TEST`. Halaman memakai sesi research
dan endpoint SS-017 yang sudah ada, tanpa token publik atau data vendor. Rencana
ditampilkan sebelum chart dan book, termasuk nominal layanan, lot bila tersedia,
entry/stop/TP, horizon, waktu WIB, deadline exit dan expiry. Nominal detail berasal
dari konfigurasi layanan; input nominal dashboard tidak mengubahnya. Probabilitas,
estimasi hasil dan resource null tetap **Tidak tersedia**. READY selalu ditahan
di lingkungan simulasi. Riwayat sinyal menampilkan versi yang diterima dari API.

## Chart dan lisensi

Lightweight Charts **5.2.0**, dependency exact dengan lockfile, berlisensi Apache-2.0.
Lihat [dokumentasi resmi](https://tradingview.github.io/lightweight-charts/docs/5.2)
dan [NOTICE rilis](https://github.com/tradingview/lightweight-charts/blob/v5.2.0/NOTICE).
Atribusi TradingView, copyright 2025, logo/link dan tautan lisensi tersedia di
halaman. Library merender data yang diberikan; tidak menyediakan feed pasar.

Candle dan histogram volume lot berasal dari riwayat aktual berlabel simulasi.
Garis horizontal menandai entry, stop dan TP; garis vertikal menandai expiry.
Whitespace pada waktu expiry tidak menciptakan harga/volume. Skala harga mencakup
level rencana. Drag horizontal dan pinch zoom didukung, drag vertikal tetap untuk
scroll halaman. Interval 1m/5m/15m hanya meminta riwayat interval tersebut; tidak
mengubah horizon rencana dan tidak mengagregasi/mengisi candle yang hilang.

Proyeksi hanya dirender bila coverage berstatus validated, model/horizon cocok
dengan rencana aktif, serta semua titik berada setelah as_of/riwayat/waktu kini
dan sebelum expiry. Garis median/batas putus-putus, latar ungu dan rentang berisi
warna memisahkannya dari candle. Setiap tingkat coverage yang dikirim digambar
terpisah dan diberi label pada legenda. Pergantian interval, zoom atau expiry
tidak menulis ulang riwayat. Proyeksi yang sudah lewat disembunyikan. Fixture API
saat ini tidak mempunyai proyeksi tervalidasi; screenshot proyeksi memakai mock
simulasi khusus pengujian tampilan, bukan hasil validasi model produksi.

## Snapshot dan kualitas

Detail, chart dan riwayat masing-masing memakai polling 15 detik dan timeout
10 detik. Permintaan interval/reload sebelumnya dibatalkan dan respons terlambat
diabaikan. Gagal refresh menghapus resource lama; retry memakai snapshot baru.
Halaman tidak menggabungkan delta stream. Book berasal dari **satu respons detail
utuh**, termasuk snapshot_id, sequence (string), timestamp, kedua sisi dan lot
kumulatif. Setiap refresh mengganti seluruh book, tanpa mengambil sisi lain dari
snapshot lama. Snapshot dengan simbol, urutan harga, spread atau lot kumulatif
tidak konsisten ditolak. Waktu/umur snapshot terus diperbarui dalam detik.

UI menampilkan paling banyak lima tingkat per sisi; tidak menambah baris saat
feed hanya mengirim satu/kurang dari lima tingkat. Kedalaman terbatas berlabel.
Spread hanya dihitung bila kedua sisi tersedia. Status kualitas/feed dan keadaan
pasar tutup/model belum tervalidasi tetap terlihat. Umur snapshot tidak mengubah
label simulasi menjadi live.

Pressure 1/5/15 menit menampilkan cakupan klasifikasi dan metode, termasuk label
**Estimasi** untuk klasifikasi estimated. Rasio beli/jual hanya muncul bila
validated, cakupan positif, metode tersedia dan kedua rasio konsisten. Flag
validated merupakan pernyataan upstream bahwa validasi termasuk ambang cakupan
telah dipenuhi; UI tidak menetapkan ambang produksi baru. Window yang hilang tetap
tidak tersedia. Ini volume agresor, bukan jumlah investor atau komposisi antrean.

Tipe dan validator runtime detail/chart/history dihasilkan dari kontrak canonical
SS-002 bersama kandidat. Ajv menolak field tambahan/internal, mode selain research,
origin selain simulation serta bentuk tidak valid. Pemeriksaan semantik menolak
scope salah, OHLC tidak konsisten, candle masa depan dan urutan waktu rusak.
Tidak ada perubahan schema wire/API backend.

## Verifikasi dan batas

`npm run check` dan `npm test` pada apps/web memeriksa build produksi dan browser,
termasuk interval/race, expiry, coverage bertingkat, pergantian snapshot, depth lima
tingkat/terbatas, null/error/retry, penolakan payload, metode pressure, pinch/drag,
serta viewport sentuh 360px tanpa overflow. Screenshot:

- [Desktop simulasi](../screenshots/SS-019-desktop.png)
- [Mobile 360px](../screenshots/SS-019-mobile.png)
- [Proyeksi mock simulasi](../screenshots/SS-019-projection.png)

Sumber API aktual tetap fixture TEST, satu candle 1m, satu tingkat book, tanpa
proyeksi atau pressure tervalidasi. 5m/15m kosong. Tidak ada feed vendor, notifikasi
posisi, transaksi atau model produksi baru. G0/G1/G2/G3 tetap memerlukan bukti
terpisah. Sesi fixture loopback tidak menggantikan autentikasi pilot SS-023.
