# Fondasi adapter feed — SS-011

Status 13 November 2026: **implementasi parsial; issue #11 tetap terblokir sampel
vendor**. Pemilik mengonfirmasi belum ada vendor/sampel dan meminta pencarian
sumber tanpa perjanjian khusus. Tidak ada koneksi pasar yang diaktifkan dan G0
tetap pending. Fixture adalah data sintetis buatan proyek, bukan sampel vendor.

## Hasil inspeksi

- SS-005 menyediakan lifecycle worker dengan port `work`; belum ada job ingest.
- SS-009 menyediakan aturan lot point-in-time; konversi volume harus menggunakan
  aturan instrumen pada waktu event yang sudah diketahui pada waktu availability.
- SS-010 menyediakan journal append-only, mode terpisah dan versi koreksi.
- SS-008 belum menghasilkan vendor disetujui, dokumentasi wire atau sampel
  berizin. Karena itu contract test **sampel vendor: NOT_ASSESSED**.
- Kontrak v1 dibekukan. `MarketEvent` hanya mendukung trade, book_snapshot dan
  feed_status; `Candle` tersedia sebagai payload chart tanpa envelope ingest.
  Menambah enum candle pada v1 akan melanggar kebijakan kompatibilitas SS-002.

## Batas dan cara memakai fondasi

`application/feed.py` menyediakan `FeedIngestor`, boundary sequential tanpa
network. Decoder vendor yang belum dibuat wajib menghasilkan `FeedMessage`
berdasarkan spesifikasi nyata. `FeedProfile` mengunci source, schema, asal data,
delivery dan unit volume; perubahan profil dalam sesi ditolak. Referensi bukti
wajib untuk profil market; field tersebut adalah provenance, bukan pemeriksaan
lisensi otomatis atau izin melewati G0.

Empat port harus disediakan caller:

1. `lot_shares(symbol, event_time, available_at)`: lookup aturan lot berversi dari
   SS-009, bukan konstanta produksi. Reference yang hilang/ambigu harus melempar
   error. Fixture test memakai lot sintetis 100 saham.
2. `validate(schema, payload)`: gunakan `adapters.feed.validate_observation`, yang
   memvalidasi JSON Schema bersama beserta format timestamp.
3. `commit(observation)`: simpan atomik atau lempar sebelum efek tersimpan.
   `MarketJournalSink(Journal(dsn, mode, ""))` menyimpan MarketEvent ke SS-010.
   Cursor/book baru maju setelah commit berhasil. Jangan membungkus error commit
   yang ambigu sebagai retry otomatis; baca keadaan durable terlebih dahulu.
4. `snapshot_request(symbol, connection)`: minta snapshot baru pada transport
   aktif. Error request tetap terlihat; delta berikutnya mencoba request kembali.

`adapters.feed.simulation_messages(path)` hanya menerima schema
`simulation-feed/1` dengan `data_origin=simulation`. Replay caller memberikan
received_at, available_at dan processed_at secara eksplisit; adapter tidak
mengarang received_at historis dari event_time. Profil simulasi ditandai delayed,
degraded/SIMULATION dan tidak dapat dipakai di deployment live.

Harga memakai string IDR dua desimal dan Decimal. Volume saham dikonversi secara
exact, volume pecahan lot ditolak, aggressor unknown tetap unknown. Book ditujukan
untuk sesi continuous pasar reguler; locked/crossed book ditolak, mekanisme lelang
belum didukung. Delta adalah perubahan **jumlah absolut per harga**, nol menghapus
level. Semantik increment, indeks level atau sequence global memerlukan decoder
tersendiri, tidak boleh langsung dimasukkan ke boundary ini.

## Ordering, recovery dan koreksi

- Sequence book adalah integer berurutan **per simbol dan koneksi**. Snapshot
  pertama wajib ada. Delta tidak diterapkan saat gap, saat belum sinkron, atau
  setelah reconnect. Tidak ada buffer spekulatif.
- Gap membatalkan status synchronized dan meminta snapshot. Snapshot recovery
  wajib mencakup setidaknya sequence tertinggi yang ditolak; snapshot lama tidak
  dapat membuka kembali delta. Delta diterapkan ke salinan lalu diterbitkan
  sebagai book_snapshot utuh; sisi, urutan harga dan kumulatif dihitung atomik.
- `reconnect()` mengganti identitas koneksi dan membatalkan semua book sebelum
  meminta snapshot. Pesan dari koneksi sebelumnya ditolak. Sequence boleh reset
  hanya pada koneksi baru; decoder harus memberi event ID snapshot yang baru.
