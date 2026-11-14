# SS-026 — Kualifikasi integrasi paper

Inspeksi GitHub 14 November 2026: dependency implementasi #16/#19/#20/#21/#22/
#23/#25 sudah closed. **#8/G0 masih open**: feed, sampel berizin, biaya dan
kapasitas vendor belum terbukti. Laporan SS-016 tetap **G1 no-go/experiment**.
Status closed pada issue implementasi bukan keputusan lulus gerbang.

Implementasi ini menyatukan kualifikasi **offline**, bukan paper live.
Issue #26 belum memenuhi seluruh scope prospektif: toleransi dari validasi belum
tersedia dan tidak boleh dikarang untuk menutup issue. Tidak ada adapter
prospektif, reservasi modal bersama, promosi model, atau kredit observasi G2.

## Alur dan batas

`application.paper.qualify` menjalankan satu rencana hipotetis dari posisi datar
dalam namespace paper. FeedIngestor memvalidasi pesan/timing dan merekonsiliasi
book, FeatureEngine menghitung snapshot point-in-time, baseline memberi skor
aturan (bukan probabilitas), lalu risk engine menentukan kapasitas. Feed,
bid/ask, waktu quote, likuiditas, trigger dan kontrol pada input caller diganti
dengan nilai yang dihitung pipeline. Referensi dan fee berversi tetap diperlukan.

Pesan sesudah waktu keputusan hanya memengaruhi replay. Candle yang dimulai
sebelum entry tidak dipakai sebagai pemicu exit. Harga pecahan IDR ditolak di
batas eksekusi, tidak dibulatkan diam-diam. Setiap frame book diperiksa kembali
terhadap heartbeat/recovery; candle tidak menyediakan likuiditas atau menyegarkan
umur book. Kontrol SS-025 dibaca ulang sebelum replay menghasilkan output.

Replay SS-014 mencatat antrean, latensi, fee, partial/unfilled dan posisi yang
gagal exit. `paper_fills`/`paper_positions` berasal dari replay; `actual_fills`
selalu kosong dengan penanda **excluded**, bukan klaim bahwa pengguna tidak
memiliki transaksi. Ledger `manual_position_events` tidak dibaca/diubah.
Tidak boleh menjumlahkan PnL atau jumlah transaksi dua sumber tersebut.

Policy alert SS-022 dipanggil di scope paper sebagai preview. Satu pengamatan
READY belum memenuhi hysteresis sehingga preview null. Job offline tidak
memanggil inbox, mengirim alert, atau membuat fill manual. Kualifikasi dedup
inbox persisten diuji terpisah lewat receipt acceptance.

## Receipt persisten dan tampilan

Migrasi `007_paper_qualification.sql` menambah receipt append-only pada database
`saham_signal_paper`, dengan RLS per akun, content hash dan retry idempotent.
Receipt menyimpan hash input/protokol, fitur, baseline, audit risiko, replay dan
alasan blokir. Akun runtime hanya membutuhkan SELECT/INSERT pada tabel tersebut;
tidak membutuhkan akses tulis ledger manual atau kontrol operasi.

Backup SS-025 kini mencakup **sembilan tabel**, termasuk `paper_qualification`.
Restore tetap hanya ke target kosong dengan manifest migrasi identik dan selalu
pause. Backup lama dengan manifest enam migrasi harus dipulihkan memakai rilis
yang cocok, lalu dimigrasikan; jangan mengedit checksum atau memaksa manifest.

`GET /api/ops/paper` membutuhkan sesi admin bertanda tangan, mode paper dan
akun pilot server. Query tidak dapat memilih akun/mode. Receipt kosong memberi
`receipt: null`; database gagal memberi 503 tanpa fallback. Respons private/
no-store menyertakan status kontrol terbaru; receipt lama tetap sebuah artefak
historis, bukan rekomendasi entry saat ini.

