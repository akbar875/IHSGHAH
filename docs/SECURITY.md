# Keamanan dan data pribadi — SS-023

## Hasil inspeksi dan keputusan

Issue #23 melengkapi ADR-0001: satu pemilik dengan akun persisten yang
diprovisikan administrator, tanpa registrasi publik. SS-004/010/017 menyediakan
error tersanitasi, scope server, PostgreSQL RLS dan cache bertanda akun/mode.
Kekurangan sebelumnya: sesi fixture statis, tanpa expiry/rate limit/batas payload,
serta belum ada prosedur TLS dan data pribadi. SS-023 menutup batas tersebut;
G0–G3 tetap belum lulus dan tidak mengaktifkan feed/broker/pilot produksi.

## Provisioning dan otorisasi

Set `SESSION_SECRET` acak minimal 32 karakter dari secret manager, `PILOT_ACCOUNT_ID`
persisten, dan `SESSION_TTL_SECONDS` (default 3600, maksimum 28800). Jalankan
`python -m saham_signal.application.security` pada terminal administrator dengan
environment tersebut untuk menghasilkan cookie. Keluaran ini adalah kredensial:
jangan masukkan ke Git, log CI, URL, browser storage atau bundle. Pasang sebagai
cookie host-only lewat kanal administrasi tepercaya dengan `HttpOnly`, `SameSite=Strict`,
`Path=/`, `Max-Age` dan `Secure` pada TLS. Tidak ada endpoint publik penerbit sesi.

Cookie HMAC-SHA256 mengikat nonce acak, expiry, akun dan mode. Tidak memuat ID akun.
HTTP dan WebSocket memakai verifier yang sama; stream ditutup saat sesi habis.
Rotasi `SESSION_SECRET` dan restart seluruh proses mencabut semua sesi termasuk
stream aktif pada iterasi berikutnya. Logout lokal menghapus cookie; pencabutan
segera atas cookie yang dicuri memerlukan rotasi secret. Tidak ada refresh otomatis.
Jam server harus tersinkronisasi. Akun/mode dari query atau payload tidak dipercaya.
Semua resource personal melalui scope server dan RLS; runtime DB bukan superuser,
owner tabel atau role `BYPASSRLS`.

Tanpa `SESSION_SECRET`, token fixture lama hanya diterima pada research lokal
tanpa TLS deployment. Dengan secret, token fixture mentah selalu ditolak.
`MARKET_FIXTURE_ENABLED` tetap research-only: sesi valid bukan izin membuka
API market paper/live yang belum diintegrasikan. Token fixture masih diperlukan
untuk kompatibilitas konfigurasi fixture, tetapi bukan kredensial sesi bertanda tangan.

## TLS, batas dan log

Untuk akses selain development loopback, set `DEPLOYMENT_TLS_REQUIRED=true`
dan `CORS_ORIGINS` HTTPS eksplisit. Jalankan API dengan sertifikat tepercaya:

```sh
python -m saham_signal.transport.http --ssl-certfile /run/secrets/tls.crt --ssl-keyfile /run/secrets/tls.key
```

Entrypoint bind loopback; gunakan gateway HTTPS dengan upstream HTTPS yang memverifikasi
sertifikat API. API tidak mempercayai `X-Forwarded-*`. HTTP/WS plaintext ditolak,
HTTPS mendapat HSTS. Gateway mengalihkan HTTP publik ke HTTPS, membatasi koneksi,
timeout body/header 10 detik, frame WS 64 KiB dan body 64 KiB. Jangan membuka
port backend/database/Redis ke publik. Sertifikat dan secret berada di luar repo.

Budget tetap per proses/mode untuk satu pilot: default 120 HTTP/handshake per menit,
termasuk request gagal; pesan WS memakai budget 120/menit tersendiri. Balasan HTTP
429 memakai `Retry-After: 60`. Identitas/IP palsu tidak menciptakan bucket baru.
`RATE_LIMIT_PER_MINUTE` mengatur budget; health/readiness tidak menghabiskannya.
Multi-process harus memakai limit agregat pada gateway, karena limit aplikasi
bukan limiter terdistribusi. Gateway juga membatasi koneksi WS aktif dan slow clients.
`REQUEST_MAX_BYTES` default 65536 membatasi body streaming dan pesan WS sebelum JSON
diproses. JSON Schema menolak extra fields, nilai nominal/lot dan bentuk input invalid.

