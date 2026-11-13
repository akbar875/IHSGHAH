# SS-014 — Replay dan simulator eksekusi konservatif

`saham_signal.application.replay.replay` menerima referensi point-in-time SS-009,
jadwal biaya berversi, order limit, serta `Frame` book lengkap. Hasilnya dictionary
JSON yang hanya boleh disimpan sebagai artefak riset. Tidak ada broker, endpoint
bisnis, notifikasi, atau penulisan Fill/Position pengguna di modul ini.

## Input dan integrasi

- Mulai dari posisi simulasi kosong; pembelian simulasi membentuk holdings. Penjualan
  dibatasi holdings sehingga gagal/partial exit menyisakan posisi terbuka.
- `Order`: ID unik, symbol, side, saham, limit IDR, submitted_at dan deadline aware.
  Bracket exit opsional membutuhkan stop dan target; stop tidak memperlebar limit
  minimum jual yang ditetapkan pemanggil.
- `Frame`: ID unik, symbol, event_time, available_at, bids/asks dalam saham dan IDR
  integer, best-first. Sisi kosong adalah likuiditas kosong, bukan fill pada harga
  batas. Book crossed/locked ditolak; stale/tidak synchronized tidak dieksekusi.
- Untuk SS-011, ambil book lengkap sesudah normalisasi/rekonsiliasi snapshot atau
  delta; pertahankan event_time/available_at observasi dan synchronized book.
  Untuk SS-010, replay jurnal berdasarkan available_at, rekonstruksi book dengan
  urutan koneksi/sequence dan recovery adapter sebelum membuat Frame. Jangan memakai
  baris koreksi terbaru seolah sudah tersedia pada waktu aslinya. Modul ini tidak
  menggantikan decoder vendor, pemeriksaan gap, ataupun loader jurnal.
- Low/high opsional hanya untuk candle selesai yang sudah tersedia. Hindari range
  bar yang mencakup waktu sebelum order dibuat. Range memicu exit; volume candle
  tidak dianggap likuiditas yang dapat dieksekusi.
- `FeeSchedule.version` memakai interval efektif dan available_at. Tarif Decimal
  broker beli/jual, levy, pajak jual dan minimum adalah konfigurasi eksplisit,
  **bukan tarif broker/BEI produksi**. Tidak ada fallback jika biaya kosong/ambigu.
- `data_limits` wajib menjelaskan sumber/keterbatasan input; mode hanya research
  atau paper. Seed dicatat; versi ini tidak memakai sampling acak.

## Aturan eksekusi dan laporan

Frame diurutkan berdasarkan availability lalu ID; order berdasarkan submitted_at
lalu ID. Setiap slice melintasi sisi berlawanan book (membayar spread), ditambah
slippage merugikan sejumlah tick. Limit, lot, fraksi, sesi, status instrumen dan
batas harian diperiksa dari referensi yang diketahui saat itu. Latensi berlaku
sebelum memakai book, termasuk setelah trigger bracket. Jika stop dan TP tersentuh
dalam satu range, stop dipilih. Trigger tidak menjamin fill.

Kapasitas level dikurangi queue reserve dan seluruh volume yang sudah dieksekusi
pada symbol/side/harga itu sepanjang replay. Tidak ada inferensi replenishment;
kebijakan ini sengaja konservatif dan dapat menghasilkan banyak unfilled pada
replay panjang. Harga tersentuh tanpa volume tidak mengisi resting order.
Partial fill dibulatkan ke lot. Setiap slice membayar minimum dan biaya yang
dibulatkan ke atas ke 0,01 IDR. Dampak ukuran berasal dari depth yang dikonsumsi,
slippage dan pembatasan kapasitas; bukan model dampak pasar terkalibrasi.

Laporan menyertakan versi model/policy, seed, input/report hash, order input/status,
fill simulasi beserta fee/reference version, snapshot referensi yang digunakan,
jadwal biaya lengkap, keputusan per frame/order, holdings dan net cash flow.
Cash flow bukan profit final jika posisi masih terbuka. Tidak ada auto-liquidation,
mark-to-market, cash sizing atau probabilitas fill. Semua asumsi dan batas model,
ditambah data_limits pemanggil, tertulis di setiap laporan. Simpan input Frame
bersama laporan agar hash dapat diverifikasi dan replay dapat diulang.

## Verifikasi dan gerbang

```powershell
cd services/api
.venv/Scripts/python.exe -m pytest tests/test_replay.py -q
```

Skenario sintetis mencakup ARA tanpa penjual, ARB tanpa pembeli, partial/unfilled,
spread/slippage, latensi, biaya bertanggal, stop sebelum TP, posisi tanpa short,
repeatability, kesehatan book, referensi dan isolasi live. SS-009/010 serta
fondasi simulasi SS-011 sudah tersedia. Issue #11 masih terbuka untuk sampel vendor
berizin; hasil ini tidak memenuhi validasi vendor atau G0/G1. Evaluasi holdout,
biaya/hak data final, dan kalibrasi eksekusi tetap pekerjaan terpisah.
