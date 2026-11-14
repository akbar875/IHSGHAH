# Informasi resmi dan berita internal — SS-024

## Hasil inspeksi

Issue #24 memerlukan ingest berizin, deduplikasi, pemetaan emiten, kredibilitas,
first-available timestamp, ekstraksi terbatas dan ablation tanpa menghambat pasar.
#10/#13/#23 telah selesai dan ada di main. #8 masih terbuka: belum ada vendor,
kontrak atau sampel berizin. Karena itu implementasi bersyarat ini menyediakan
jalur research dengan pengaman izin dan bukti simulasi. Tidak ada sumber produksi
diaktifkan, manfaat berita produksi belum diukur dan G0–G3 tetap pending.

## Jalur dan batas kepercayaan

`python -m saham_signal.news_ingest registry.json` adalah job operator terpisah:
satu envelope plaintext JSON dari stdin → validasi → ekstraksi → transaksi pada
`internal_news`. Job tidak dijalankan oleh startup API/worker atau feed consumer.
Kegagalan, backlog atau timeout berita tidak menahan commit pasar. Tidak ada queue
pasar bersama, callback model, fetch URL, browser, tool executor atau akses broker.
Sumber belum terdaftar atau grant tidak mengizinkan storage/analysis ditolak.
Grant harus valid saat penerimaan dan saat hasil tersedia. Izin pemrosesan LLM
terpisah dan default false. Registry merupakan konfigurasi operator tepercaya;
isi dokumen/model tidak dapat mengubah izin atau kredibilitas sumber.

Input hanya `text/plain`, maksimal 32.000 karakter/64.000 byte UTF-8; envelope
maksimal 70.000 byte. HTML, attachment, field URL/action/tool, harga/lot dan metadata
tambahan ditolak schema. URL/instruksi di dalam teks tetap teks pasif: tidak diikuti
atau dieksekusi. Error CLI generik tidak mencetak teks, DSN atau respons model.
Tidak ada pemanggilan LLM atau sumber berbayar sehingga anggaran pemanggilan saat
ini **nol**. Ekstraktor jaringan kelak memerlukan izin/anggaran/isolasi tersendiri
serta kontrol [keamanan dokumen](../SECURITY.md); belum diimplementasikan.

Ekstraksi default hanya memetakan kode emiten empat huruf eksplisit dari universe
operator. Nama/alias ambigu abstain; ini bukan entity linker bahasa alami. Keluaran
ekstraktor opsional hanya boleh berisi symbols, jenis event, ringkasan internal,
method dan versi. Simbol wajib ada di teks dan universe; LLM tidak dapat menciptakan
otorisasi entry, kredibilitas atau angka trading. Data `unverified` disimpan untuk
audit tetapi tidak dihitung sebagai fitur. Ringkasan/teks tetap data tidak tepercaya
meskipun asal sumber official. Tidak ada raw sentiment atau ringkasan pada UI.

## Waktu, revisi dan deduplikasi

Semua waktu harus timezone-aware; simpan UTC. `received_at` dibuat oleh clock job,
bukan field input. `available_at = max(received_at, published_at, waktu selesai
ekstraksi)`. Publikasi lama yang baru diterima hari ini tidak tersedia untuk backtest
kemarin. Hasil ekstraksi terlambat juga belum tersedia saat publikasi. Replay hanya
membaca `available_at <= as_of`, lalu memilih revisi tertinggi yang sudah tersedia.

Kunci sumber/document_id/revision idempotent dan terkunci transaksi. Retry identik
mengembalikan receipt pertama, bukan membuat timestamp lebih dini/baru. Isi berubah
dengan revision sama ditolak. Revisi dimulai 1, berurutan dan availability monoton;
koreksi append-only tidak mengubah snapshot masa lalu. Hash SHA256 atas teks NFKC,
casefold dan whitespace dipakai untuk exact normalized dedup lintas dokumen/sumber.
Near-duplicate/parafrasa belum digabung. Pemilihan sumber official/verified hanya
menggunakan salinan yang sudah tersedia saat cutoff; verifikasi kemudian tidak
menaikkan kredibilitas historis. Feature window memakai waktu pertama hash diketahui,
sehingga sindikasi terlambat tidak menyegarkan berita lama. Semua receipt dipertahankan.

`NewsRepository.as_of` mengembalikan receipt tersedia termasuk revisi untuk audit;
`point_in_time` membuat tampilan revisi/dedup dan `event_count` menghitung fitur.
Fitur dihitung ulang dengan reducer yang sama pada research. Tidak ada integrasi
otomatis ke `FeatureEngine`, ranking produk, risk engine atau serving cache.

## Menjalankan secara lokal

