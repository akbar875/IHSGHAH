# Audit vendor dan hak data SS-008

Tanggal pemeriksaan: **13 November 2026, Asia/Jakarta**. Status: **G0 PENDING**.
Ini audit publik tahap awal. Tidak ada kontrak, kredensial, penawaran, sampel
feed/historis berizin, ataupun hasil uji pasar dalam repo.

## Sumber bukti publik

| ID | Sumber primer | Fakta yang dapat dibuktikan |
|---|---|---|
| E1 | [Layanan Data BEI](https://www.idx.id/id/produk/layanan-data-bei/) | Produk real-time/delayed/EoD/log, direct/indirect, depth lima level; IQ Plus, RTI, Antara, IDXSTI dan ICE tercantum sebagai redistributor. Pengumuman perubahan efektif 1 Januari 2027. Sampel produk indirect diarahkan ke redistributor. |
| E2 | [Katalog BEI 2027](https://www.idx.id/media/zmopzq1r/idx-data-services-catalogue-pricelist-2027_compressed.pdf), halaman cetak 2, 7, 9–10 | Struktur lisensi dan harga indikatif masa depan; bukan penawaran pilot 2026. |
| E3 | [ICE: IDX](https://developer.ice.com/fixed-income-data-services/catalog/indonesia-stock-exchange-idx) | Streaming saham/indeks L1/L2, historis/EoD, timestamp bursa dan ICE, status instrumen/sesi, format native/normalized; klaim MBO perlu validasi entitlement. Angka history sejak Juni 2005 tidak membuktikan ketersediaan historis book per saham sejak tanggal tersebut. |
| E4 | [IQ Plus SCF](https://next.iqplus.info/?act=datafeed) | Feed teks untuk integrasi aplikasi, quote/live trade dan corporate action; rekomendasi dedicated internet 4 Mbps. Disclaimer halaman publik menyebut delay minimal 10 menit serta larangan redistribusi konten situs; bukan bukti entitlement feed berbayar. Kontak marketing@iqplus.info. |
| E5 | [RTI](https://www.rti.co.id/) | Situs menampilkan produk aplikasi/market info; halaman yang ditinjau belum membuktikan spesifikasi feed server. |

Sumber publik adalah bukti penawaran produk, bukan pemberian izin kepada aplikasi
ini. Tautan bisa berubah; catat kembali versi/tanggal dan referensi dokumen privat
saat transaksi. Tidak menyalin kontrak rahasia atau data pasar ke Git.

## Perbandingan kandidat

`Belum terbukti` berarti belum ada bukti untuk akun/paket pilot, bukan klaim bahwa
vendor tidak menyediakan kemampuan itu. Tidak memberi skor nol untuk data hilang.

| Kriteria | IQ Plus SCF (E1/E4) | ICE Feed + History (E1/E3) | RTI (E1/E5) | BEI langsung (E1) |
|---|---|---|---|---|
| Trade/feed | Quote/live trade dipublikasikan | Streaming IDX dipublikasikan | Feed server perlu spesifikasi | Produk langsung tersedia |
| Historis intraday/book | Belum terbukti | Historis ada; resolusi/periode per paket perlu konfirmasi | Belum terbukti | Log/EoD ada; tick/book perlu konfirmasi |
| Depth | Jumlah level/snapshot belum terbukti | L2/MBO diklaim; level aktual perlu konfirmasi | Belum terbukti | Produk depth/ITCH; entitlement perlu konfirmasi |
| Timestamp | Semantik feed belum terbukti | Native exchange + system UTC diklaim | Belum terbukti | Spesifikasi paket diperlukan |
| Sequence/recovery | Belum terbukti | Belum terbukti pada paket pilot | Belum terbukti | Spesifikasi paket diperlukan |
| Heartbeat/SLA numerik | Belum terbukti | Klaim kualitas bukan SLA numerik | Belum terbukti | Kontrak diperlukan |
| Harga all-in pilot | Belum ada penawaran | Belum ada penawaran | Belum ada penawaran | Biaya koneksi dan lisensi perlu dihitung |
| Hasil sampel aktual | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED |

Rekomendasi bersyarat: **IQ Plus lebih dahulu, ICE sebagai pembanding, RTI sebagai
alternatif lokal**. Urutan ini penilaian kebutuhan pilot, bukan peringkat harga
atau kualitas yang sudah diukur. Lihat [ADR-0002](../decisions/0002-market-data-procurement.md).

## Audit hak penggunaan

Semua hak spesifik aplikasi berikut berstatus **UNCONFIRMED** untuk seluruh
kandidat. Daftar redistributor resmi tidak otomatis memberikan hak ke pelanggan.

| Penggunaan yang diminta | Bukti privat yang wajib dirujuk sebelum diaktifkan |
|---|---|
| Ingest/cache dan raw log | Paket, entitlement, lokasi server dan batas koneksi |
| Storage/backup/replay | Durasi retensi, salinan backup, disaster recovery, penghapusan setelah terminasi |
| Non-display/analisis/model | Kategori penggunaan, training, derived data, retensi artefak model |
| Display satu akun | Media web/chart/book, jumlah user/device dan kewajiban pelaporan |
| Notifikasi/hasil turunan | Izin isi alert/sinyal dan penerima; jangan anggap derived data bebas lisensi |
| Redistribusi/API/export | Hak ke pihak lain, ekspor CSV dan penggunaan multi-user; default belum diaktifkan |
| Historis dan aturan efektif | Cakupan delisting, corporate action, koreksi, kalender, versi dan hak simpan |

Simpan kontrak di penyimpanan privat pemilik. Repo cukup memuat ID bukti, issuer,
tanggal dokumen, effective_from/to, ruang lingkup, reviewer dan hasil keputusan;
jangan memasukkan lokasi akses bertoken atau informasi komersial rahasia.

## Biaya dan perubahan lintas tanggal

E2 halaman cetak 2 mencantumkan IDX ITCH Data Prime display, main connection lokal
Rp44.000.000; halaman 7 mencantumkan non-display lokal non-group main connection
kategori 1 Rp11.000.000 dan kategori 2 Rp5.500.000. Halaman 10 menyebut unit/user
L2 Rp32.000 per bulan. Angka-angka ini komponen berbeda, **bukan total biaya
pilot**, bukan harga IQ Plus/RTI/ICE, dan tidak boleh langsung dijumlahkan.
Katalog juga memuat hak aktivitas non-display kategori 1/2 bagi pelanggan display;
minta klasifikasi tertulis agar tidak menghitung lisensi ganda atau mengasumsikan
pengecualian berlaku ke akun ini.

Perubahan produk 2027 mencakup ITCH Prime dan penamaan depth; pemetaan produk
2026 ke 2027 harus dikonfirmasi, tidak cukup mengandalkan nama paket lama.
Kontrak yang melewati **1 Januari 2027** memerlukan verifikasi ulang produk,
harga, klasifikasi penggunaan, user count, dan ketentuan. Tanggal pengumuman,
tanggal efektif kontrak, serta tanggal efektif aturan pasar disimpan terpisah.

Anggaran disetujui saat ini: **belum ada**. Batas pengeluaran sementara Rp0,
tanpa pembelian. Rumus pembanding penawaran: setup + histori/backfill + 12 ×
(feed + lisensi yang benar-benar berlaku + user + koneksi + storage/egress +
dukungan) + pajak/FX. Minta rincian 2026 dan 2027, minimum commitment, pembatalan,
kenaikan harga, batas simbol, koneksi, pesan/detik dan fair-use.

## Penilaian sampel dan gap

Tidak ditemukan sampel feed/historis berizin yang dapat diuji dari sumber primer
yang ditinjau. E1 mengarahkan produk indirect ke redistributor. Pemilik menyatakan
belum memiliki sampel. Hasil **NOT_ASSESSED**, jumlah record **0**, periode
**tidak tersedia**, metrik latensi/gap/duplikasi/depth **tidak tersedia**. Contoh
kontrak simulasi repo bukan sampel vendor dan tidak dihitung sebagai bukti G0.

Gap utama: izin penggunaan/storage, entitlement depth, historis point-in-time,
sequence/recovery, heartbeat, SLA numerik, serta biaya/kapasitas. Belum ada vendor
yang dapat dinyatakan lulus. Ikuti [protokol evaluasi](vendor-evaluation.md) setelah
sampel diterima; hasil gagal maupun tidak lengkap harus tetap tercatat.

## Status acceptance dan gerbang

| Acceptance #8 | Status dan bukti |
|---|---|
| Bukti hak data dan keputusan vendor | Parsial: bukti publik dan shortlist tersedia; kontrak/keputusan final belum ada |
| Sampel feed/historis dinilai, gap dicatat | Gap tercatat; pengukuran sampel belum dapat dilakukan |
| Aturan lintas tanggal/pembaruan kontrak ditinjau | Selesai pada audit ini; implementasi aturan efektif tetap SS-009 |
| G0 pending saat bukti belum cukup | Terpenuhi: **PENDING** |

Pemilik repo menindaklanjuti penawaran, izin/sampel dan anggaran; maintainer data
mengevaluasi sampel; pemilik menyetujui pilihan akhir. Issue #8 belum memenuhi
seluruh acceptance dan tidak boleh ditandai selesai hanya karena audit di-push.
SS-008 sampai SS-012 tetap harus memberikan bukti G0 bersama sebelum promosi.
