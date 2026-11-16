# Daftar dan detail saham dengan data gratis

Arahan 17 November 2026: daftar ringkas yang dapat dipilih, detail order book,
antrean, chart dengan waktu/warna, serta target backtest **1.000 transaksi
historis**. Pengguna memilih data gratis karena belum memiliki API/feed broker.

Ticker menautkan ke `/stocks/<symbol>?source=daily`. Detail simulasi lama tetap
terpisah. Daftar/detail memeriksa snapshot setiap 15 detik, mencegah request
bertumpuk, berhenti saat tab tersembunyi, dan menghapus data saat gagal. Ini
pembaruan snapshot EOD, **bukan real time bursa**.

`GET /api/research/stocks/{symbol}` memerlukan sesi research, menolak query dan
mengembalikan 404 untuk simbol yang tidak ada. Import menyimpan maksimal 253
penutupan/volume historis per ticker dan laporan replay dari seluruh sumber.
Snapshot lama masih terbaca tetapi harus diimpor ulang untuk chart/backtest.
Batas snapshot 16 MiB. Respons EOD daftar menghilangkan riwayat/laporan besar.

Waktu chart berupa tanggal EOD WIB, tanpa jam transaksi fiktif. Chart harga
memakai biru untuk penutupan, abu-abu volume, hijau target, merah stop. Chart
backtest memakai ungu untuk indeks hasil (awal 100), hijau/merah untuk transaksi
positif/negatif. Crosshair/tabel menunjukkan tanggal entry/exit dan hasil.

## Replay `ma-rsi-close-replay-v1`

Replay kronologis long-only memakai filter bullish screener pada tanggal sinyal.
Entry hipotetis di close sesi berikutnya bila volume positif dan harga masih
di antara stop/target sinyal. Satu posisi per ticker, tanpa overlap. Return
sesudah entry memakai `ret_1d` adjusted penyedia. Exit di close pertama yang
melewati level relatif stop/target, atau setelah 15 sesi. Gap stop memakai hasil
close yang sebenarnya, bukan fill tepat pada stop.

Asumsi biaya beli 0,15%, jual 0,25%, slippage 0,10% per sisi. Net multiple:
`gross × (1 − sell_fee − slippage) / (1 + buy_fee + slippage)`.
Indeks hasil dikompaun, drawdown juga mengamati mark-to-market selama posisi.
Belum sizing lot atau Fill nyata.

Maksimal 1.000 transaksi selesai per ticker dipilih kronologis tanpa pengulangan.
Kekurangan sampel tidak dipenuhi dengan resampling atau transaksi palsu. Posisi
terbuka tidak dihitung selesai. Record ditolak, return hilang/ekstrem, jeda >7
hari atau volume nol saat posisi terbuka menghentikan replay dan menahan metrik
ringkasan. Transaksi sebelumnya tetap tersedia sebagai catatan parsial bergap.

Ini eksplorasi **in-sample**, belum holdout. Universe/delisting, waktu ketersediaan
fitur dan aksi korporasi penyedia belum diaudit. OHLC/touch intraday, antrean,
suspensi, lot, spread, market impact dan aturan historis belum dimodelkan. Hasil
masa lalu bukan probabilitas arah mendatang. Studi momentum sebelumnya tetap G1
NO-GO. Pada saham bearish, laporan tetap menguji beli historis, bukan short selling.

## Sumber dan deployment

Sumber EOD tidak memuat depth. Respons mengembalikan `order_book=null`,
`individual_queue=null`, `depth_status=feed_not_connected`. Real time dan antrean
memerlukan feed terpisah; posisi antrean individual perlu dukungan penyedia.

```powershell
$env:PYTHONPATH='services/api/src'
services/api/.venv/Scripts/python.exe -m saham_signal.eod --input .work/idx-stock-features.csv --output .work/free-eod/snapshot.json
```

Gunakan `--download` menggantikan `--input` untuk sumber terbaru. Pada deployment,
sediakan snapshot di `EOD_SNAPSHOT_PATH` dan sesi research sesuai panduan keamanan.
File `.work` lokal tidak otomatis ikut Git/Vercel.
