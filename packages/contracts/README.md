# Contracts v1 — SS-002

Status: kontrak dan fixture simulasi tersedia; belum ada server/feed berjalan atau kelulusan G0/G1/G2/G3. Dependency: [ADR-0001 Accepted](../../docs/decisions/0001-stack-and-module-boundaries.md).

## Sumber kontrak dan pemeriksaan

[definitions.mjs](scripts/definitions.mjs) adalah sumber deklaratif tunggal. `npm run build` menerbitkan [JSON Schema 2020-12](v1/schema.json) dan [OpenAPI 3.1.1](v1/openapi.json). Artefak JSON dikomit agar TypeScript/Python tidak perlu menjalankan generator JavaScript. Jangan edit hasil generate; `npm run check` mendeteksi artefak tertinggal. [examples.json](v1/examples.json) adalah fixture terpisah untuk seluruh definisi; semua berlabel simulasi dan bukan bukti aturan BEI atau performa model.

```sh
cd packages/contracts
npm ci --ignore-scripts
npm run check
python -m venv .venv
# Windows: gunakan .venv/Scripts/python.exe
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python test/check_python.py
```

Validator JavaScript: Ajv 8.20.0 + ajv-formats 3.0.1 (MIT), dependency exact dan lockfile. Validator Python: jsonschema + FormatChecker dan rfc3339-validator (MIT), dependency pengujian dipin dalam requirements-test.txt. Keduanya memvalidasi schema dan fixture JSON yang sama. Tidak ada coercion, default injection atau penghapusan field asing. TypeScript memakai Ajv2020 untuk validasi runtime; Python memakai Draft202012Validator. Generator tipe statis/SDK dipilih saat bootstrap SS-003/004 tanpa menulis ulang kontrak. Tidak ada perhitungan domain di paket ini.

## Representasi wire

| Nilai | Representasi |
|---|---|
| Uang/harga | String IDR dengan dua pecahan, maksimum 16 digit integer: `"1000.00"`. Float JSON dilarang. Harga >0, biaya boleh nol. Backend memakai Decimal/integer minor unit; jangan memakai Number untuk pembukuan. |
| Return/slippage/risiko | String enam pecahan dalam rasio, bukan persen: `"0.005000"` = 0,5%. Batas bisnis diperiksa domain. |
| Lot | Integer; fill/level book >0, sisa/volume candle boleh nol. Saham = lots × lot_size_shares dari aturan bertanggal, bukan konstanta global. |
| Waktu | RFC3339 UTC berakhiran Z; offset lokal ditolak. UI Asia/Jakarta. as_of adalah waktu snapshot, data_as_of waktu input sinyal; available_at batas penggunaan informasi pada replay. |
| Sequence | String integer desimal sampai 20 digit, dibandingkan dengan BigInt/int. Scope per stream/subscription/mode/akun/simbol. |
| Probabilitas | `{status,value,calibration_version}`: unvalidated/unavailable wajib value dan versi null; validated wajib nilai 0..1 dan versi kalibrasi. Nol bukan pengganti nilai hilang. |
| Versi | contract_version exact 1.0.0; versi Signal/plan integer positif; versi model, aturan, konfigurasi, dataset dan biaya terpisah. |

Setiap respons/event memiliki contract_version, as_of, mode, data_origin, quality. Mode deployment research/paper/live berbeda dari quality.feed live/delayed/disconnected/unavailable. Simulation dilarang pada mode live; consumer tetap wajib menolak event mode lain sebelum mutasi/pengiriman alert.

InstrumentRule memuat aturan efektif dan kalender berversi. MarketEvent memuat event_time, provider_time nullable, received_at, available_at, processed_at, source, sequence dan payload bertag trade/book_snapshot/feed_status. Jenis event tambahan memerlukan versi kontrak berikutnya. NewsEvent dan Experiment hanya backend, tanpa rute publik.

Signal satu versi append-only; perubahan membuat versi baru. READY tidak membuka posisi. Fill aktual/simulasi dicatat terpisah. CLOSED wajib remaining_lots=0; exit gagal tetap OPEN/PARTIAL/EXIT_REQUESTED dengan overnight_risk. Konsistensi jumlah fill/biaya/harga rata-rata, waktu, simbol, tick/limit, stop/target, risiko dan transisi status adalah kewajiban domain SS-009/010/015/021; otorisasi SS-023. Schema memvalidasi bentuk wire, bukan konsistensi lintas field/kelayakan strategi. Unik/idempotent ID diperiksa storage.

## REST publik

Base `/api/v1`, JSON, seluruh rute memerlukan sesi. Nama cookie pada OpenAPI adalah interface awal; autentikasi final/CSRF di SS-023. Server menentukan akun/mode dari sesi/deployment. Request fill tidak menerima user_id atau mode; fees_idr adalah biaya pengisian pengguna. SS-017 menyediakan [query market dan stream fixture research](../../docs/market-data/market-api.md); rute lainnya masih spesifikasi:

| Rute | Kontrak |
|---|---|
| GET /candidates | CandidatesResponse (Signal[]) sesuai nominal/konfigurasi akun |
| GET /stocks/{symbol} | StockDetailResponse: harga, aturan, sinyal, likuiditas, depth, tekanan agresor |
| GET /stocks/{symbol}/depth | DepthResponse: satu snapshot konsisten dan kedalaman terbatas |
| GET /stocks/{symbol}/chart?interval=1m | ChartResponse; 1m/5m/15m, candle terpisah dari proyeksi |
| GET /stocks/{symbol}/signals | SignalHistoryResponse append-only |
| GET/PUT /watchlist | Watchlist / WatchlistResponse |
| GET/PUT /settings/risk | RiskSettings / RiskSettingsResponse; configuration_version untuk optimistic concurrency |
| GET/POST /positions | PositionsResponse / OpenPositionRequest → PositionResponse; fill awal BUY |
| GET /positions/{position_id} | PositionResponse |
| POST /positions/{position_id}/fills | FillRequest → PositionResponse; BUY tambahan/SELL parsial diperiksa domain |
| GET /alerts | AlertsResponse, in-app |

