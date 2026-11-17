# Data gratis yang dipakai aplikasi — riset harian

Keputusan pemilik: gunakan sumber gratis yang kualitasnya dapat diperiksa.
Integrasi aktif memakai **Aethereal IDX Stock Features**, melalui CSV tetap
`https://dataset.aethereal.top/files/idx-stock-features.csv`. Halaman sumber
[IDX Stock Features](https://dataset.aethereal.top/datasets/idx-stock-features)
mencantumkan **CC BY 4.0**, pembaruan harian dan fitur berbasis data sampai tanggal
masing-masing. Aplikasi menampilkan atribusi, tautan sumber/lisensi dan tanggal data.
Lisensi publisher bukan verifikasi hak upstream atau kelulusan G0 intraday.

Ini tambahan halaman `/research` dengan **data pasar harian asli**. Dashboard
intraday/fixture, pipeline paper dan gerbang G0/G1 tidak diganti menjadi live.
Tidak ada ranking rekomendasi, probabilitas profit, entry/stop/TP atau auto-fill
dari data harian. Return satu hari adalah adjusted return yang dihitung penyedia,
bukan ramalan perubahan esok hari. RSI juga indikator penyedia, belum hasil
validasi model kita.

## Pemilihan dan pemeriksaan sumber

- Gratis tanpa akun, API key, kartu kredit, trial atau upgrade otomatis.
- Schema 19 kolom diperiksa, termasuk identitas/date, nilai finite, harga/volume,
  rentang RSI/correlation/drawdown, volume integer dan konsistensi close × volume.
- Duplikat membatalkan kedua record; out-of-order/future/invalid ditolak. Bila
  record terbaru ticker gagal, ticker dikeluarkan dan tidak diganti baris lama
  seolah-olah data terbaru. Indikator kosong tetap null, volume nol tetap nol.
- Snapshot hanya memublikasikan record terakhir per ticker, urutan alfabet.
  Tidak mengubah actual fill, signal history, alert atau ukuran posisi.
- Hash file sumber, waktu observasi/import, statistik karantina dan hash snapshot
  disimpan. available_at tidak dibalik menjadi tanggal historis baris sehingga
  file ini tidak berpura-pura menjadi jurnal point-in-time masa lalu.

Hasil unduhan aktual dan pemeriksaan API ada pada
[laporan integrasi](../../research/reports/free-daily-integration.md).
Pemeriksaan struktur/konsistensi tidak membuktikan setiap harga benar terhadap
bursa. Universe publisher memakai pilihan saham masa kini; historis delisting,
aturan dan corporate action belum tervalidasi untuk klaim backtest produk.

## Kolektor dan cache

Collector operator hanya mengunduh dari satu HTTPS URL tetap, tidak menerima URL
request/user, tidak mengirim credential dan menolak redirect. Batas sumber 64 MiB,
socket timeout 30 detik, anggaran transfer 90 detik. Tidak ada polling startup,
retry tanpa batas atau download pada setiap request browser.

Unduhan divalidasi sebelum publikasi. Penulisan temp + fsync + replace atomik
mempertahankan snapshot lama jika download/validasi gagal; temp unduhan dibersihkan.
Raw CSV dan snapshot lokal tetap di `.work`, tidak di Git. `--input` tersedia
untuk import salinan provider yang sudah diunduh: operator bertanggung jawab atas
asal file, sedangkan SHA hanya membuktikan integritas, bukan otorisasi sumber.

Endpoint `GET /api/research/eod` memerlukan sesi admin research bertanda tangan,
path snapshot hanya dari konfigurasi server, tidak menerima query path/account.
Paper/live menolak konfigurasi EOD saat startup. Data kosong, korup, hash salah,
masa depan, path tidak tersedia atau file >16 MiB memberi 503 tanpa fallback
fixture. Respons private/no-store dan tidak bergantung pada feed vendor, broker
atau database posisi. Readiness keseluruhan API tetap memerlukan PostgreSQL/Redis.

Stale harian adalah **lebih dari 7 hari kalender** berdasarkan tanggal baris atau
umur snapshot. Ini ambang tampilan research, bukan SLA bursa atau izin entry.
Tanggal setiap ticker selalu terlihat. Browser menghapus data lama saat retry
atau error, memvalidasi metadata, dan tidak mengganti null dengan angka buatan.

## Menjalankan lokal

Dari `services/api` dengan environment backend terkunci:

```sh
uv run --locked python -m saham_signal.eod --download --output ../../.work/eod/snapshot.json
```

Set `EOD_SNAPSHOT_PATH` ke **path absolut** file tersebut pada konfigurasi API
research. Siapkan SESSION_SECRET dan PILOT_ACCOUNT_ID serta sesi admin mengikuti
[panduan keamanan](../SECURITY.md). Jalankan API seperti biasa. Tidak diperlukan
MARKET_FIXTURE_ENABLED untuk endpoint data harian.

Pada web, gunakan `NEXT_PUBLIC_API_BASE_URL` yang menunjuk service research.
Misalnya `http://127.0.0.1:8000/api/v1` bila web dibuka pada hostname `127.0.0.1`;
gunakan hostname yang sama agar cookie SameSite bekerja. Buka `/research` atau
tautan **Data harian**. Jika halaman menunjukkan sesi belum aktif, buka **Akses
research** (`/access`) dan masukkan nilai token `v1.…` yang diterbitkan administrator
melalui `python -m saham_signal.application.security` (tanpa awalan `saham_session=`
dan atribut cookie). Origin web harus tercantum di `CORS_ORIGINS`. Setelah aktivasi,
daftar saham dimuat kembali. Klik kode saham di daftar kandidat atau data harian
untuk membuka chart dan backtest. Kandidat kosong berbeda dari data gagal dimuat:
snapshot bisa tersedia tanpa saham yang memenuhi filter tren.

Tombol muat ulang hanya membaca cache; jalankan ulang
collector secara eksplisit untuk memperbarui data. Tidak ada automation baru.

## Kandidat intraday gratis

[IDX Edge PRO](https://stock.arjum.com/api-docs) mendokumentasikan kuota gratis
1.000 request/hari dan chart intraday. Probe publik mendapati `/api/health` 200
dan `/api/price/BBCA` 401 tanpa key. API key/login belum tersedia; data, latensi,
historis book, sequence/recovery dan izin aplikasi belum dapat diuji. Tidak ada
login, akun, pembelian atau bypass autentikasi yang dilakukan. Kandidat ini belum
diaktifkan dan tidak dipakai sebagai fallback diam-diam.

G0 intraday tetap pending/NO-GO dan G1 tetap no-go sampai bukti yang sesuai PRD
tersedia. Sumber EOD gratis ini membuat riset harian benar-benar dapat digunakan,
tanpa menyatakan akurasi prediksi intraday sudah terbukti.
