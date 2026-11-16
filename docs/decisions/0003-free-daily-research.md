# ADR-0003: Scope harian dengan anggaran data Rp0

- Status: Accepted untuk perubahan scope oleh pemilik pada 16 November 2026.
- Terkait: #26; menggantikan target intraday untuk pekerjaan riset berikutnya.

Pemilik memilih **ubah scope menjadi harian dan jalankan validasinya** setelah
perbedaan kebutuhan trade/book intraday dengan ketersediaan data gratis dijelaskan.
Sumber awal tetap Aethereal IDX Stock Features, CC BY 4.0 dengan atribusi. Tidak ada
langganan, akun baru atau biaya. Implementasi intraday lama tetap sebagai simulasi.

Riset baru menilai baseline long-only harian dengan holding lima sesi dan jeda
satu sesi sebelum entry. Ini memperbolehkan posisi overnight dalam eksperimen
harian, menggantikan default intraday tanpa overnight hanya untuk scope baru ini.
Protokol `research/protocols/daily-free-v1.json` dibekukan dalam commit sebelum
eksekusi. Baseline tidak dilatih atau dipilih berdasarkan hasil holdout; champion
momentum20 ditentukan sebelumnya. Semua pembanding wajib dilaporkan.

G0 harian harus memisahkan kelayakan file untuk riset offline dari bukti data
point-in-time, universe historis dan hak rilis. G1 harian memerlukan expectancy
bersih dengan interval dependensi waktu, batas risiko, diversifikasi, kalibrasi,
dan asumsi eksekusi yang dapat dibuktikan. Kelulusan tes kode bukan kelulusan model.
Hasil FAIL/NOT_ASSESSED tetap menahan paper dengan kualitas sinyal. Persetujuan
scope bukan persetujuan hasil profit, broker fee, atau promosi model.

Retur adjusted penyedia, universe saham yang dipilih sekarang, tidak adanya
jurnal publikasi historis, dan asumsi fractional/full fill membatasi studi ini.
Studi tidak merekayasa trade/order book, lot, suspensi, antrean, aturan historis,
dividen, atau fill aktual dari candle/indikator. Raw data tetap privat di `.work`.
Tidak ada perubahan otomatis pada gerbang intraday, ledger paper/actual atau alert.
