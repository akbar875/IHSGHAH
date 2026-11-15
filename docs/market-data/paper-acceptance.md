# SS-026 — Bukti acceptance, keputusan gerbang dan laporan fill

Tindak lanjut atas empat acceptance criteria issue #26. Implementasi awal hanya
menghasilkan receipt offline, memakai status gerbang tetap dan mengecualikan
ledger aktual. Kini endpoint admin `/api/ops/paper` membaca bukti dan ledger
dalam satu snapshot PostgreSQL repeatable-read per akun/mode.

| Kriteria | Implementasi dan bukti | Status bukti produk saat ini |
|---|---|---|
| 12 skenario PRD memiliki hasil/bukti | Verifier CI menghasilkan nomor, hasil dan nama tes per skenario serta hash file sumber. Halaman paper menampilkan semua 12 hasil dan detail buktinya. | Kualifikasi sintetik; bukan sertifikasi vendor. |
| G0/G1 lulus sebelum paper live berkualitas sinyal | Review operator append-only, asal bukti market, versi rilis, hash manifest data/model, masa berlaku, toleransi G1, protokol dan evidence E2E harus cocok. | Keputusan lulus nyata belum tersedia; G0 masih pending dan G1 SS-016 no-go. |
| Paper/actual fill terpisah | Replay dan ledger manual dikueri terpisah, dengan sumber/as-of dan satuan eksplisit. Tidak ada penjumlahan PnL keduanya. | Teruji dengan dua fill paper dan satu fill manual sintetis pada PostgreSQL. |
| Kegagalan kritis menahan kemajuan | Semua skenario harus lulus; `check-admission` exit nonzero saat gagal/missing, review salah/expired, protokol tidak cocok atau pause. | Setiap satu dari 12 skenario diuji gagal bergantian dan seluruhnya ditahan. |

Tes utama: `tests/test_paper_evidence.py`, `tests/test_paper.py`, dan
`apps/web/tests/paper.spec.ts`. Verifier CI mengharuskan tes pemisahan laporan,
review gerbang, persistensi dan penolakan kegagalan kritis ikut lulus.
Artifact `paper-acceptance-<run_id>` mengikat hasil pada SHA checkout bersih.
Receipt lama dengan `revision_kind=worktree-base` boleh ditampilkan sebagai hasil
kualifikasi, tetapi tidak memenuhi syarat kemajuan untuk suatu rilis.

## Penyimpanan dan kewenangan

Migrasi `008_paper_evidence.sql` menambah tabel append-only `paper_evidence`.
Setiap jenis (`acceptance`, `G0`, `G1`, `protocol`) memiliki cursor terbaru per akun.
Import memakai expected cursor dan advisory lock; retry receipt yang sama
mengembalikan cursor awal dan tidak mengaktifkan kembali review lama yang sudah
digantikan no-go. Hash dicek kembali saat dibaca. UPDATE/DELETE/TRUNCATE ditolak.

Runtime membutuhkan SELECT; import hanya memakai credential operator BYPASSRLS
terpisah, tidak diberikan kepada API. RLS tetap menolak INSERT runtime walaupun
runtime keliru diberi grant INSERT. Tidak ada mutation endpoint HTTP. Sesi admin
bertanda tangan mendapat akses baca sesuai akun pilot dan mode paper server,
termasuk CORS credential untuk origin yang disetujui. Query request tidak dapat
memilih akun/mode. Database/schema rusak menghasilkan 503 tanpa angka fallback.

Backup/restore SS-025 sekarang mencakup **sepuluh tabel**, termasuk bukti paper.
Manifest migrasi harus identik, target harus kosong dan restore selalu pause.
Identity cursor evidence diteruskan di atas high-water mark hasil restore.

## Review G0/G1

Schema review tersedia melalui `GateDecision.model_json_schema()` pada
`saham_signal.application.acceptance`. Isi gate, decision, release (SHA commit
40 karakter), reviewer, reviewed_at, valid_until, reason, dan proofs. Referensi
bukti adalah ID dokumen privat beserta SHA256; jangan unggah kontrak, secret atau
data berlisensi ke Git. Hash membuktikan integritas receipt, **bukan** kebenaran
lisensi atau kualitas model. Operator wajib memeriksa dokumen/sumber aslinya.

G0 passed mengharuskan seluruh check: `ingest_rights`, `analysis_model_rights`,
`storage_replay_rights`, `display_alert_rights`, `feed_quality`, `history_quality`,
`cost_capacity`. G1 passed mengharuskan `locked_holdout`, `positive_expectancy_ci`,
`risk_budget`, `robustness`, `calibration_fill_validation`. Setiap proof harus
passed dan ber-origin market; fixture simulation ditolak sebagai dasar kelulusan.