Migrasi `005_internal_news.sql` dijalankan eksplisit melalui entrypoint migrasi
biasa. Tabel hanya menerima data pada database `saham_signal_research`, append-only,
dengan RLS context `ss.news_internal`. Tidak ada data personal atau mode paper/live.
Jalankan job dengan role khusus NONSUPERUSER/NOBYPASSRLS, bukan pemilik schema.
Berikan USAGE schema, SELECT/INSERT `internal_news` dan USAGE sequence
`internal_news_cursor_seq`; jangan beri akses journal/posisi atau DDL. Jangan beri
API/market role akses tabel ini atau default grants ke seluruh tabel. RLS context
bukan autentikasi; pemisahan hak SQL adalah batas kemampuan utama.

Set `NEWS_DATABASE_URL` di environment job dengan DSN role khusus. Job tidak membaca
`DATABASE_URL`/credential API. Contoh registry **simulasi saja**, simpan di direktori
lokal yang tidak di-commit; perbarui interval sesuai eksperimen:

```json
{
  "grants": [{
    "source": "invented-official",
    "evidence": "SIMULATION ONLY, not a vendor license",
    "valid_from": "2026-10-01T00:00:00Z",
    "valid_to": "2026-12-01T00:00:00Z",
    "storage": true,
    "analysis": true,
    "llm_processing": false,
    "origin": "simulation",
    "credibility": "official"
  }],
  "symbols": ["SIMA", "SIMB"]
}
```

Envelope stdin:

```json
{
  "source": "invented-official",
  "document": {
    "document_id": "sim-1",
    "revision": 1,
    "published_at": "2026-11-14T03:00:00Z",
    "text": "SIMULATION ONLY: SIMA disclosure"
  }
}
```

Dari `services/api`, di shell POSIX:

```sh
uv run --locked python -m saham_signal.news_ingest /local/registry.json < /local/envelope.json
uv run --locked python -m saham_signal.adapters.news_simulation
uv run --locked pytest tests/test_news.py
```

Pada PowerShell gunakan `Get-Content -Raw <file> | ...news_ingest <registry>`.
Tidak ada network adapter vendor; adapter berizin kelak harus memasok envelope lewat
stdin dan menegakkan MIME/batas/timeout sebelum serialisasi. Operator memonitor
exit status job dan latency/backlog melalui runner terpisah, tanpa mencetak payload.

Retensi tidak diasumsikan dari masa berlaku grant: arsip append-only belum memiliki
janitor. Sebelum data nyata, operator wajib menyetujui hak storage/analisis/LLM,
masa simpan, backup/legal hold dan prosedur hapus sesuai kontrak. Jika belum dapat
dipenuhi, jangan membuat grant licensed atau mengaktifkan ingest. Data berlisensi,
registry/kontrak rahasia dan kredensial tidak masuk Git.

## Ablation dan keputusan

`NewsProtocol` membekukan hash dataset berita, protokol baseline SS-016, aturan
gate dan window sebelum membuka holdout. Operator harus menyimpan protokol serta
receipt konsumsi holdout secara atomik dalam journal eksperimen sebagaimana SS-016;
guard in-process bukan lock riset lintas proses. Manifest dataset pasar, referensi,
biaya, split, purge/embargo dan penggunaan holdout sekali diwarisi `Study`.

Bandingkan baseline yang sama per nominal/split dengan dan tanpa gate tetap
`require-verified-mapped-event-v1`. Gate hanya menahan entry baseline bila tidak ada
event terverifikasi tersedia; berita positif tidak menciptakan entry. Kedua jalur
memakai `execute`, risk sizing, harga, biaya dan simulator SS-016 yang sama.
Tidak melatih model, mengubah harga/sizing atau memilih aturan memakai holdout.
Calibration berita belum dikembangkan; tidak menerbitkan probabilitas model berita.

Laporan mencatat metrik setelah biaya dan paired delta pada kesempatan yang sama,
termasuk nol untuk rencana yang ditahan, dengan CI bootstrap blok sesi. Posisi belum
tertutup membuat perbandingan censored (`null`), bukan diasumsikan profit/exit.
CI lower bound >0 hanya flag manfaat research; bukan izin promosi. Ranking produk
tetap baseline dan `ranking_enabled=false` dalam semua keadaan. Tanpa manfaat
terukur, berita tidak dipaksakan. Sampel berizin, bukti OOS, kajian risiko dan
persetujuan independen diperlukan sebelum perubahan ranking.

[Bukti simulasi](../../research/reports/SS-024-simulation.md) membandingkan dataset
kosong dan event tersedia untuk semua kasus. Tes menguji late arrivals, latency,
koreksi, sindikasi, izin/schema, immutability dan concurrency PostgreSQL, error
tersanitasi serta absennya dependensi berita pada jalur pasar/transport. Integrasi
PostgreSQL memakai `PERSISTENCE_TEST_DSN` disposable dan dijalankan oleh CI backend.
