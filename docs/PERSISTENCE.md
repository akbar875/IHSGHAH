# SS-010: penyimpanan point-in-time dan audit

Issue [#10](https://github.com/akbar875/IHSGHAH/issues/10) menyediakan fondasi
PostgreSQL untuk kontrak v1. Dependency #2 dan #6 sudah selesai. Ini bukan feed,
engine pembukuan posisi, endpoint bisnis, ataupun kelulusan G0/G1/G2/G3.

## Migrasi dan paket

Dari `services/api`, setelah `uv sync --locked`, jalankan:

```sh
uv run --locked python -m saham_signal.migrate
```

Konfigurasi mengikuti `APP_MODE` dan `DATABASE_URL` pada panduan API. Gunakan
database dan credential terpisah per mode. Jalankan migrasi secara eksplisit
dengan role pemilik schema sebelum API/worker, bukan saat masing-masing startup.
Migrasi berurutan dikemas dalam wheel bersama schema kontrak v1 kanonis.
Satu transaksi dan advisory lock mencegah persaingan migrator; checksum menolak
perubahan file yang sudah diterapkan. Rerun tidak mengubah histori. Migrasi baru
harus memakai nomor baru; tidak ada downgrade destruktif otomatis.

## Model dan unit

`journal` menjadi sumber otoritatif append-only untuk lima snapshot kontrak:

| Kind | Identitas/versi | Scope |
|---|---|---|
| MarketEvent | event_id + versi koreksi | mode, user_id kosong (pasar bersama) |
| Signal | signal_id + version | mode dan akun, termasuk konfigurasi personal |
| Fill | fill_id + versi rekaman | mode dan akun |
| Position | position_id + versi snapshot internal | mode dan akun |
| Experiment | experiment_id + versi hasil | research dan akun |

Envelope menambahkan idempotency key, actor, alasan internal, versi kontrak,
source, data_origin, sequence, event_time, provider_time nullable, received_at,
available_at dan processed_at. `recorded_at` berasal dari database. Timestamp
bertipe `timestamptz`, dinormalisasi UTC pada masukan; tampilan tetap WIB.
Sequence `numeric(20,0)` menyimpan seluruh rentang string sequence kontrak,
termasuk pesan out-of-order dan sequence yang sama pada sumber berbeda.
Jangan gunakan sequence vendor sebagai ID global atau cursor commit.

Snapshot JSONB divalidasi terhadap schema v1 bersama sebelum koneksi database.
Nilai uang tetap string desimal dua tempat seperti kontrak. View `fills` dan
`position_versions` mengekspose uang sebagai `numeric(18,2)`; psycopg membaca
`Decimal`. Tidak ada konversi float atau pembulatan input. Lot adalah integer;
lot size tetap berasal dari referensi instrumen, tidak dihardcode di pembukuan.
Probability null yang belum tervalidasi dipertahankan.

`signal_versions`, `position_versions`, `experiments`, serta `audit_versions`
merupakan view atas rekaman yang sama, sehingga snapshot dan audit tidak mungkin
terpisah akibat partial commit. Trigger menolak UPDATE, DELETE dan TRUNCATE,
termasuk melalui view. Pembatalan/koreksi menambahkan versi berikutnya dengan
alasan, tidak menimpa versi lama. View audit bersifat internal, tidak dikirim ke UI.

## Repository dan transaksi

`saham_signal.adapters.persistence.Journal(dsn, mode, user_id)` memerlukan scope
server yang sudah diotorisasi. `append([Record, ...])` memvalidasi seluruh batch
dan menyimpan satu transaksi. Pencatatan fill dan snapshot posisi yang dihasilkan
harus berada dalam batch yang sama. Modul posisi kelak menghitung dan memvalidasi
efek bisnis (lot tersisa, biaya, koreksi, partial fill); repository ini tidak
membuka posisi dari sinyal READY atau mengeksekusi order.

Key unik per mode/akun. Retry identik mengembalikan cursor asli tanpa efek
tambahan; key sama dengan isi berbeda ditolak. Seluruh envelope termasuk waktu
processing harus dipertahankan saat retry. Versi tiap entitas harus berurutan
mulai 1, termasuk bila memakai idempotency key baru. Batch gagal akan rollback
seluruh efek baru. Advisory lock per akun/mode menyerialkan writer untuk pilot,
termasuk writer konkuren; semua writer wajib melalui repository ini. Hash
collision hanya menyerialkan scope tambahan, tidak membuka akses data.

`replay(as_of)` memfilter `available_at <= as_of`, diurutkan available_at,
sequence, lalu cursor sebagai tie-breaker. `snapshot(kind, id, as_of)` mengambil
versi tertinggi yang sudah tersedia. Waktu kejadian lama tidak membuat informasi
yang baru diterima terlihat lebih awal. Replay ini membaca snapshot yang saat ini
tersimpan, bukan API stream paginasi; cursor append tidak boleh dipakai sebagai
watermark available_at. Volume besar/paginasi dan retensi partisi perlu ukuran
beban dan izin data pada issue adapter/operasi berikutnya. Indeks tersedia untuk
scope+available_at, riwayat entitas+versi, dan source+recorded_at.

## Isolasi dan hak akses

Repository memeriksa nama database `saham_signal_<mode>`. RLS dipaksa pada
`journal`, termasuk pemilik biasa; view memakai `security_invoker`. Scope mode
dan akun dipasang dengan `set_config(..., true)` dalam transaksi sehingga tidak
bocor ke transaksi berikutnya. Tanpa scope, akses ditolak. Akun kosong hanya
untuk MarketEvent. Eksperimen hanya research; simulasi ditolak pada live.

Role runtime produksi harus NONSUPERUSER, NOBYPASSRLS, bukan pemilik schema,
tanpa hak DDL/keanggotaan role migrator. Berikan USAGE schema, SELECT/INSERT
`journal`, USAGE identity sequence dan SELECT view yang diperlukan. Untuk
retention_candidates, berikan SELECT retention_policy juga; jangan beri hak
mengubah policy kepada runtime. Pemilik migrasi mengelola policy secara terpisah.
Credential superuser lokal Compose hanya untuk pengembangan/CI.

RLS memperkuat scope aplikasi, bukan autentikasi pengguna: role backend dapat
mengatur context untuk akun yang telah diotorisasi. Jangan mengekspos SQL,
credential, atau pilihan user_id/mode langsung kepada browser. SS-023 tetap
menyediakan sesi dan otorisasi transport sebelum akses pilot personal.

## Retensi dan pemulihan

`retention_policy` berisi mode, source, retain_days nullable, legal_hold (default
true), dan approval_ref. Tanpa policy atau saat hold aktif, tidak ada kandidat
kedaluwarsa. `retention_candidates` menampilkan rekaman melewati retain_days
berdasarkan recorded_at. Ini inventaris untuk ekspor/arsip, tidak menghapus
otomatis. Kebijakan vendor belum disepakati pada SS-008, sehingga tidak
mengarang durasi retensi produksi. Data contoh hanya simulasi.

Sebelum data berizin/personal dipakai: catat persetujuan dan durasi per source,
backup database sesuai mode, uji restore, lalu ekspor kandidat beserta checksum
dan verifikasi replay dari arsip. Penghapusan yang diwajibkan kontrak/akun
memerlukan migrasi pemeliharaan eksplisit oleh pemilik, mencakup snapshot,
backup dan salinan arsip. Runtime tidak mendapat pengecualian trigger. Jangan
mengaktifkan ingest berizin bila persyaratan hapus/retensinya belum dapat dipenuhi.
SS-023/025 melengkapi kebijakan personal, backup dan runbook produksi.

## Validasi

Test biasa memeriksa kontrak dan envelope. Pengujian PostgreSQL sungguhan
memerlukan database research **disposable**, dengan role admin yang dapat
membuat schema/role pengujian:

```sh
PERSISTENCE_TEST_DSN=postgresql://.../saham_signal_research uv run --locked pytest tests/test_persistence.py
```

Pada PowerShell gunakan `$env:PERSISTENCE_TEST_DSN = 'postgresql://...'` lalu
jalankan perintah pytest. Setiap test membuat schema dan role acak miliknya
sendiri lalu membersihkannya; tidak mereset schema aplikasi. CI backend wajib
menyediakan PostgreSQL 18.7 sementara agar test database tidak dilewati.
Test mencakup database/schema kosong, rerun/checksum migrasi, duplicate konkuren,
atomic rollback, Decimal maksimum, versi pembatalan historis, available_at,
sequence 20 digit/out-of-order, eksperimen, RLS non-superuser, penolakan mode,
trigger append-only, dan kandidat retensi dengan legal hold.
