# Screener bullish dan bearish

Arahan produk 16 November 2026: halaman utama hanya daftar kandidat teknikal,
potensi ke target, harga acuan, take profit dan stop loss. Dashboard simulasi lama
tersedia terpisah di `/simulation`.

`GET /api/research/screener` menggunakan sesi research dan snapshot EOD terverifikasi
yang sama dengan `/api/research/eod`. Tidak memerlukan database atau fixture.
Impor ulang CSV diperlukan agar snapshot lama memiliki indikator tren:

```powershell
$env:PYTHONPATH='services/api/src'
services/api/.venv/Scripts/python.exe -m saham_signal.eod --input .work/idx-stock-features.csv --output .work/free-eod/snapshot.json
```

Gunakan `--download` sebagai pengganti `--input` untuk memperbarui dari penyedia.
Set `EOD_SNAPSHOT_PATH` ke path absolut snapshot pada lingkungan API seperti sebelumnya.

## Aturan v1

- Bullish: close > SMA20 > SMA50 > SMA200, RSI14 50–70, return20 > 0.
- Bearish: close < SMA20 < SMA50 < SMA200, RSI14 30–<50, return20 < 0.
- Volume positif, harga minimal Rp50, rata-rata nilai transaksi 20 hari minimal
  Rp1 miliar. Semua data harus bertanggal sama dengan tanggal terbaru snapshot,
  tidak tertinggal lebih dari 7 hari kalender. Urutan alfabet, tanpa skor probabilitas.
- Bullish: stop = MA20 × 0,99, dibulatkan turun. Bearish: invalidasi = MA20 × 1,01,
  dibulatkan naik. Jarak risiko wajib 1–10% dari harga acuan.
- Target = harga acuan ± 2 × jarak risiko, dibulatkan keluar mengikuti tangga
  fraksi reguler. Karena pembulatan, reward/risk minimal 2. Persentase adalah jarak
  ke target, bukan ramalan return rata-rata atau peluang target tercapai.
- Bearish merupakan peringatan bagi pemegang posisi beli. Target turun dan batas
  invalidasi bukan TP/SL long dan bukan instruksi short selling.

Pendekatan trend MA + momentum RSI mengacu pada dokumentasi publik
[sapatekno/skill-saham](https://github.com/sapatekno/skill-saham). Implementasi ini
mandiri, bukan integrasi atau eksekusi engine lengkap GitHub tersebut. Kode
`core/technical.py` dan `scripts/analyze_asset.py` sudah ditinjau. MACD, ADX, ATR, VCP, dan
verifikasi lintas sumber repo itu belum tersedia dalam snapshot EOD lokal.

Horizon 5–15 sesi merupakan jangka peninjauan, bukan waktu pencapaian target yang
terkalibrasi. Biaya, gap, slippage, suspensi, aksi korporasi serta aturan instrumen
terkini tidak dimodelkan. Harga masuk yang berubah mengharuskan hitung ulang.
Ini skenario research berbasis aturan, belum strategi tervalidasi; studi momentum
sebelumnya tetap G1 NO-GO dan tidak dipakai sebagai bukti kualitas screener ini.
Tidak mengaktifkan alert, posisi, paper live, atau eksekusi broker.