Daftar maksimum 1000 elemen: server mengembalikan error jika melampaui batas, tidak memotong diam-diam; pagination memerlukan versi baru. PUT mengganti objek utuh. PUT/POST wajib Idempotency-Key (1..128 karakter), scope akun+mode+method+path; retry body sama mengembalikan hasil pertama, body berbeda menghasilkan 409. Konfigurasi basi menghasilkan 409. Perubahan nominal menghasilkan snapshot/subscription baru. Tidak ada auto-order broker.

Sukses GET/PUT 200, POST 201. ErrorResponse memuat metadata sama serta `{code,request_id,retryable,fields}`, tanpa pesan bebas, stack atau respons upstream. Pemetaan: 400 INVALID_REQUEST/UNSUPPORTED_VERSION, 401 UNAUTHENTICATED, 403 FORBIDDEN, 404 NOT_FOUND, 409 CONFLICT/RESYNC_REQUIRED, 422 INVALID_REQUEST, 429 RATE_LIMITED, 500 INTERNAL_ERROR, 503 DATA_UNAVAILABLE. Retryable 429/503 memberi Retry-After dan backoff. UI memakai teks lokal berdasarkan code. Error tidak mengungkap keberadaan akun lain.

Seluruh objek publik menggunakan additionalProperties:false, termasuk nested/stream, tanpa map bebas, dokumen berita, source_ref berita, DSN atau credential. Serializer server memetakan allowlist, tidak meneruskan objek ORM/vendor. Field teks metadata bukan saluran konten upstream. Test menelusuri referensi REST/WebSocket agar NewsEvent/Experiment/MarketEvent tidak terpapar. Keamanan nilai dan akses tetap diuji SS-023.

## WebSocket snapshot/delta

Path `/api/v1/stream`, sesi dan pemeriksaan Origin sebelum upgrade. Subscribe berisi contract_version, subscription_id, topic, symbol nullable, resume_cursor nullable. Signals dipersonalisasi nominal/risk aktif; positions/alerts hanya pemilik; depth wajib symbol. Server menentukan user_id/mode. Cursor opak terikat akun, mode, konfigurasi, topic, simbol dan stream; bukan token akses.

1. Subscribe baru menerima Snapshot dengan stream_id, cursor, sequence dan seluruh items; snapshot dan cursor atomik. Klien mengganti state subscription utuh.
2. Delta memiliki previous_sequence, sequence, cursor dan operations. Sequence wajib previous_sequence+1. Upsert mengganti entitas utuh; remove menghapus entity_id. ID harus cocok signal_id/position_id/event_id/symbol sesuai topic. Depth adalah satu book penuh, bukan campuran level. Seluruh operations diterapkan atomik.
3. Terapkan delta hanya jika scope/stream cocok dan previous_sequence sama dengan terakhir. Duplikat sequence≤terakhir diabaikan. Gap, delta sebelum snapshot, stream baru, pesan invalid, atau kualitas kritis buruk menahan status live dan meminta resync. Jangan mengirim alert dari state yang belum sinkron.
4. Reconnect segera menampilkan disconnected/resync. Replay dari cursor hanya jika seluruh rantai tersedia dan scope identik dengan snapshot lokal. Cursor kedaluwarsa/salah scope atau snapshot lokal hilang: ErrorResponse RESYNC_REQUIRED, lalu subscribe cursor null dan Snapshot baru. Restart memakai stream_id baru. Live tampil hanya setelah snapshot/rantai lengkap dengan feed live dan status healthy.
5. Error auth menutup koneksi; retry memerlukan sesi sah. Cursor tebakan tidak memberi akses akun lain. Redis bukan penyimpan cursor otoritatif. Ordering, dedup, resync dan otorisasi implementasi diuji SS-017/023/026; schema hanya bentuk pesan.

Contoh: snapshot seq 1 → delta previous 1, seq 2; seq 2 ulang diabaikan; delta previous 3, seq 4 setelah seq 2 meminta resync. Sesudah snapshot baru seq 10, delta previous 10, seq 11 boleh diterapkan. Timestamp bukan pengganti sequence.

## Kompatibilitas

Kontrak v1 dibekukan pada rilis ini. Karena objek ditutup/versi exact, perubahan field/enum/required/nullable/unit/arti atau set nilai valid memerlukan major baru dengan direktori/path baru (`v2`, `/api/v2`). Penambahan endpoint tanpa mengubah schema lama boleh dirilis terpisah; jangan menganggap penambahan field kompatibel. Patch hanya dokumentasi/fixture yang tidak mengubah set payload valid; contract_version wire tetap 1.0.0. Pertahankan v1 selama migrasi; deploy server mendukung versi baru sebelum client. Consumer menolak versi asing. Perubahan model/policy tidak mengubah versi wire. Review kontrak dan check JS/Python wajib; build --check mendeteksi drift generate, bukan bukti kompatibilitas semantik otomatis.

Dasar format: [JSON Schema 2020-12](https://json-schema.org/draft/2020-12), [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html), [Ajv formats](https://ajv.js.org/packages/ajv-formats.html). Scope produk: [PRD §12 dan FR-01/06/08/12](../../docs/PRD-Saham-Signal.md).
