# API FastAPI

Fondasi SS-004: package `saham-signal-backend` yang dapat dipasang API dan worker,
konfigurasi startup tervalidasi, probe dependency, CORS dan error contract SS-002.
Belum ada endpoint bisnis, autentikasi, ingest, sinyal, migrasi, atau alert.

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
Compose/database/migrasi mengikuti SS-006/010; belum dibutuhkan untuk health/smoke.
Swagger lokal di `/docs`; `/openapi.json` mendokumentasikan endpoint bootstrap saja,
terpisah dari kontrak bisnis rencana di `packages/contracts/v1/openapi.json`.

## Konfigurasi dan isolasi

Settings dibekukan saat factory dipanggil sebelum server menerima traffic. Mode
tidak dapat diganti lewat header/query. Startup gagal dengan pesan generik tanpa
mencetak nilai environment bila tidak valid.

| Variable | Default / validasi |
|---|---|
| `APP_MODE` | `research`; hanya `research`, `paper`, `live` |
| `DATABASE_URL` | PostgreSQL lokal research; nama DB wajib `saham_signal_<mode>`, query override ditolak |
| `REDIS_URL` | `redis://127.0.0.1:6379/0`; hanya `redis`/`rediss`, query override ditolak |
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

CORS mengizinkan GET dan header Accept/Content-Type saja; credentials dimatikan.
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
Worker lifecycle/job belum diimplementasikan pada SS-004.

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
dan matriks CI lintas service mengikuti SS-006/007. Dependency langsung dipin exact,
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
