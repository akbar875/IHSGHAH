# Arsitektur awal

Status: usulan perencanaan dari PRD, belum menjadi implementasi atau keputusan versi dependency.

## Komponen

| Lokasi | Tanggung jawab | Batas |
|---|---|---|
| `apps/web` | Dashboard, detail, posisi manual, status data, alert | Tidak menerima rahasia vendor atau dokumen berita internal |
| `services/api` | REST/WebSocket, autentikasi, konfigurasi, posisi, query snapshot | Modular monolith; kontrak berversi |
| `services/worker` | Ingest, fitur, sinyal, risiko, replay, pengiriman alert | Berbagi modul domain backend; bukan duplikasi aturan di UI |
| PostgreSQL | Event, aturan efektif, posisi/fill, audit, eksperimen | Point-in-time; uang desimal/integer presisi tetap |
| Redis | Cache, pub/sub | Bukan sumber audit/posisi otoritatif |
| Object storage | Raw data dan artefak riset/model | Hak vendor dan retensi harus disepakati |

## Aliran data

```text
Vendor -> adapter -> normalisasi/event log -> fitur -> model + risiko
       -> snapshot sinyal -> API / WebSocket -> web

Informasi resmi/berita -> ekstraksi + deduplikasi -> penyimpanan point-in-time
                     -> fitur internal (jalur terpisah dari ingest pasar)

Fill pengguna -> posisi nyata -> pemantauan risiko -> alert -> konfirmasi exit
```

## Invarian kontrak

- Metadata respons: `as_of`, `mode`, kualitas data, dan versi kontrak.
- Timestamp UTC dengan `event_time`, `provider_time` bila tersedia, `received_at`, `available_at`, `processed_at`, dan sequence.
- Snapshot awal + delta berurutan; reconnect melakukan resinkronisasi sebelum status live.
- Probability nullable; return, horizon, harga acuan, biaya, dan unit lot eksplisit.
- Sinyal WATCH -> READY -> EXPIRED/CANCELLED terpisah dari posisi OPEN/PARTIAL -> EXIT_REQUESTED -> CLOSED.
- Transisi deterministik, idempotent, dan dapat direplay; audit perubahan append-only.
- Isolasi akun serta namespace research/paper/live berlaku pada penyimpanan, cache, stream, dan alert.

## Keputusan yang masih terbuka

Vendor dan hak data, anggaran, akun pilot/multi-user, versi dependency, library chart berlisensi sesuai, kanal push, tarif broker, serta ambang validasi belum ditetapkan. Rekam keputusan melalui [ADR](decisions/README.md), jangan menganggap placeholder konfigurasi sebagai nilai produksi.

## Gerbang rilis

G0 memverifikasi hak dan kualitas data. G1 memverifikasi baseline/holdout. G2 memerlukan observasi paper prospektif dan toleransi yang dibekukan sebelumnya. G3 memerlukan kesiapan operasional serta kajian distribusi produk. Detail dan kriteria otoritatif berada pada PRD bagian 10; selesainya issue teknis tidak otomatis meluluskan gerbang.
