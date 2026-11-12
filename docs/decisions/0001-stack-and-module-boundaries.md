# ADR-0001: Stack, batas modul, konfigurasi, dan akun pilot

- Status: Proposed — siap ditinjau pemilik repo; belum Accepted
- Tanggal: 2026-11-12 (Asia/Jakarta)
- Issue: [#1 / SS-001](https://github.com/akbar875/IHSGHAH/issues/1)
- Pengambil keputusan: pemilik repo; penerimaan dicatat melalui review atau konfirmasi eksplisit sebelum status diubah
- Acuan: [PRD](../PRD-Saham-Signal.md) bagian 11, 12, 13, dan 16

## Konteks

Repositori baru berisi scaffold. Belum ada runtime aplikasi, dependency terpasang, vendor, atau hasil validasi strategi. Issue #1 membekukan fondasi agar kontrak dan bootstrap tidak memilih stack maupun batas domain yang berbeda. Keputusan ini tidak meluluskan G0/G1/G2/G3.

Pilot mengutamakan pengoperasian sederhana, aturan deterministik yang sama untuk riset dan pemantauan, serta pemisahan data pengguna. Beban feed dan anggaran belum diketahui sehingga pemecahan menjadi microservices belum beralasan.

## Keputusan

### Stack dan baseline versi

Gunakan Next.js App Router dengan TypeScript untuk web, Python/FastAPI modular monolith untuk API, proses worker Python terpisah dari server HTTP, PostgreSQL sebagai penyimpanan otoritatif, serta Redis untuk cache dan pemberitahuan perubahan. API dan worker dirilis dari kode backend yang sama.

Baseline berikut diverifikasi pada 12 November 2026 dari dokumentasi penerbit dan metadata paket. Ini pilihan awal, bukan klaim bahwa integrasi sudah diuji. Bootstrap wajib menggunakan versi exact dan lockfile; perubahan baseline harus menjelaskan alasan serta hasil pemeriksaan kompatibilitas dan keamanan. Jangan memakai tag `latest` dalam manifest atau image runtime.

| Komponen | Baseline | Lisensi upstream | Alasan dan verifikasi |
|---|---|---|---|
| Node.js | 24.22.3, jalur 24 LTS | MIT serta notice komponen bawaan | Pilih jalur LTS matang; [rilis](https://nodejs.org/en/about/previous-releases/), [versi exact](https://nodejs.org/dist/index.json), [lisensi](https://github.com/nodejs/node/blob/v24.x/LICENSE) |
| Next.js | 16.4.6 | MIT | App Router dan TypeScript; Node minimum 20.9 dipenuhi; [instalasi](https://nextjs.org/docs/app/getting-started/installation), [metadata versi](https://registry.npmjs.org/next/16.4.6) |
| React / React DOM | 19.3.1 / 19.3.1 | MIT | Pasangan versi sama, memenuhi peer React 19 Next.js; [React](https://registry.npmjs.org/react/19.3.1), [React DOM](https://registry.npmjs.org/react-dom/19.3.1) |
| TypeScript | 6.0.3 | Apache-2.0 | Compiler stabil; adopsi compiler major baru ditunda sampai bootstrap teruji; [metadata](https://registry.npmjs.org/typescript/6.0.3) |
| CPython | 3.13.18, jalur 3.13 | PSF-2.0 serta notice komponen bawaan | Jalur security-supported, konservatif untuk ekosistem analisis; [rilis dan dukungan](https://www.python.org/downloads/), [lisensi](https://docs.python.org/3.13/license.html) |
| FastAPI | 0.162.5 | MIT | Kontrak bertipe dan OpenAPI; Python minimum 3.10 dipenuhi; [metadata](https://pypi.org/pypi/fastapi/0.162.5/json), [kebijakan versi](https://fastapi.tiangolo.com/deployment/versions/) |
| PostgreSQL | 18.7, jalur 18 | PostgreSQL License | Transaksi, constraint, audit, dan query point-in-time; [dukungan](https://www.postgresql.org/support/versioning/), [lisensi](https://www.postgresql.org/about/licence/) |
| Redis Open Source | 8.2.11, jalur 8.2 | Pilihan upstream RSALv2 / SSPLv1 / AGPLv3; usulan memakai AGPLv3 | Proses server terpisah tanpa modifikasi; [rilis](https://github.com/redis/redis/releases/tag/8.2.11), [teks lisensi](https://github.com/redis/redis/blob/8.2/LICENSE.txt) |

Redis 8 tidak dicatat sebagai BSD. Pemilik repo perlu menerima pilihan lisensi Redis bersama ADR ini. Image, notice, dan kewajiban distribusi diverifikasi lagi pada SS-006; distribusi publik/berbayar ditinjau sebelum G3. Jika pilihan ini tidak diterima, evaluasi Valkey dengan ADR pengganti dan uji kompatibilitas. Lisensi dependency tidak menentukan lisensi kode aplikasi; lisensi repo tetap keputusan pemilik.

Pin dependency transitif, driver database, server ASGI, library validasi, dan tooling pada bootstrap SS-003/004/006. Bukti kompatibilitas berupa build web, startup API/worker, koneksi database/cache, serta CI SS-007. Tidak menyatakan paket analisis atau model yang belum dipilih sudah mendukung baseline Python ini.

### Ownership dan arah dependency

Ownership di bawah adalah tanggung jawab modul; pemilik repo menjadi penanggung jawab awal seluruh modul sampai maintainer lain ditunjuk.

| Lokasi / modul | Pemilik tanggung jawab dan data | Batas dependency |
|---|---|---|
| `apps/web` | Presentasi dashboard, detail, form fill, watchlist, status, dan alert | Konsumsi kontrak publik API; tidak mengakses database, Redis, vendor, dokumen berita, atau menghitung risiko otoritatif |
| `packages/contracts` | Skema dan contoh API/event berversi lintas bahasa | Tanpa runtime domain; SS-002 menetapkan format source of truth dan pemeriksaan kompatibilitas Python/TypeScript |
| `services/api` transport | REST, WebSocket, autentikasi, otorisasi, validasi, query snapshot | Memanggil application service; tidak menjalankan ingest atau loop model dalam request HTTP |
| `services/api` domain/application | Instrumen/aturan efektif, kualitas, fitur, sinyal, risiko, posisi/fill, konfigurasi, alert, eksperimen | Domain tidak mengimpor FastAPI, vendor SDK, atau adapter storage; application service memakai interface repository/event publisher |
| `services/api` infrastructure | Implementasi repository PostgreSQL, Redis, adapter vendor, clock, dan object storage | Implementasi interface domain; query personal selalu membawa konteks akun dan mode |
| `services/worker` | Lifecycle ingest, penjadwalan fitur/sinyal, replay, alert, retry dan shutdown | Mengimpor paket backend yang dipaketkan SS-004; tidak menyalin aturan domain atau memakai manipulasi `sys.path`; pekerjaan CPU berat di luar event loop HTTP |
| `infra` | Compose, jaringan internal, konfigurasi runtime, migrasi, backup dan deployment | API dan worker memakai paket/image backend sama dengan entrypoint berbeda; satu jalur migrasi backend, tidak berlomba saat startup |
| `research` | Protokol, dataset/eksperimen, evaluasi dan usulan promosi | Memakai domain yang sama; tidak menulis state paper/live atau mempromosikan model otomatis |
| `tests` | Acceptance lintas service dan pengujian isolasi/replay | Fixture diberi label simulasi; tidak mengharuskan data vendor berlisensi untuk CI dasar |

Pengemasan modul backend dan entrypoint konkret diselesaikan SS-004/005. Batas ini berlaku sejak bootstrap. Domain hanya bergantung pada tipe kontrak/domain dan pustaka dasar; transport, worker, dan adapter bergantung ke domain, bukan sebaliknya. Akses lintas modul melalui application service dan event berversi, bukan menulis tabel modul lain langsung.

PostgreSQL menyimpan event, versi sinyal, fill/posisi, audit, konfigurasi, dan outbox alert secara otoritatif. Transaksi domain dan outbox dicatat atomik; worker mengirim dengan idempotency key. Redis pub/sub hanya pemberitahuan yang boleh hilang: restart/reconnect membaca snapshot dan cursor dari PostgreSQL. Redis bukan satu-satunya antrean untuk alert atau audit. Cache dapat dibangun ulang. Raw data besar dan artefak kelak memakai object storage setelah hak penyimpanan/retensi ditetapkan.

### Alur konfigurasi

1. `.env.example` mendokumentasikan nama dan nilai lokal tanpa kredensial nyata; `.env` lokal diabaikan Git. Deployment memasok environment/secret store per service dan mode, tidak membawa `.env` pengembangan.
2. API dan worker memuat konfigurasi bertipe sekali saat startup. Environment mengalahkan default kode; file lokal hanya sumber pengembangan. Validasi menolak `APP_MODE` di luar `research`, `paper`, `live`, namespace tidak cocok, secret wajib hilang, atau koneksi mode lain. Startup gagal secara jelas tanpa mencetak secret; mode tidak bisa diganti lewat query/header request.
3. Konfigurasi deployment (koneksi, mode, akun pilot, kill switch) hanya server. Web menerima konfigurasi publik yang diizinkan dan metadata mode dari API. `NEXT_PUBLIC_*` hanya untuk nilai publik; credential vendor, DSN, dan session secret tidak boleh memakai awalan ini.
4. Preferensi akun (nominal, biaya broker bertanggal, risiko, watchlist) disimpan berversi di PostgreSQL dengan audit. Input divalidasi API; tidak mengubah environment atau batas risiko global. Hasil/cache personal memasukkan akun, mode, nominal, dan versi konfigurasi.
5. Default pengembangan `research`, UTC untuk waktu persisten dan `Asia/Jakarta` untuk tampilan. Contoh koneksi lokal tidak mengaktifkan feed maupun alert live. SS-004 mengimplementasikan validasi startup; SS-006 menyediakan resource terpisah; SS-020 mengimplementasikan preferensi akun.

### Isolasi research, paper, dan live

| Area | Aturan |
|---|---|
| Database | Database dan credential berbeda per mode; role satu mode tidak diberi akses database mode lain. Data personal tetap memiliki `user_id` meskipun pilot hanya satu akun. SS-010/023 menerapkan constraint dan otorisasi. |
| Redis | Instance/credential terpisah per mode untuk deployment; seluruh key, channel dan dedup memakai prefix `saham-signal:<mode>:` serta akun bila personal. Nomor logical database saja tidak dianggap batas keamanan. |
| Object storage | Bucket/prefix per mode dengan izin terpisah; dataset riset merupakan salinan berversi yang diizinkan vendor, bukan akses tulis ke paper/live. |
| Event dan job | Envelope memuat mode, identitas event, versi, timestamp dan akun bila personal; consumer menolak mode berbeda sebelum mutasi/pengiriman. Worker terikat satu mode sepanjang lifecycle. |
| Alert | Tujuan dan dedup terpisah per mode/akun/event/kanal. Fixture dan replay hanya jalur research; simulasi paper tetap berlabel paper. Tidak ada fallback otomatis ke kanal live. |
| UI dan feed | Mode berasal dari server dan selalu tampak; mode simulasi berbeda dari kualitas Live/Delayed/Terputus. Feed berlabel live di lingkungan paper tidak mengubah posisi paper menjadi posisi nyata. |
| Promosi | Artefak dipromosikan dengan versi, laporan gerbang, persetujuan dan rollback; tidak menyalin posisi/cache/antrean antar-mode. Live tetap dinonaktifkan sampai persyaratan PRD terbukti. |

Jalur ingest pasar tidak menunggu pemrosesan berita. Data kritis tidak sehat menahan entry; kill switch mempertahankan visibilitas posisi. READY tidak membuka posisi dan exit yang gagal tetap terbuka. Uang menggunakan desimal/integer presisi tetap; probability belum tervalidasi bernilai null. Seluruh evaluasi historis menghormati `available_at`.

### Akun pilot

Usulkan pilot pribadi satu pemilik, satu akun yang diprovisikan secara administratif, tanpa registrasi publik, undangan, atau organisasi multi-user pada MVP. Tetap gunakan identitas akun persisten dan otorisasi server pada setiap akses personal, termasuk subscription WebSocket. Identitas tidak diambil dari `user_id` yang dikirim browser tanpa pemeriksaan sesi.

SS-023 memilih mekanisme autentikasi/session dan menguji akses akun lain ditolak. Sebelum itu pengembangan hanya lokal dengan fixture research; tidak boleh dipublikasikan sebagai pilot berisi posisi pribadi. Single-account tidak berarti tanpa autentikasi. Penambahan pengguna atau distribusi publik memerlukan keputusan baru dan pemeriksaan hak display data pada G3. Persetujuan ADR juga menerima batas pilot ini.

## Alternatif

| Alternatif | Alasan tidak dipilih untuk fondasi |
|---|---|
| SPA React/Vite | Layak untuk dashboard; Next.js mengikuti PRD dan menyediakan routing/layout dalam satu aplikasi. Evaluasi ulang bila kompleksitas server web tidak memberi manfaat. |
| Backend seluruhnya di Next.js/Node.js | Mengurangi bahasa, tetapi memisahkan ekosistem analisis Python dari aturan backend; berisiko menduplikasi perhitungan. |
| Django | Auth/admin terintegrasi menarik; FastAPI dipilih untuk API bertipe dan transport terpisah dari domain. Konsekuensinya auth dan tooling migrasi perlu keputusan pada bootstrap/keamanan. |
| Microservices + broker terdistribusi | Biaya operasi dan konsistensi terlalu besar untuk pilot tanpa bukti beban; pecah modul hanya setelah profil kapasitas menunjukkan kebutuhan. |
| SQLite / database dokumen | SQLite bermanfaat untuk prototipe, tetapi target API/worker membutuhkan transaksi bersamaan, constraint, dan audit relasional PostgreSQL. Database dokumen tidak memberi keuntungan jelas untuk posisi/fill. |
| PostgreSQL saja tanpa Redis | Dapat menyederhanakan awal, tetapi Redis dipilih untuk cache/fan-out sementara. Kebenaran sistem tetap dapat dipulihkan dari PostgreSQL. |
| Valkey / Redis 7 lama | Valkey menjadi kandidat bila lisensi Redis 8 tidak diterima; tidak menganggapnya pengganti tanpa uji. Tidak membekukan versi Redis lama hanya untuk mempertahankan lisensi historis. |
| TimescaleDB sejak awal | Ditunda sampai volume dan pola query diketahui; PostgreSQL standar menghindari extension/lisensi tambahan sebelum pengukuran. |
| Multi-user dan registrasi publik | Menambah permukaan keamanan, operasi dan kebutuhan hak data; tidak diperlukan untuk pilot pribadi. Struktur akun tetap disiapkan. |

## Keputusan terbuka dan tindak lanjut

| Keputusan | Alasan belum final / default | Pemilik dan tindak lanjut |
|---|---|---|
| Penerimaan ADR, lisensi Redis dan batas akun pilot | Memerlukan penilaian pemilik terhadap dokumen konkret | Pemilik repo: review ADR ini; catat bukti penerimaan sebelum `Accepted` dan sebelum SS-001 dinyatakan selesai |
| Format kontrak dan code generation | Belum ada skema lintas bahasa | Maintainer kontrak / SS-002: pilih source of truth, versioning dan compatibility checks |
| Tooling bootstrap dan dependency transitif | Belum ada build untuk membuktikan kombinasi paket | Maintainer web/backend / SS-003/004/005: pin dan lock, audit lisensi, smoke test; ubah ADR jika baseline tidak kompatibel |
| Image, secret store dan deployment | Belum ada target hosting/anggaran | Maintainer infra / SS-006/025: image exact beserta digest, resource per mode, backup/restore dan pengelolaan secret |
| Auth dan retensi data personal | Bergantung cara akses pilot | Maintainer backend / SS-023: session, provisioning, otorisasi per akun, ekspor/penghapusan, retensi sebelum pilot |
| Vendor, hak data, biaya dan kapasitas | Sampel/kontrak vendor belum tersedia | Pemilik repo / SS-008: audit display/non-display, simpan/redistribusi dan SLA sebelum G0 |
| Object storage dan time-series extension | Volume, retensi dan hak penyimpanan belum diketahui | Maintainer persistence / SS-010 bersama SS-008; ukur kapasitas sebelum menambah dependency |
| Chart dan browser push | Belum diperlukan untuk bootstrap | Maintainer web / SS-019/022: periksa lisensi chart; push opsional setelah izin pengguna, in-app wajib |
| Biaya broker, ambang model, dan promosi | Harus berdasarkan tarif berlaku dan validasi | Pemilik kebijakan / SS-015/016/027/028: versikan biaya, bekukan ambang sebelum evaluasi, buktikan gerbang terpisah |

## Konsekuensi dan validasi

Dua runtime membutuhkan lockfile dan CI masing-masing; proses worker terpisah menjaga request HTTP tidak menanggung loop ingest/CPU. Pembagian modul menjaga aturan risiko dan state machine identik pada replay dan pemantauan. Database/resource terpisah meningkatkan biaya lokal/deployment tetapi mengurangi kemungkinan simulasi menulis ke live.

Validasi untuk perubahan dokumentasi ini: `node scripts/check-scaffold.mjs`, `node scripts/publish-issues.mjs` (dry run), dan `git diff --check`. Belum ada pengujian integrasi runtime. SS-007 menambahkan build/typecheck web dan test backend; SS-023 menguji penolakan akses antar-akun/mode; SS-026 menguji snapshot/delta, reconnect, dedup, partial fill, dan feed putus.

Tinjau ulang ADR bila baseline tidak kompatibel saat bootstrap, dukungan/security dependency berubah, kebutuhan multi-user muncul, lisensi/deployment berubah, atau pengukuran menunjukkan PostgreSQL/worker tunggal tidak memenuhi beban pilot. Penerimaan ADR tidak menggantikan verifikasi ulang patch dan lisensi pada implementasi.