Kedua gate harus mengikat `data_manifest_sha256` yang sama; G1 juga wajib
mengikat `model_artifact_sha256`, validation_ref dan tiga toleransi finite.
Protokol harus dibekukan sesudah review validasi, dengan nilai toleransi yang sama,
sebelum observasi dimulai. Keputusan harus masih berlaku pada waktu mulai.
Acceptance untuk kemajuan harus ber-origin market, scope `licensed-feed-e2e`,
dan mengikat rilis, manifest data serta model yang sama. CI sintetik saat ini
tetap menghasilkan scope component-and-browser dan tidak dapat membuka gerbang.

Format v1 ditolak bila origin/scope diubah menjadi market/E2E. Bukti berizin
memakai format terpisah `SS-026-reviewed-e2e-v2`, dengan reviewer, reviewed_at dan
`gate_review_sha256` yang mengikat dua review terkini. Importer memeriksa aktor
review, file hasil asli dan hash. Perubahan review gate membatalkan kecocokan
review E2E lama. Format v2 adalah input review operator atas pengujian berizin,
bukan format keluaran CI fixture dan bukan sertifikasi otomatis atas sumber data.

Tidak ada pemetaan otomatis status closed issue menjadi keputusan passed.
Review pending/no-go dapat dicatat tanpa membuat bukti kelulusan rekaan.
Minimum protokol tetap 60 sesi DAN 300 transaksi layak; ini bukan bukti G2 lulus.

## Command operator

Gunakan environment backend terkunci, APP_MODE=paper, database/namespace paper,
akun pilot dan sesi sesuai panduan keamanan. Set `PAPER_RELEASE_SHA` ke commit
artefak yang benar-benar terpasang dan cocokkan dengan build receipt. Jangan
menggunakan SHA rilis lama untuk menyatakan kode baru telah direview.

```sh
python -m saham_signal.paper_evidence import --kind acceptance --file paper-acceptance.json --backend paper-backend.xml --browser paper-browser.json --actor operator --expected-cursor 0
python -m saham_signal.paper_evidence import --kind G0 --file g0-review.json --actor operator --expected-cursor 0
python -m saham_signal.paper_evidence import --kind G1 --file g1-review.json --actor operator --expected-cursor 0
python -m saham_signal.paper_evidence import --kind protocol --file frozen-protocol.json --actor operator --expected-cursor 0
python -m saham_signal.paper_evidence status
python -m saham_signal.paper_evidence check-admission
```

Import acceptance memerlukan dua file hasil asli; hash keduanya harus cocok dengan
receipt, bukan hanya hash JSON receipt itu sendiri. Protocol memakai format
`ObservationProtocol.document()`. Untuk mengganti review, baca evidence_cursors
dari status lalu pakai expected cursor terbaru. Perintah gagal tidak mencetak
payload pribadi/DSN. `check-admission` adalah pemeriksaan prasyarat, bukan command
start, izin broker atau permit yang boleh dicache. Jalur prospektif harus tetap
memeriksa kontrol dan reservasi secara atomik sebelum publikasi/eksekusi.

## Laporan aktual

Bagian `fill_reports.paper` berasal dari receipt replay. Bagian
`fill_reports.actual` membaca snapshot terkini setiap posisi dari
`manual_position_events` untuk akun yang sama **pada mode paper**. Origin harus
manual dan ID fill tidak boleh terduplikasi. Angka nol hanya muncul setelah query
ledger yang berhasil; kegagalan database menghapus tampilan lama, bukan dianggap
tidak ada transaksi. Actual berarti dikonfirmasi manual, belum diverifikasi broker.

`buy_lots`/`sell_lots`, remaining lots dan realized PnL aktual disajikan terpisah
dari shares/cash flow replay. Tidak mengakses database live/research lewat endpoint
paper atau menyimpulkan isi akun lain. `combined_pnl` selalu null. Receipt replay
historis tidak ditulis ulang ketika ledger manual bertambah.

## Batas penyelesaian

Hasil pengujian guard tidak memberikan keputusan G0/G1 produk. #8 telah ditutup
untuk riset EOD, tetapi [keputusan intraday](free-vendor-decision.md) masih NO-GO
dan G0 pending. SS-016 masih G1 no-go. Karena itu belum ada approval intraday nyata,
paper live tetap disabled, dan issue #26 belum boleh ditutup sebagai selesai penuh.
Tiga kriteria dengan bukti kualifikasi dan pemisahan laporan dapat dicentang;
kriteria keputusan lulus tetap menunggu bukti eksternal yang sah.