- Dedup sesi memakai event_id + revision dan fingerprint isi sumber, tanpa
  waktu penerimaan ulang. Isi berbeda pada identitas sama adalah konflik yang
  harus dikarantina; konflik book memicu resnapshot.
- Trade/candle terlambat tetap disimpan dengan timestamp asli dan
  `Observation.out_of_order=True`. Koreksi berupa replacement revision berurutan
  pada event_id, simbol dan tipe yang sama. Journal mempertahankan versi lama.
  Koreksi book memerlukan snapshot baru; cancel trade belum didukung oleh v1.
- Heartbeat terpisah dari trade. Status disconnected/degraded membatalkan book;
  heartbeat sehat saja tidak memulihkan book. Timeout wall-clock dan kualitas
  feed agregat tetap scope SS-012.

Identitas MarketEvent adalah hash source + upstream ID agar vendor berbeda tidak
bertabrakan. Reason journal menyimpan schema dan fingerprint upstream. Simpan raw
message melalui quarantine/storage privat caller jika dibutuhkan untuk audit;
modul ini tidak mencatat payload vendor ke log.

Dedup/revision memory **belum direhidrasi lintas restart**. Restart harus memulihkan
identitas/revision durable dan meminta snapshot sebelum ingest dilanjutkan.
Journal menolak key durable yang berbeda isi; fondasi ini tidak mengklaim
exactly-once. Rotate sesi sesuai batas memori yang ditentukan deployment; jangan
menghapus seen state saat koneksi reconnect biasa. Integrasi transport, raw
quarantine, backoff, checkpoint recovery dan job worker belum diaktifkan.

Candle dinormalisasi dan divalidasi terhadap schema `Candle`, dengan metadata
source/waktu tetap di `Observation`. `MarketJournalSink` sengaja menolaknya:
persistensi candle beserta interval dan koreksi perlu envelope kontrak baru yang
direview tersendiri. Jangan mengklaim replay candle durable sudah tersedia.

## Sumber tanpa negosiasi lisensi khusus

Pencarian dokumentasi resmi pada 13 November 2026:

| Kandidat | Bukti publik | Kesesuaian dengan SS-011 |
|---|---|---|
| EODHD Free | [Paket](https://eodhd.com/help/plans): 20 API call/hari, satu tahun histori EOD; [akses](https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours) memerlukan akun/token | Kandidat riset EOD self-service. Entitlement simbol BEI, hak storage dan penggunaan aktual belum diuji; bukan bukti trade/book intraday tersedia gratis. |
| Website BEI | [Syarat penggunaan](https://www.idx.id/id/syarat-penggunaan): penggunaan nonkomersial dengan atribusi/tanggal akses dijelaskan, scraping/crawling tidak diperkenankan | Bukan endpoint feed otomatis yang dapat dipakai untuk memenuhi issue ini. |
| Delayed/EOD melalui redistributor resmi | [Katalog BEI 2024](https://www.idx.id/media/dz5jsh1i/idx-data-catalogue-pricelist-non-ab-april-2024.pdf) mencantumkan pembebasan biaya tertentu untuk non-display delayed/EOD dari redistributor | Bebas biaya tertentu bukan bukti seluruh layanan gratis atau bebas syarat. Semantik delayed/EOD berbeda dari trade/book real-time. |

Kesimpulan terbatas: **belum ditemukan sumber BEI gratis tanpa perjanjian khusus
yang terbukti menyediakan trade + book minimal lima level, sequence, koreksi dan
recovery untuk scope ini**. Ini hasil pencarian, bukan klaim semua vendor tidak
memiliki penawaran tersebut. Belum mendaftar akun, membeli feed atau menghubungi
vendor. Sumber EOD tidak dijadikan fallback diam-diam untuk kebutuhan intraday.

## Validasi dan syarat penyelesaian issue

Dari `services/api`:

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest
```

`tests/test_feed.py` menguji fixture sintetis, unit/timestamp, dedup/conflict,
koreksi, late event, determinisme, gap/snapshot/reconnect, invalid book,
disconnect, isolasi profil/mode dan gagal commit. `test_feed_journal_roundtrip`
di `test_persistence.py` memakai PostgreSQL nyata melalui `PERSISTENCE_TEST_DSN`
seperti suite SS-010; test dilewati bila DSN tidak disediakan.

Issue #11 baru dapat ditutup setelah decoder/transport vendor yang dipilih,
contract test sampel nyata, checkpoint recovery lintas restart, dan jalur candle
durable diselesaikan. Bukti sampel harus mengikuti
[protokol evaluasi vendor](vendor-evaluation.md). PR fondasi ini menautkan
`Refs #11`, bukan mengklaim acceptance vendor sudah lulus.
