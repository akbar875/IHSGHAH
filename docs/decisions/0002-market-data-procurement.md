# ADR-0002: Pengadaan data pasar dan batas pilot G0

- Status: Proposed — keputusan pengadaan final menunggu bukti dan persetujuan anggaran
- Tanggal: 2026-11-13 (Asia/Jakarta)
- Issue: [#8 / SS-008](https://github.com/akbar875/IHSGHAH/issues/8)
- Pengambil keputusan: pemilik repo
- Dependency: ADR-0001 Accepted, issue #1 closed; tersedia pada main
- Bukti: [audit vendor dan hak data](../market-data/vendor-audit.md)
- Prosedur lanjutan: [permintaan penawaran dan evaluasi sampel](../market-data/vendor-evaluation.md)

## Konteks

Belum ada vendor, sampel berizin, atau anggaran data. Pemilik repo mengonfirmasi
kondisi ini pada 13 November 2026 dan meminta pencarian vendor. Audit publik dapat
menyaring kandidat, tetapi tidak mengonfirmasi entitlement akun, hak penyimpanan,
SLA kontraktual, maupun kualitas feed aktual. G0 tetap **PENDING**.

## Rekomendasi keputusan

1. Prioritaskan permintaan penawaran **IQ Plus SCF** untuk jalur lokal. Alasannya
   adalah produk integrasi aplikasi yang dipublikasikan serta status redistributor
   dalam daftar BEI; ini penilaian kecocokan awal, bukan bukti vendor termurah.
2. Bandingkan dengan **ICE Consolidated Feed + History** untuk kebutuhan replay
   dan metadata. Gunakan **RTI Infokom** sebagai alternatif lokal bila IQ Plus
   tidak memenuhi depth, historis, recovery, atau izin. Pilihan final hanya dibuat
   sesudah jawaban tertulis dan sampel dinilai dengan prosedur yang sama.
3. Tunda koneksi langsung BEI. Pilot satu akun belum membuktikan kebutuhan biaya
   jaringan dan operasi koneksi langsung. Jangan memakai halaman harga publik,
   endpoint aplikasi konsumen, atau scraping sebagai pengganti feed berizin.
4. Bekukan pengeluaran berbayar pada **Rp0 sampai anggaran disetujui**. Ini batas
   otorisasi saat ini, bukan estimasi harga vendor atau keputusan bahwa data gratis
   mencukupi. Minta total biaya tahun pertama dan biaya berulang menurut checklist.
5. Tidak ada fallback otomatis antarvendor. Perbedaan timestamp, unit, sequence,
   corporate action dan kedalaman harus direkonsiliasi lebih dahulu pada SS-011.

## Universe pilot yang diusulkan

Satu akun pribadi, paling banyak 20 saham biasa pasar reguler pada awal evaluasi;
tanpa derivatif, waran, ETF, papan/mekanisme khusus, atau saham tersuspensi.
Jumlah 20 adalah batas beban awal yang diusulkan, bukan entitlement vendor.

Manifest universe berversi harus memuat identitas instrumen, board, alasan inklusi,
effective_from/to, dan sumber aturan. Pilih saham dari peringkat median nilai
transaksi 60 sesi sebelumnya yang tersedia saat tanggal pemilihan, setelah filter
kelayakan SS-009. Jangan menetapkan ticker hari ini sebagai universe seluruh
backtest; sertakan saham keluar/delisting pada dataset historis bila memenuhi
aturan saat itu. Jika data pemilihan belum lengkap, universe belum dapat diaktifkan.

## Kriteria kualitas yang diusulkan

- Feed trade dan book minimal lima level, status instrumen/sesi, heartbeat, serta
  snapshot konsisten dan cara recovery gap wajib tersedia untuk fitur terkait.
- Semua timestamp dipetakan ke UTC; event_time dan received_at dapat dilacak.
  provider_time/sequence yang tidak tersedia dicatat sebagai gap, tidak direka.
  available_at hasil ingest dan processed_at dibentuk oleh sistem kita.
- Reconnect harus menghasilkan snapshot baru sebelum delta diterapkan. Tidak ada
  gap tak terselesaikan, book campuran versi, atau duplikasi setelah normalisasi
  pada dataset evaluasi yang diterima. Kegagalan dikarantina dan menghalangi entry.
- Target internal PRD: p95 received_at ke tampilan <=2 detik; evaluasi sinyal tiap
  5 detik; heartbeat/gap >10 detik menahan entry sampai resinkronisasi. Ambang ini
  belum merupakan SLA vendor. Feed dengan heartbeat lebih jarang perlu keputusan
  ulang, bukan otomatis dianggap sehat dengan ambang yang tidak cocok.
- Provider lag diukur terpisah dari latensi internal. Feed delayed tidak mendukung
  entry real-time. Tanpa bukti antrean/fill, probabilitas fill tetap null.
- Uji minimal 10 sesi utuh untuk evaluasi teknis awal, termasuk pembukaan,
  penutupan dan recovery terkontrol; ini tidak menggantikan observasi G2.
  Histori awal yang diminta: 12 bulan trade/book dan candle 1m, termasuk koreksi
  dan aturan efektif. Kekurangan periode/granularitas dicatat dan membatasi riset.

## Alternatif dan konsekuensi

| Alternatif | Pertimbangan |
|---|---|
| IQ Plus lokal | Jalur permintaan pertama; depth/historis/sequence dan harga belum terbukti |
| ICE | Dokumentasi publik metadata lebih rinci; hak, biaya dan cakupan aktual masih perlu penawaran |
| RTI | Alternatif resmi; aplikasi konsumen tidak membuktikan hak feed server |
| BEI langsung | Sumber otoritatif; biaya dan operasi koneksi belum sesuai bukti kebutuhan pilot |
| EoD/delayed | Bisa dievaluasi untuk riset yang diizinkan; tidak memenuhi entry intraday real-time |

Belum ada pembelian, komunikasi vendor, integrasi SDK, atau perubahan runtime.
SS-009/010 boleh menyiapkan desain/fixture, tetapi akses data nyata dan kelulusan
G0 tidak boleh disimpulkan dari selesainya audit dokumentasi ini.

## Tinjau ulang

Tinjau sebelum kontrak ditandatangani, sebelum 1 Januari 2027, saat produk/biaya
atau ketentuan berubah, universe melebihi 20 saham, distribusi bertambah, atau
kebutuhan retensi/model berubah. Catat tanggal berlaku lisensi dan aturan secara
terpisah; jangan menerapkan katalog 2027 sebagai kontrak aktif 2026.

ADR tetap Proposed sampai pemilik menerima rekomendasi dan batas anggaran, serta
hasil pengadaan dilengkapi. Penerimaan ADR sendiri tidak meluluskan G0.
