# Infrastruktur lokal — SS-006

PostgreSQL 18.7 dan Redis 8.2.11 berjalan melalui Docker Compose. API dan worker
tetap proses host dari wheel backend yang sama. Tidak ada feed, migrasi bisnis,
deployment produksi, atau kelulusan gerbang G0/G1/G2/G3 pada setup ini.

## Fresh clone dan startup

Prasyarat: Git, Node.js 22+ (baseline repo 24.22.3), Docker Engine Linux lokal dan
Compose v2.20+ (`up --wait`), serta uv 0.13.7/Python 3.13.18 untuk backend.
Pada Windows jalankan Docker Desktop dengan Linux containers terlebih dahulu.
Linux/macOS memerlukan socket lokal `/var/run/docker.sock`; socket rootless/custom
tidak didukung wrapper ini. Semua perintah berikut dari root repo:

```powershell
node scripts/local-infra.mjs check research
node scripts/local-infra.mjs up research
node scripts/local-infra.mjs status research
cd services/api
uv sync --locked
Copy-Item .env.example .env
uv run --locked python -m saham_signal.transport.http --env-file .env
```

`up` menunggu kedua healthcheck sehat (maksimum 120 detik). Shell lain:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

`/ready` harus 200 dengan `postgresql: true` dan `redis: true`. Probe memakai
credential aktual untuk `SELECT 1` dan `PING`. Bila salah satu layanan berhenti,
credential salah, atau timeout, `/ready` 503 `DATA_UNAVAILABLE`; `/health` tetap 200.
Readiness otomatis pulih pada request berikutnya setelah dependency sehat.
Jalankan worker mengikuti [panduan worker](../services/worker/README.md).

## Konfigurasi dan isolasi

Tanpa file env tambahan, wrapper menggunakan default lokal di tabel. Opsional:
salin `infra/.env.example` ke `infra/.env.research`, `.env.paper`, atau `.env.live`.
File hanya menerima empat key contoh, bentuk `KEY=value` tanpa quote/interpolasi.
Port 1024–65535; password 12–128 karakter `A-Z a-z 0-9 _ -` agar aman di DSN.
Username/database tetap `saham_signal_<mode>`; password dan port dapat diubah.
File lokal diabaikan Git. Nilai `LOCAL_*` environment proses tidak dibaca.

| Mode lokal | Project Compose | PostgreSQL / Redis host | Password PG / Redis | Namespace |
|---|---|---|---|---|
| research | saham-signal-local-research | 5432 / 6379 | local_only_research / local_redis_research | saham-signal:research: |
| paper | saham-signal-local-paper | 5433 / 6380 | local_only_paper / local_redis_paper | saham-signal:paper: |
| live | saham-signal-local-live | 5434 / 6381 | local_only_live / local_redis_live | saham-signal:live: |

`node scripts/local-infra.mjs up paper` membuat instance PostgreSQL, instance Redis,
network, dan volume terpisah. Mode `live` di sini juga **hanya sandbox lokal**, tanpa
data produksi atau akses broker. Semua port bind `127.0.0.1`. Database/role per mode
berada di instance PostgreSQL terpisah; logical Redis DB selalu 0 karena isolasinya
instance, bukan nomor DB. Prefix namespace tetap wajib pada key/channel aplikasi.
Role bootstrap PostgreSQL adalah administrator instance lokalnya; ini bukan template
least-privilege produksi. Deployment harus menyediakan secret/resource sendiri.

API/worker memakai environment server sendiri, tidak otomatis membaca env Compose.
Set `APP_MODE`, `DATABASE_URL`, `REDIS_URL`, dan `REDIS_NAMESPACE` sesuai mode/port/
password yang dipilih. Contoh paper:

```dotenv
APP_MODE=paper
DATABASE_URL=postgresql://saham_signal_paper:local_only_paper@127.0.0.1:5433/saham_signal_paper
REDIS_URL=redis://:local_redis_paper@127.0.0.1:6380/0
REDIS_NAMESPACE=saham-signal:paper:
SESSION_SECRET=local_sandbox_only_at_least_32_characters
PILOT_ACCOUNT_ID=local-sandbox
```

