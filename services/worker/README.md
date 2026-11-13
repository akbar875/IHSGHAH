# Worker

SS-005 menyediakan lifecycle worker dalam wheel `saham-signal-backend` yang sama
dengan API. Entrypoint `saham_signal.worker` dan runner application mengimpor
`Settings`/`Mode` backend; tidak ada salinan aturan domain atau manipulasi `sys.path`.
Direktori ini berisi panduan operasional proses worker, bukan package kedua.

## Menjalankan dari fresh clone

Prasyarat sama dengan [API](../api/README.md): uv **0.13.7**, Python **3.13.18**
(diunduh uv bila perlu). Dari root repo:

```powershell
cd services/api
uv sync --locked
Copy-Item ../worker/.env.example .env.worker
uv run --locked python -m saham_signal.worker --env-file .env.worker
```

Hentikan dengan Ctrl+C (Windows/POSIX) atau SIGTERM (POSIX). Untuk smoke portabel:
`uv run --locked python -m saham_signal.worker --stop-after 0.3`.
Worker mulai tanpa PostgreSQL/Redis karena belum ada job, vendor, ingest, sinyal,
alert, atau resource eksternal yang dibuka. Heartbeat hanya membuktikan proses hidup,
bukan readiness feed/database/model maupun kelulusan G0/G1/G2/G3.

Deployment memasang wheel backend yang sama dengan API, lalu menjalankan
`python -m saham_signal.worker`; gunakan environment/secret store tanpa file lokal.
Tidak ada dependency atau lockfile kedua; build dan CI memakai `services/api`.

## Konfigurasi

Konfigurasi dibaca sekali saat startup dan dibekukan. Environment proses mengalahkan
file yang diminta eksplisit melalui `--env-file`; tanpa flag, `.env` tidak dibaca.
Mode, DSN, namespace dan persyaratan paper/live mengikuti
[validasi backend](../api/README.md#konfigurasi-dan-isolasi).

| Variable | Default | Batas |
|---|---|---|
| `WORKER_HEARTBEAT_SECONDS` | 30 | 0.05–3600, finite |
| `WORKER_MAX_ATTEMPTS` | 3 | 1–10, termasuk percobaan pertama |
| `WORKER_RETRY_SECONDS` | 1 | 0.05–60, finite; backoff tetap |
| `WORKER_SHUTDOWN_SECONDS` | 10 | 0.05–60, finite; waktu drain |

Log JSON stdout berisi hanya event tetap, mode, attempt dan waktu UTC. Startup,
heartbeat, retry/failure, stopping, timeout dan stopped tercatat tanpa repr settings,
pesan exception, DSN, kredensial, atau payload job. Konfigurasi invalid keluar 2
dengan pesan generik; kegagalan runtime/retry habis keluar 1; shutdown normal keluar 0.

## Shutdown, retry dan efek samping

Runner `application.worker.run_worker` menjalankan satu coroutine pekerjaan pada
satu waktu. Saat stop diminta, tidak menerima pekerjaan berikutnya atau retry baru;
backoff dapat dihentikan segera. Pekerjaan aktif diberi waktu drain, lalu dibatalkan
dan ditunggu cleanup `finally`-nya. Heartbeat memiliki task sendiri, semua task
dibersihkan sebelum stopped. Job mendatang wajib memakai async I/O dengan timeout,
mematuhi cancellation, dan menutup resource di `finally`; kerja CPU/blocking harus
dipisah. Supervisor tetap perlu batas terminate untuk proses yang tidak kooperatif.

Hanya `RetryableWorkError` yang diulang sampai batas attempt. Job hanya boleh
melemparnya jika belum ada efek committed, atau jika transaksi/durable idempotency
key memastikan pengulangan tidak menggandakan efek. Error lain (termasuk hasil commit
yang tidak diketahui) langsung menghentikan worker tanpa retry otomatis.
Bootstrap tidak memiliki job berefek samping, antrean persisten, atau dedup lintas
restart. Jangan menganggapnya jaminan exactly-once. Implementasi outbox/dedup durable
untuk alert/job nyata mengikuti modul persistence/integrasi terkait sesuai ADR.

## Verifikasi

Dari `services/api`:

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest
uv build
```

Test mencakup proses nyata start/heartbeat/stop, konfigurasi invalid tanpa secret,
SIGTERM pada POSIX, retry habis/pulih, error non-retryable, stop saat backoff,
drain/cancel dan cleanup pekerjaan aktif. Test double yang gagal sebelum commit
kemudian sukses menghasilkan satu efek; tidak ada koneksi vendor/data berlisensi.
