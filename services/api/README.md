# API FastAPI

Fondasi SS-004: package `saham-signal-backend` yang dapat dipasang API dan worker,
konfigurasi startup tervalidasi, probe dependency, CORS dan error contract SS-002.
SS-017 menambahkan [API market dan stream fixture research](../../docs/market-data/market-api.md).
SS-020 menambahkan [watchlist dan profil risiko/biaya per akun](../../docs/market-data/watchlist-settings.md),
penyimpanan PostgreSQL append-only dan evaluasi budget simulasi. Migrasi eksplisit
`uv run --locked python -m saham_signal.migrate` diperlukan sebelum akses pengaturan.
Belum ada autentikasi produksi, ingest vendor, model tervalidasi, atau alert live.

SS-009 menambahkan service internal [referensi instrumen point-in-time](../../docs/market-data/instrument-rules.md).
`lookup` memilih versi berdasarkan waktu berlaku dan `available_at`; `check_entry`
memeriksa board/pasar, status, aksi korporasi, sesi, lot, fraksi dan limit.
Adapter default kosong dan seluruh fixture berlabel simulasi; belum ada feed produksi.

SS-015 menambahkan [risk engine dan state rencana](../../docs/market-data/risk-engine.md)
internal research/paper. `evaluate` menghitung lot dengan Decimal, `transition`
memperbarui WATCH/READY/EXPIRED/CANCELLED secara idempotent dan berversi, dan
`audit_document` menyediakan artefak replay. Tidak ada Fill/Position atau alert live
yang dibuat; reservasi portofolio atomik tetap tanggung jawab service pemanggil.

## Fresh clone / menjalankan lokal

