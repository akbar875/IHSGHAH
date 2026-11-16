# Integrasi sumber gratis — 16 November 2026

Pemilik memilih sumber gratis. **Aethereal IDX Stock Features (CC BY 4.0)** dipakai
untuk halaman riset harian; file raw IDX Stock Prices sebelumnya tetap hanya bahan
audit/evaluasi. [Halaman sumber](https://dataset.aethereal.top/datasets/idx-stock-features)
menyebut pembaruan harian dan atribusi. Tidak ada biaya vendor, akun, API key,
langganan atau model/rilis yang dipromosikan.

## Bukti unduhan dan kualitas aktual

[Receipt import](free-daily-import.json) dihasilkan collector dari unduhan HTTPS
aktual, bukan fixture. Source CSV 47.128.462 byte, SHA-256
`08f7326196a7b9b3a8c4740a040997ec46e01cf4374d72e261594f8723a87347`.

| Pemeriksaan | Hasil |
|---|---:|
| Record diperiksa / diterima | 303.743 / 303.743 |
| Record ditolak menurut aturan importer | 0 |
| Ticker aktual yang dipublikasikan | 114 |
| Tanggal terakhir | 2026-11-13 |
| Record volume nol | 16.428 |

Publisher menyebut 120 saham; aplikasi menampilkan 114 ticker yang benar-benar
tersedia, tanpa mengarang sisanya. Pemeriksaan meliputi schema, tanggal/identitas,
angka finite, harga/volume, rentang indikator, serta close × volume. Nol rejected
bukan klaim bahwa seluruh harga benar terhadap bursa atau indikator sudah
divalidasi independen.

[Cross-check](free-daily-crosscheck.json) membandingkan date/close/volume terakhir
untuk 114 ticker terhadap unduhan IDX Stock Prices yang sudah diaudit sebelumnya:
**114 cocok, 0 berbeda**, toleransi close 0,0001 IDR untuk presisi ekspor.
Kedua file berasal dari publisher yang sama; ini uji konsistensi lintas dataset,
bukan pembandingan independen dengan data resmi bursa.

## Integrasi aplikasi

[Uji endpoint dengan dataset aktual](free-daily-api-check.json) menjalankan
`GET /api/research/eod` melalui ASGI TestClient dan sesi admin research: tanpa sesi
401, dengan sesi 200 dan 114 ticker, origin market/frequency daily. API tidak
membutuhkan fixture market aktif dan tidak membaca/mengubah ledger/alert.

Halaman `/research` menampilkan tanggal data/import, atribusi CC BY 4.0, close,
adjusted return satu hari, volume dan RSI penyedia. Pencarian ticker aktif;
stale >7 hari kalender diberi label. Error/hash invalid menahan respons dan
menghapus angka lama pada browser; tidak ada fallback ke angka simulasi.

Tes otomatis memakai nilai sintetis terpisah untuk kasus rusak, duplikat,
karantina latest, null/volume nol, future/stale, auth, oversized download,
mode isolation dan tampilan 360px. Screenshot layout memakai **fixture sintetis**:
[mobile](../../docs/screenshots/free-eod-mobile.png) dan
[desktop](../../docs/screenshots/free-eod-desktop.png).
CI tetap memakai fixture deterministik; unduhan publik tidak menjadi dependency CI.

## Kandidat intraday dan batas

Probe publik IDX Edge PRO menghasilkan health 200 dan price/BBCA 401 tanpa API
key. Dokumennya mengiklankan paket gratis; akses data, latensi, book/recovery dan
hak aplikasi belum diuji sehingga belum dipasang. Tidak ada upaya melewati login.

Integrasi ini memberi penggunaan nyata data gratis untuk **riset harian**.
G0 intraday tetap pending/NO-GO, G1 belum lulus, paper live tetap disabled.
Probabilitas profit dan kemampuan prediksi intraday tidak disimpulkan dari
kualitas struktur CSV, kecocokan harga, indikator RSI atau kelulusan tes software.