Entrypoint menonaktifkan access log Uvicorn (URL/query mungkin berisi rahasia).
Filter server membuang access record dan mengganti traceback dengan pesan tetap;
error API tidak memantulkan input/exception. Log aplikasi hanya field allowlist
seperti request ID, event, mode dan status. Jangan log cookie, Authorization, body,
DSN, environment atau dokumen. Terapkan redaction yang sama di gateway/APM;
nonaktifkan capture body/header/exception locals. `MARKET_DATA_API_KEY` hanya server,
tidak pernah `NEXT_PUBLIC_*`. CI memeriksa batas environment web.

## Ekspor, penghapusan dan retensi

Pemilik meminta ekspor melalui administrator terautentikasi. Bekukan penulisan,
verifikasi akun/mode, lalu gunakan transaksi read-only repeatable-read dengan
`Journal._scope` pada role runtime untuk mengekspor JSON/CSV: seluruh versi
`manual_position_events` (command dan snapshot termasuk fill/plan),
`personal_preferences` (watchlist/profil), `in_app_alerts`, `alert_gates` dan journal
personal. Setiap SELECT wajib `WHERE mode=:mode AND user_id=:account`; jangan
sertakan market data berlisensi atau akun lain. Kirim terenkripsi lewat kanal
pribadi, catat hanya ID permintaan, dan hapus salinan ekspor maksimal 24 jam.
Endpoint daftar posisi saat ini hanya snapshot terbaru, bukan ekspor ledger lengkap.

Retensi default pilot: ledger/konfigurasi selama akun aktif; alert/gate maksimal
30 hari, log operasional tersanitasi 14 hari, backup terenkripsi rolling 30 hari.
Administrator melakukan review retensi mingguan. Tidak ada janitor otomatis;
prosedur operator wajib tersedia sebelum pilot. Retensi data vendor mengikuti kontrak
SS-008, bukan kebijakan personal ini.

Penghapusan atas permintaan pemilik: revoke sesi, hentikan API/worker dan verifikasi
identitas serta cakupan. Runtime **tidak** diberi DELETE/TRUNCATE atau kemampuan
menonaktifkan trigger append-only. Administrator melakukan rebuild database mode
di lingkungan terisolasi dari ekspor yang mengecualikan akun tersebut, beserta
alert/gate, preferensi dan journal personalnya. Uji akun lain tetap utuh, lalu
switch database; hapus database lama, cache akun dan ekspor sementara. Untuk pilot
satu akun tanpa data lain, seluruh database/volume mode dapat dimusnahkan oleh
operator setelah verifikasi. Jangan menjalankan operasi ini melalui request aplikasi.
Selesaikan maksimal 30 hari, kecuali kewajiban retensi yang disampaikan ke pemilik.
Backup lama kedaluwarsa maksimal 30 hari; restore wajib menerapkan daftar penghapusan
sebelum service dibuka. Catat bukti tanpa payload posisi. Tidak ada penghapusan data
nyata yang dilakukan oleh implementasi issue ini.

## Dokumen eksternal

Fetch URL, upload dokumen, eksekusi prompt/tool dan endpoint action dokumen
dinonaktifkan: tidak ada rute atau client fetch dokumen dalam API/worker saat ini.
URL pada input personal ditolak schema. Isi dokumen/berita adalah data tidak
tepercaya dan tidak boleh menjadi instruksi, kode, tool call atau otorisasi trading.
SS-024 harus mempertahankan worker tanpa kemampuan eksekusi tool/action, egress
deny-by-default dan tanpa kredensial posisi. Sebelum fetch ditambahkan, wajib ada
allowlist HTTPS hostname/port/path, resolusi DNS/IP publik pada setiap koneksi,
penolakan loopback/private/link-local/metadata IPv4/IPv6, redirect dimatikan,
timeout/ukuran/MIME dan sandbox parser. Jangan menambahkan generic URL proxy.

Rujukan: [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
dan [OWASP SSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).

## Bukti penerimaan

`tests/test_security.py` menguji signature/expiry/rotasi/akun/mode, akses personal
lintas akun ditolak, CSRF, query injection, batas payload, 429, TLS, WS, cache/alert
dan log. Suite persistence/positions/preferences/alerts menguji scope PostgreSQL RLS
dengan role runtime. Jalankan ruff, mypy, pytest dengan `PERSISTENCE_TEST_DSN` disposable,
kontrak, scaffold dan pemeriksaan secret boundary sebelum integrasi pilot.
