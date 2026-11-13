# Permintaan penawaran dan evaluasi sampel

Untuk [issue #8](https://github.com/akbar875/IHSGHAH/issues/8), mengikuti
[ADR-0002](../decisions/0002-market-data-procurement.md) dan [audit](vendor-audit.md).
Dokumen ini draf siap digunakan; belum dikirim ke vendor.

## Permintaan ke kandidat

Tujuan: aplikasi riset/paper saham BEI intraday, satu akun pribadi, maksimal 20
saham biasa pasar reguler; server melakukan analisis dan browser menampilkan
harga/chart/book serta alert in-app. Tidak ada eksekusi broker otomatis. Mohon
konfirmasi tertulis untuk penggunaan ini, termasuk lisensi yang berlaku sebelum
dan sesudah 1 Januari 2027.

1. Berikan paket trade, book minimal lima level, status instrumen/sesi, kalender,
   fraksi/batas harga dan corporate action. Jelaskan unit harga/volume/lot, raw
   vs adjusted, identitas instrumen dan cakupan delisting.
2. Berikan spesifikasi timestamp event/provider, zona/precision, sequence dan
   scope/reset-nya, heartbeat, snapshot/delta, koreksi/cancel, recovery/replay,
   reconnect serta dokumentasi schema berversi. Apakah transport terenkripsi?
3. Berikan sampel berizin minimal 10 sesi penuh trade/book untuk universe uji,
   termasuk pembukaan/penutupan dan skenario gap/reconnect; tawarkan historis
   awal 12 bulan tick/book dan candle 1m. Jika tidak tersedia, nyatakan batas
   cakupan/periode dan izin uji/storage. Berikan checksum/manifes dan versi schema.
4. Konfirmasi hak cache, raw storage, backup, retensi, replay, analisis/training,
   output turunan, display satu akun, alert, ekspor dan redistribusi. Jelaskan
   kewajiban setelah kontrak berakhir dan batas lokasi server/cloud/DR.
5. Berikan SLA uptime/latensi, jam dukungan, pemberitahuan outage/perubahan,
   kapasitas simbol/pesan/koneksi, throttling, dan prosedur recovery/backfill.
6. Pisahkan harga setup, feed, historis, lisensi, user, koneksi, pajak, dukungan,
   minimum commitment dan biaya terminasi; jelaskan tarif/tanggal efektif 2027.
   Nyatakan legal entity yang dapat berlangganan dan apakah pilot pribadi diterima.

Kontak publik awal IQ Plus: marketing@iqplus.info ([produk](https://next.iqplus.info/?act=datafeed)).
Pembanding ICE: [form kontak dari halaman produk IDX](https://developer.ice.com/fixed-income-data-services/catalog/indonesia-stock-exchange-idx).
Alternatif RTI: [situs resmi](https://www.rti.co.id/).
Pencarian vendor bukan persetujuan pembelian atau pengiriman pesan keluar.

## Prosedur evaluasi yang harus direkam

1. Verifikasi izin evaluasi dan retensi terlebih dahulu. Simpan sampel serta
   kontrak di storage privat; gunakan ID bukti dan checksum di laporan repo.
2. Catat vendor/paket, versi schema, waktu penerimaan UTC, rentang event,
   jumlah record per tipe/simbol/sesi, aturan efektif, serta semua interval hilang.
3. Petakan field ke kontrak SS-002. Bedakan event_time, provider_time,
   received_at lokal, available_at dan processed_at. Jangan mengisi waktu ingest
   historis dengan event_time. Tanpa waktu ketersediaan yang terbukti, nyatakan
   keterbatasan point-in-time dan jangan klaim backtest bebas look-ahead.
4. Hitung jumlah/persentase null, duplikat, out-of-order, sequence gap dan
   koreksi; dokumentasikan denominator dan scope/reset sequence. Rekonstruksi
   snapshot/delta menurut spesifikasi vendor, bandingkan checksum/total bila ada.
   Ulangi ingest untuk membuktikan hasil idempoten dan replay deterministik.
5. Periksa unit lot/harga, depth aktual, crossed/invalid book menurut fase pasar,
   status suspensi, candle hasil agregasi trade, penyesuaian corporate action dan
   saham sepi dengan heartbeat sehat. Jangan menganggap tidak ada trade sebagai
   feed putus. Record invalid dikarantina, tidak diam-diam dibuang.
6. Uji koneksi putus, delta hilang/duplikat, sequence reset, snapshot kedaluwarsa
   dan koreksi; entry ditahan sampai snapshot konsisten. Gunakan gangguan
   terkontrol di research, bukan pada feed produksi vendor.
7. Ukur provider lag hanya jika timestamp/clock memungkinkan, dan ukur latensi
   internal terpisah. Arsip historis tanpa received_at tidak dapat mengukur SLA
   live. Untuk p95 end-to-end gunakan instrumentasi API/UI saat integrasi SS-011/012
   dan beban 20 simbol; catat hardware, throughput dan jumlah observasi.
8. Isi laporan di bawah. Evaluasi teknis awal bukan kelulusan G0; bukti hak,
   biaya, aturan dan hasil SS-009 sampai SS-012 tetap diperiksa bersama.

## Format laporan hasil berikutnya

| Field | Isi wajib |
|---|---|
| Identitas | Vendor, produk, reviewer, tanggal, schema/kontrak/code version |
| Bukti | ID izin privat, effective_from/to, checksum/manifes sampel |
| Cakupan | Simbol/board, sesi/periode, record per tipe, depth min/max, histori tersedia |
| Kualitas | Null, duplikat, out-of-order, gap sebelum/sesudah recovery; numerator/denominator |
| Waktu | Timestamp mapping, precision, clock skew, provider lag dan latensi internal p50/p95/p99 |
| Recovery | Setiap skenario, hasil aktual, snapshot/cursor dan batas kehilangan |
| Hak/biaya | Matrix izin dengan ID bukti, penawaran all-in dan budget disetujui |
| Kesimpulan | PASS/FAIL/NOT_ASSESSED per kriteria, gap, pemilik, tindakan dan evaluasi ulang |

Untuk setiap bukti yang tidak tersedia gunakan NOT_ASSESSED, bukan PASS atau nol.
Kriteria kualitas awal tercantum pada ADR; perubahan ambang harus diberi alasan
sebelum evaluasi diulang. Hanya pemilik dapat menyetujui biaya dan keputusan
pengadaan; laporan ini tidak memesan layanan.