Paper/live mewajibkan session secret dan akun pilot sesuai validasi backend; ini
tidak mengaktifkan autentikasi, sinyal, alert, atau trading. Bila port bentrok,
ubah port file infra lalu ubah DSN API/worker. Mengganti password PostgreSQL pada
volume yang sudah diinisialisasi tidak mengganti password role: ubah lewat SQL
administratif atau lakukan reset lokal eksplisit bila data boleh dibuang.

## Shutdown dan reset lokal

```powershell
node scripts/local-infra.mjs stop research
node scripts/local-infra.mjs up research
node scripts/local-infra.mjs down research
```

`stop` menghentikan proses; `down` menghapus container/network. Keduanya menyimpan
volume. PostgreSQL 18 memakai mount `/var/lib/postgresql`; Redis memakai `/data`
dengan AOF agar restart/recreate tidak membuang data. Ini bukan strategi backup.

Untuk **membuang seluruh data sandbox research** secara sengaja:

```powershell
node scripts/local-infra.mjs reset research --confirm-local-reset=saham-signal-local-research
node scripts/local-infra.mjs up research
```

Reset menolak konfirmasi mode lain, project/file/host tambahan, dan volume tanpa
label ownership lokal yang sesuai. Wrapper memakai endpoint lokal tetap (Windows:
pipe Docker Desktop Linux; POSIX: socket di atas), project `saham-signal-local-<mode>`,
manifest tetap dan named volumes milik project itu saja. `DOCKER_HOST`,
`DOCKER_CONTEXT`, seluruh `COMPOSE_*`, serta DSN environment dibuang; file `.env`
otomatis Compose dinonaktifkan. Tidak ada `prune`, remote DSN, external volume,
bind mount data, atau wildcard delete. Reset tidak menyasar infrastruktur produksi;
jangan simpan data produksi dalam sandbox/volume berlabel lokal ini.

## Verifikasi

```powershell
node --test scripts/local-infra.test.mjs
node scripts/local-infra.mjs check research
node scripts/local-infra.mjs check paper
node scripts/local-infra.mjs check live
node scripts/check-local-infra.mjs
```

Integrasi terakhir memerlukan `uv sync --locked` di `services/api`. Jalankan pada
sandbox research/paper disposable: test membuat tabel `local_infra_smoke` dan key
sentinel, me-recreate container untuk membuktikan persistence, memutus PostgreSQL
dan Redis bergantian untuk membuktikan readiness 503/pulih, menguji credential salah,
serta membuktikan tabel/database/key research tidak ada di instance paper. Test
menghapus sentinel ketika sukses dan `down` kedua stack di akhir; volume tetap ada.
CI [local-infra.yml](../.github/workflows/local-infra.yml) menjalankan test nyata
di Linux lalu reset volume CI dengan konfirmasi eksplisit. Ini validasi SS-006;
matriks quality checks lintas service yang lebih luas mengikuti SS-007.

## Image dan lisensi

Image resmi dikunci tag exact **dan digest multi-platform** di `compose.yaml`,
diverifikasi dari registry pada 13 November 2026. PostgreSQL memakai PostgreSQL
License; Redis 8.2.11 menawarkan RSALv2/SSPLv1/AGPLv3, dengan pilihan **AGPLv3**
yang diterima ADR-0001. Redis server tidak memakai lisensi MIT client Python.
Image tetap membawa notice/lisensi OS dan library lain. Pertahankan notice dan
akses source upstream sesuai lisensi saat mendistribusikan image; distribusi
publik/berbayar ditinjau sebelum G3. Tidak ada modifikasi server pada setup ini.
Upgrade wajib memperbarui tag/digest dan mengulang integrasi serta audit notice.

Referensi: [image PostgreSQL dan volume 18+](https://hub.docker.com/_/postgres),
[image Redis](https://hub.docker.com/_/redis),
[lisensi Redis 8.2](https://github.com/redis/redis/blob/8.2/LICENSE.txt),
[healthcheck Compose](https://docs.docker.com/compose/how-tos/startup-order/),
[autentikasi Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/security/).