Prasyarat: Git dan [uv 0.13.7](https://docs.astral.sh/uv/getting-started/installation/).
Python **3.13.18** diunduh otomatis oleh uv bila belum tersedia. Dari root repo:

```powershell
cd services/api
uv sync --locked
Copy-Item .env.example .env
uv run --locked python -m saham_signal.transport.http --env-file .env
```

Entrypoint bind ke `127.0.0.1:8000` dan mengatur selector event loop yang diperlukan
psycopg async pada Windows. Tanpa `--env-file`, hanya environment proses dan default
kode yang dipakai. Environment proses mengalahkan file lokal. Deployment sebaiknya
memasok environment/secret store, tanpa file `.env` pengembangan.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

API dapat mulai tanpa PostgreSQL/Redis. `/health` mengembalikan 200
`{"status":"ok","mode":"research"}` untuk liveness; `/ready` mengembalikan 503
`DATA_UNAVAILABLE` sampai **kedua** dependency benar-benar menjawab `SELECT 1` dan
Redis `PING`. Setiap request readiness mengulang pemeriksaan secara paralel, timeout
per dependency (default 3 detik), tanpa cache status dan tanpa menampilkan DSN/exception.
Koneksi probe selalu ditutup. Readiness 200 berisi `status`, `mode`, dan
`dependencies: {"postgresql": true, "redis": true}`. Tidak ada klaim kesiapan feed/model.
Compose PostgreSQL/Redis tersedia di [setup lokal SS-006](../../infra/README.md).
Jalankan `node scripts/local-infra.mjs up research` dari root; default Settings dan
file env contoh cocok dengan credential Compose. Migrasi bisnis mengikuti SS-010.
Swagger lokal di `/docs`; `/openapi.json` mencantumkan bootstrap dan rute market.
Schema wire market otoritatif tetap `packages/contracts/v1/openapi.json` beserta
`schema.json`; payload aktual divalidasi terhadap schema yang dibundel di wheel.

## Konfigurasi dan isolasi

Settings dibekukan saat factory dipanggil sebelum server menerima traffic. Mode
tidak dapat diganti lewat header/query. Startup gagal dengan pesan generik tanpa
mencetak nilai environment bila tidak valid.

| Variable | Default / validasi |
|---|---|
| `APP_MODE` | `research`; hanya `research`, `paper`, `live` |
| `DATABASE_URL` | PostgreSQL lokal research; nama DB wajib `saham_signal_<mode>`, query override ditolak |
| `REDIS_URL` | Redis localhost:6379/0 dengan password lokal research sesuai env contoh; hanya `redis`/`rediss`, query override ditolak |
| `REDIS_NAMESPACE` | `saham-signal:research:`; wajib sama dengan mode |
| `CORS_ORIGINS` | JSON array origin HTTP(S) eksplisit, default localhost/127.0.0.1:3000; wildcard/path ditolak; `[]` mematikan CORS |
| `READINESS_TIMEOUT_SECONDS` | 3; rentang 0.1–10 |
| `SESSION_SECRET` | wajib 32+ karakter di paper/live; dirahasiakan pada repr/error |
| `PILOT_ACCOUNT_ID` | wajib di paper/live; provisioning/auth mengikuti SS-023 |

Nama database/namespace adalah validasi konfigurasi, **bukan bukti batas izin**.
Deployment wajib memakai database, role/credential, dan instance Redis terpisah per
mode sesuai ADR-0001/SS-006. Nomor logical Redis DB saja tidak cukup. Mode paper/live
tidak mengaktifkan fitur live apa pun. Bootstrap hanya boleh diakses lokal sebelum
autentikasi/otorisasi SS-023 dan gerbang terkait dibuktikan.

CORS mengizinkan GET/PUT dan header Accept/Content-Type/Idempotency-Key; credentials hanya aktif
saat fixture research diaktifkan, untuk origin lokal eksplisit yang dikonfigurasi.
Header `X-Request-ID` dibuat server, tersedia pada sukses/error dan diekspos untuk
origin yang diizinkan. Error HTTP/validasi/internal mengikuti
`packages/contracts/v1/schema.json#/$defs/ErrorResponse`:
envelope `contract_version`, `as_of` UTC, `mode`, `data_origin`, `quality`, dan
`data: {code, request_id, retryable, fields}`. Error research/paper berlabel simulation;
error live berlabel market dengan kualitas/feed unavailable, tanpa klaim feed hidup.
Respons 429/503 memberi `Retry-After: 3`. Tidak mengembalikan pesan exception,
input mentah, atau data internal. `fields` kosong untuk endpoint bootstrap.
Preflight CORS ditangani middleware transport; respons penolakan preflight bukan
respons error bisnis. Skema kontrak SS-002 tetap sumber kebenaran; test memvalidasi
payload error aktual terhadap schema tersebut, tanpa menyalin schema besar ke package.

## Batas modul dan worker

```text
src/saham_signal/
  domain/       Mode dan aturan murni; hanya standard library
  application/  Use case dan port DependencyProbe; tanpa FastAPI/storage
  adapters/     Implementasi PostgreSQL/Redis
  config.py     Settings tervalidasi yang dibagi API/worker
  transport/    Factory HTTP, lifespan, error, CORS dan composition root
```

Transport/adapters bergantung pada application/domain. Worker SS-005 memasang package
ini (contoh `uv pip install ./services/api` dari root atau wheel hasil `uv build`),
lalu mengimpor `saham_signal.*`; tanpa manipulasi `sys.path` atau duplikasi domain.
Lifecycle SS-005 memakai wheel ini melalui `python -m saham_signal.worker`.
Setup, heartbeat, shutdown, dan aturan retry tersedia di [panduan worker](../worker/README.md).
Belum ada job bisnis/vendor atau sinyal.

## Verifikasi

Dari `services/api`:

```powershell
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest
uv build
```

Test mencakup health, dependency gagal/timeout/pulih, lifecycle readiness, kontrak error,
CORS allow/deny, mode/isolasi/secret, serta kegagalan startup proses nyata. Probe
diganti test double untuk tes deterministik; integrasi server PostgreSQL/Redis hidup
tersedia melalui `node scripts/check-local-infra.mjs` dari root dan CI SS-006.
Matriks CI lintas service tersedia dalam [panduan SS-007](../../docs/RUNTIME-CI.md),
termasuk smoke wheel terpasang tanpa dependency dev. Dependency langsung dipin exact,
transitif dan hash artifact terkunci pada `uv.lock`; gunakan `--locked` agar drift gagal.

Baseline FastAPI 0.162.5/Python 3.13.18 mengikuti ADR. uv adalah tooling MIT/Apache-2.0;
FastAPI, Uvicorn, Pydantic/settings, Redis client, HTTPX, pytest, mypy, jsonschema dan
Hatchling memakai MIT/BSD; Ruff MIT. Psycopg dan binary distribusinya LGPL-3.0
(library libpq/OpenSSL memiliki notice sendiri). Redis **client** MIT tidak mengubah
pilihan lisensi Redis **server** pada ADR. Lockfile dan metadata upstream perlu
ditinjau ulang saat upgrade; pin bukan klaim bebas vulnerability.

Referensi implementasi: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/),
[psycopg async/Windows](https://www.psycopg.org/psycopg3/docs/advanced/async.html).
## Penyimpanan SS-010

SS-022 menambah [inbox alert persisten](../../docs/market-data/in-app-alerts.md) pada
`GET /api/v1/alerts`. Jalankan migrasi `004_alerts.sql` sebelum memakai versi ini;
command posisi dan alert terkait sekarang commit atomik. Kontrak Alert v1 tetap sama.

Migrasi PostgreSQL dijalankan eksplisit dengan `uv run --locked python -m saham_signal.migrate`.
Lihat [panduan persistence](../../docs/PERSISTENCE.md) untuk schema append-only,
repository transaksi, isolasi role/akun/mode, retensi dan pengujian PostgreSQL.

## Keamanan SS-023

Sesi admin bertanda tangan, batas HTTP/WS, TLS dan kebijakan ekspor/penghapusan
dijelaskan dalam [panduan keamanan](../../docs/SECURITY.md). Konfigurasi research
lokal tetap kompatibel; gunakan sesi bertanda tangan untuk akses dengan TLS.

## Berita internal SS-024

[Panduan ingest, izin dan ablation](../../docs/market-data/internal-news.md) menjelaskan
migrasi `005_internal_news.sql`, job operator `python -m saham_signal.news_ingest`,
registry tepercaya dan DSN `NEWS_DATABASE_URL` role khusus research. Tidak ada fetch
atau pemanggilan LLM; sumber produksi dan integrasi ranking belum diaktifkan.