Halaman `/paper` membaca endpoint ini dan menampilkan jumlah fill/posisi
simulasi serta waktu WIB. Ia menolak mode/origin campuran, fill aktual di receipt
dan status yang mengaku mengaktifkan paper live. Error/muat ulang menghapus
angka lama. Halaman ini tidak mengubah mode dashboard research, tidak menampilkan
detail model dan tidak menyediakan tombol untuk memulai paper live.
Konfigurasikan API base URL web ke service paper untuk membaca receipt; halaman
research lain tetap membutuhkan service research dan tidak otomatis berganti mode.

## Menjalankan kualifikasi lokal

Dari environment backend terkunci pada `services/api`:

```sh
uv run --locked python -m saham_signal.paper > ../../.work/paper-simulation.json
```

Output default sepenuhnya offline dan tidak membutuhkan database. Opsi `--persist`
memerlukan konfigurasi APP_MODE=paper, DATABASE_URL database paper, namespace Redis
paper, SESSION_SECRET dan PILOT_ACCOUNT_ID=`simulation-account`. Terapkan migrasi
secara eksplisit terlebih dahulu. Command tidak menerima token atau DSN melalui
argv dan tidak mengubah identitas akun fixture menjadi akun pengguna.

Untuk pengujian, siapkan **database disposable** research dan paper; set
`PERSISTENCE_TEST_DSN` serta `PERSISTENCE_PAPER_TEST_DSN` ke masing-masing database.
Jangan gunakan database pilot. Jalankan dari `services/api`:

```sh
uv run --locked pytest --junitxml=../../.work/paper-backend.xml
```

Dari `apps/web`, setelah `npm run check` dan instalasi Chromium Playwright:

```sh
node node_modules/@playwright/test/cli.js test --reporter=list,json
```

Set `PLAYWRIGHT_JSON_OUTPUT_NAME` ke path absolut `.work/paper-browser.json`
sebelum perintah browser. Dari root, gabungkan bukti:

```sh
python scripts/check-paper-acceptance.py .work/paper-backend.xml .work/paper-browser.json .work/paper-acceptance.json
```

CI mengunggah XML backend, JSON browser, simulasi paper dan receipt gabungan.
Job `Paper acceptance qualification` menjadi dependency `Runtime quality gate`.
Evidence skenario hilang/skipped/gagal/flaky atau suite error menahan kemajuan.
Kelulusan ini hanya berarti kualifikasi komponen/browser sintetik, bukan E2E
feed vendor sampai perangkat pengguna atau kelulusan G0/G1.

## Protokol observasi dan pekerjaan tersisa

`ObservationProtocol` membekukan waktu, referensi validasi, maksimum Brier,
galat fill rate dan drawdown IDR dengan hash. Nilai harus Decimal finite positif;
toleransi fraksi tidak boleh melebihi satu. Bekukan sebelum observasi dimulai.
Minimum **60 sesi bursa DAN 300 transaksi simulasi layak eksekusi** tidak dapat
diturunkan. Dua minimum tersebut bukan bukti kelulusan otomatis: evaluasi
dependensi sinyal, sampel efektif, breakdown kondisi pasar/likuiditas/nominal
dan kecukupan bukti tetap wajib.

Manifest saat ini membiarkan tiga toleransi dan referensi validasi null.
`budgets_complete=false`, `paper_live_enabled=false`, G2 `not-started`.
Mengisi field protokol atau mengubah hasil acceptance tidak memberikan izin
eksekusi. Belum ada jalur yang bisa menerima string "G0 passed" dari request.

Untuk menyelesaikan scope prospektif #26: dapatkan bukti vendor/hak data G0;
hasilkan keputusan G1 lulus dari holdout terkunci; turunkan dan review ketiga
toleransi dari validasi; implementasikan adapter prospektif, transaksi reservasi
modal dan publikasi snapshot paper yang konsisten; jalankan acceptance E2E pada
jalur tersebut. Baru setelah itu bekukan manifest dan mulai observasi G2 dengan
log sesi/transaksi, kalibrasi/fill/drawdown serta stop/review pada pelanggaran.
