# CI runtime dan quality checks

SS-007 menjalankan `.github/workflows/runtime-ci.yml` pada setiap push, pull request,
dan pemanggilan manual. Tidak ada filter path: perubahan kontrak, konfigurasi, maupun
workflow tetap memeriksa seluruh bootstrap. Lima reusable workflow dijalankan paralel:

| Kelompok | Pemeriksaan | Perintah lokal dari root |
|---|---|---|
| Scaffold | Backlog, dependency, tautan dokumen, dry run publisher | `node scripts/check-scaffold.mjs` dan `node scripts/publish-issues.mjs` |
| Contracts | Schema/fixture JavaScript dan Python | Lihat perintah di bawah |
| Web | Generated kontrak, ESLint, TypeScript, build Next.js, browser dashboard Chromium | `npm ci --ignore-scripts --prefix apps/web`, `npm --prefix apps/web run check`, lalu dari apps/web `npx playwright install chromium` dan `npm test` |
| Backend | Ruff lint/format, mypy, pytest API/worker, build wheel, smoke wheel | Lihat perintah di bawah |
| Infrastructure | Validasi konfigurasi/mode, DB/cache nyata, persistensi, outage/recovery, isolasi | Lihat perintah di bawah |
| Paper acceptance | Gabungkan XML pytest dan JSON browser menjadi receipt 12 skenario PRD | [Panduan SS-026](market-data/paper-integration.md) |

Job web dipin ke Ubuntu 24.04 yang didukung Chromium/Playwright 1.58.2; tidak
mengikuti perpindahan `ubuntu-latest` ke OS yang belum didukung browser test.

Job **Runtime quality gate** memakai `always()` dan memerlukan hasil `success` dari
kelima kelompok dan job **Paper acceptance qualification** setelah backend/web.
Status gagal, cancelled, atau skipped membuat gate gagal. Tidak ada
`continue-on-error`, secret vendor, atau `secrets: inherit`. Permission workflow hanya
`contents: read`; checkout tidak dipakai oleh job gate. Push/PR baru membatalkan run
lama untuk ref/PR yang sama. Job komponen dibatasi 15 menit, penggabungan receipt
tiga menit, gate satu menit. Receipt sintetik tidak mengaktifkan paper live/G2;
evidence acceptance hilang, skipped, gagal atau flaky menahan quality gate.

Untuk mencegah merge saat CI gagal, pemilik repo perlu memilih **Runtime quality gate**
sebagai required status check dalam ruleset/branch protection `main`. Workflow membuat
status PR gagal; workflow sendiri tidak mengubah aturan merge repository.

## Runtime dan dependency

Node mengikuti `apps/web/.nvmrc` (24.22.3), Python mengikuti
`services/api/.python-version` (3.13.18), dan uv dipin 0.13.7. npm menggunakan
`npm ci --ignore-scripts`, backend memakai `uv sync --locked`/`uv run --locked`.
Validasi Python kontrak memakai daftar versi exact pada
`packages/contracts/requirements-test.txt`.

Integrasi memerlukan Docker Engine Linux dengan Compose v2, memakai image PostgreSQL/
Redis yang dipin digest di Compose SS-006. Credential sementara CI hanya untuk stack
lokal yang disposable. Tidak ada koneksi vendor atau data pasar berlisensi.
Fixture kontrak dan payload smoke berlabel `simulation`; sentinel infrastruktur hanya
untuk persistensi/isolasi. Kelulusan CI bukan kelulusan G0/G1/G2/G3.

## Kontrak

```powershell
npm ci --ignore-scripts --prefix packages/contracts
npm --prefix packages/contracts run check
# Gunakan Python 3.13.18 dalam virtualenv lokal.
python -m pip install -r packages/contracts/requirements-test.txt
python packages/contracts/test/check_python.py
```

## Backend dan paket distribusi

Dari `services/api`, dengan uv 0.13.7:

```powershell
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked ruff check ../../scripts/check-backend-smoke.py
uv run --locked ruff format --check ../../scripts/check-backend-smoke.py
uv run --locked mypy
uv run --locked pytest
uv build --no-sources
uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file ../../.work/runtime-requirements.txt
uv venv ../../.work/backend-smoke
uv pip sync --require-hashes --python ../../.work/backend-smoke/Scripts/python.exe ../../.work/runtime-requirements.txt
uv pip install --python ../../.work/backend-smoke/Scripts/python.exe --no-deps dist/saham_signal_backend-0.1.0-py3-none-any.whl
../../.work/backend-smoke/Scripts/python.exe -I ../../scripts/check-backend-smoke.py
```

Buat `.work` di root bila belum ada. Pada POSIX gunakan `bin/python` sebagai pengganti
`Scripts/python.exe`; workflow memakai direktori sementara runner. Wheel smoke memasang
hanya dependency runtime dari lockfile, kemudian wheel tanpa resolusi dependency baru.
Script memakai interpreter isolated (`-I`) dan working directory sementara, sehingga
source editable maupun dependency dev tidak menyembunyikan cacat packaging.

Smoke menguji HTTP `/health` 200, `/ready` 503 dengan `DATA_UNAVAILABLE` dan origin
simulation saat DB/cache tidak tersedia, serta proses worker start/heartbeat/stop.
Port HTTP dipilih dinamis; dependency diarahkan ke port lokal tanpa listener. Proses
API dibersihkan bahkan saat gagal, dan setiap operasi memiliki timeout. Test suite
backend juga menguji SIGTERM di Linux; test ini dilewati pada Windows.

## Infrastruktur nyata

Dengan Docker lokal aktif, dari root:

```powershell
services/api/.venv/Scripts/ruff.exe check infra/probe.py
services/api/.venv/Scripts/ruff.exe format --check infra/probe.py
node --test scripts/local-infra.test.mjs
node scripts/local-infra.mjs check research
node scripts/local-infra.mjs check paper
node scripts/local-infra.mjs check live
node scripts/check-local-infra.mjs
```

Pada POSIX gunakan `services/api/.venv/bin/ruff`. Integrasi terakhir secara eksplisit
menjalankan, menghentikan, dan membuat ulang stack **lokal research/paper**; gunakan
lingkungan development disposable sesuai [panduan infra](../infra/README.md).
CI juga memeriksa port/password paper yang dikonfigurasi ulang, lalu mereset volume
CI dengan konfirmasi nama project pada langkah `always()`. Tidak ada stack live
yang dijalankan oleh pemeriksaan ini.

## Menelusuri kegagalan

Buka run **Runtime CI**, lalu kelompok dan langkah pertama yang gagal. Jalankan ulang
perintah lokal kelompok tersebut dengan versi runtime/lockfile yang sama. Gate hanya
merangkum hasil; penyebab terperinci tersedia pada log masing-masing kelompok.
Perubahan workflow perlu diperiksa pada run pull request, termasuk integrasi Linux
yang memerlukan Docker dan pengujian SIGTERM.
