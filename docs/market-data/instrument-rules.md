# Referensi instrumen point-in-time (SS-009)

Implementasi backend berada di `domain/instruments.py`, application service
`application/instruments.py`, dan adapter `adapters/instrument_references.py`.
API, worker, dan replay dapat memakai service yang sama; belum ada endpoint bisnis
atau ingest vendor. Penyimpanan persisten/migrasi merupakan SS-010.

## Sumber dan batas verifikasi

Diperiksa pada **13 November 2026, Asia/Jakarta**:

- [BEI: jam dan mekanisme perdagangan](https://www.idx.id/id/produk-layanan/jam-dan-mekanisme-perdagangan/)
  merujuk Kep-00158/BEI/10-2026. Halaman menjelaskan lot reguler 100 saham,
  fraksi berdasarkan kelompok harga, sesi Jumat yang berbeda, dan mekanisme
  lelang yang terpisah. Fraksi harian menggunakan harga referensi hari tersebut,
  bukan berganti setiap kali harga order melintasi kelompok harga.
- [BEI: pengumuman](https://www.idx.id/id/berita/pengumuman/) merupakan jalur
  verifikasi kalender, suspensi/pembukaan kembali dan tindakan korporasi.
  [Pengumuman KSEI kalender 2026](https://web.ksei.co.id/files/Pengumuman_Hari_Libur_dan_Cuti_Bersama_PT_KSEI_Tahun_2026.pdf)
  juga merujuk pengumuman kalender BEI Peng-00171/BEI.POP/09-2025.

Halaman ringkasan yang bisa berubah bukan arsip lengkap aturan historis maupun
master instrumen/status harian. Implementasi **tidak memasang dataset produksi**
atau menyimpulkan tanggal efektif dari tanggal akses. Adapter kosong menolak entry.
Semua data pengujian adalah `simulation`, dengan simbol `SIM`; bukan salinan feed.
Pengadaan sumber berizin, cakupan dan verifikasi harian tetap mengikuti SS-008/G0.

## Semantik lookup

Setiap rule, hari kalender, snapshot status/aksi korporasi, dan batas harga memiliki
`Version`: ID, sumber, origin, interval efektif wajib berakhir, serta `available_at`.
Waktu wajib timezone-aware. Interval menggunakan `[effective_from, effective_to)`;
data tersedia ketika `available_at <= known_at`. Pemanggil mengirim waktu evaluasi
`at` dan cutoff pengetahuan `known_at <= at`. Tidak memakai clock saat ini.
Tanggal sesi dan batas harian berasal dari konversi `at` ke **Asia/Jakarta (UTC+7)**.
Offset tetap WIB dipakai agar tidak menambah dependency tzdata pada Windows.

Lookup memerlukan tepat satu versi yang berlaku dan diketahui untuk setiap komponen.
Tidak ada fallback ke versi terbaru, kalender weekday, atau status active secara
implisit. Data terlambat tidak bocor ke replay. Gap, duplikat/overlap, ID limit yang
tidak cocok, maupun data repository untuk simbol/pasar/tanggal lain ditolak.
Koreksi harus memiliki interval efektif yang tidak ambigu dalam snapshot repository
untuk cutoff terkait; resolver tidak memilih pemenang overlap secara diam-diam.
SS-010 perlu menyimpan riwayat revisi agar snapshot lama tetap dapat direkonstruksi.

`ReferenceRepository` adalah interface; `MemoryReferences` merupakan implementasi
immutable untuk integrasi lokal/pengujian. Tidak membaca file fixture saat startup
dan tidak mengaktifkan feed/alert. Hasil sesudah lookup memuat empat ID versi untuk
audit dan reproduksi.

## Aturan entry

`check_entry` memeriksa kelayakan referensi saja. Hasil `allowed=True` **bukan**
izin trading live, sinyal READY, atau kelulusan gerbang data/risiko/likuiditas.
Pemanggil tetap wajib menjalankan gate mode, data, risiko dan keamanan terkait.

- Cakupan awal: saham board `main`, `development`, `new_economy`, pasar `regular`.
  Board/pasar lain dan sesi selain `continuous` ditolak, termasuk call auction.
- Kalender berupa tanggal eksplisit dengan sesi lokal `[opens, closes)` yang
  berurutan tanpa overlap. Sesi kosong berarti libur/tutup; tanggal hilang berarti
  referensi tidak tersedia. Importer wajib menormalisasi presisi akhir sesi dari
  sumber dan membawa perubahan jadwal/penutupan darurat sebagai versi baru.
- Snapshot `TradingState` mencakup status lengkap dan daftar aksi korporasi
  beridentitas, bertipe, bertanggal ex-date dan bersumber. Suspended/delisted/unknown
  ditolak. `actions_resolved=False` menahan entry sampai implikasi aksi diselesaikan
  dan rule/lot/harga referensi diperbarui dari sumber otoritatif. Daftar kosong
  menyatakan snapshot lengkap tanpa aksi, bukan hasil menganggap event hilang nihil.
  Jenis awal: split, reverse_split, cash_dividend, rights, bonus; jenis lain ditolak
  meskipun diberi tanda resolved. Penyelesaian berarti referensi sudah direkonsiliasi,
  bukan perhitungan penyesuaian harga/posisi otomatis oleh service ini.
- Harga dan saham berupa integer positif; saham harus kelipatan lot versi aktif.
  Band fraksi half-open, berurutan, tanpa celah. Step dipilih dari harga referensi
  harian; harga order harus kelipatan step tersebut.
- `DailyLimits` membawa harga referensi serta batas bawah/atas absolut IDR dan
  `rule_id`, tanggal, sumber/versi. Batas inklusif. Tidak menghitung persentase,
  pembulatan ARA/ARB, harga teoretis ex-action atau pengecualian IPO secara tebakan.
  Importer harus memasok hasil otoritatif yang sudah diverifikasi; jika tidak,
  snapshot tidak lengkap dan entry ditolak. Perubahan limit intraday dapat
  menggunakan interval efektif tersendiri tanpa mengubah histori.
- Referensi simulasi tidak lolos pemeriksaan mode `live`. Origin `licensed` hanya
  boleh diisi adapter yang telah lolos verifikasi hak dan kualitas data; atribut
  tersebut sendiri tidak membuktikan G0.

Input pemrograman berupa timestamp naive ditolak dengan `ValueError`; ketidaktersediaan
referensi pada lookup berupa `ReferenceUnavailable`, dipetakan `check_entry` ke hasil
penolakan. Nilai order yang bukan integer positif langsung ditolak.

Kontrak publik v1 tidak berubah: model ini internal, bukan serializer wire.
`InstrumentRule` publik kelak diproyeksikan dari snapshot terpilih oleh SS-017,
dengan allowlist kontrak SS-002; provenance internal tidak diteruskan langsung.

## Verifikasi

Dari `services/api`, jalankan `uv run --locked ruff check .`,
`uv run --locked ruff format --check .`, `uv run --locked mypy`, dan
`uv run --locked pytest`. Test SS-009 mencakup batas band, sesi Jumat/jeda,
tanggal lokal vs UTC, libur, pergantian rule/lot/limit, suspensi dan resume,
aksi korporasi, data terlambat/hilang/ambigu, serta penolakan simulasi live.
