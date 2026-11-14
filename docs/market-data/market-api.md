# API market dan stream — SS-017

Implementasi issue #17 menyediakan query kontrak v1 dan WebSocket untuk UI tanpa
model tervalidasi. Dependency #2/#4/#10/#12/#15 serta SS-016 sudah tersedia.
Hasil SS-016 masih **G1 no-go / experiment**, dan bukti vendor G0 belum tersedia.
Tidak ada jalur input model/vendor di service fixture ini. Saat fixture dimatikan,
query market mengembalikan 503; mode paper/live tidak dapat mengaktifkan fixture.
Integrasi model produksi harus menghubungkan artefak SS-016 yang ditinjau dengan
risiko SS-015, kualitas SS-012, jurnal SS-010 dan bukti gerbang sesuai mode sebelum
menyediakan kandidat pasar. Boolean konfigurasi bukan bukti kelulusan gerbang.

## Menjalankan skenario UI lokal

Ikuti setup [API](../../services/api/README.md), kemudian atur `.env` lokal:

Sejak SS-020, query market juga membaca profil akun terbaru dari PostgreSQL.
Jalankan infra research dan migrasi `uv run --locked python -m saham_signal.migrate`
sebelum mencoba fixture. Database tidak tersedia atau migrasi belum dijalankan
menghasilkan 503; tidak ada fallback yang melewati konfigurasi risiko pengguna.

```dotenv
APP_MODE=research
MARKET_FIXTURE_ENABLED=true
# Isi dengan nilai acak lokal minimal 32 karakter, jangan gunakan contoh sebagai secret.
MARKET_FIXTURE_TOKEN=<random-local-secret-minimum-32-characters>
MARKET_NOMINAL_IDR=1000000.00
MARKET_HORIZON_MINUTES=30
```

Token adalah credential fixture satu akun, diperiksa constant-time pada cookie
`saham_session`. Atur cookie lokal melalui klien HTTP/browser development; pada
fetch ke origin API gunakan `credentials: 'include'`. Server tidak menyediakan
login atau menerbitkan cookie. Jangan taruh token di URL atau bundle web publik.
Akun berasal dari `PILOT_ACCOUNT_ID`, atau `fixture-pilot` bila kosong. Mekanisme
lokal ini hanya untuk development loopback, bukan pengganti autentikasi SS-023.
Mengganti token dan restart mencabut sesi fixture lama.

| GET `/api/v1` | Respons |
|---|---|
| `/candidates` | `CandidatesResponse`, sinyal WATCH skenario TEST |
| `/stocks/TEST` | `StockDetailResponse`, aturan simulasi, depth dan pressure |
| `/stocks/TEST/depth` | `DepthResponse`, satu snapshot book penuh, terbatas |
| `/stocks/TEST/chart?interval=1m` | `ChartResponse`, candle sintetis terpisah dari proyeksi |
| `/stocks/TEST/signals` | `SignalHistoryResponse`, versi append-only skenario |

Simbol selain TEST menghasilkan 404. Chart hanya menerima 1m/5m/15m; interval
wajib dikirim. Fixture hanya memiliki candle 1m: 5m/15m mengembalikan array kosong,
tanpa mengubah label candle 1m. Tidak ada pengisian data hilang menjadi nol.
Likuiditas yang belum dihitung `null`; probabilitas dan kuantil tetap `null`,
proyeksi kosong dan model chart `null`. WATCH bukan izin entry atau transaksi.

Fixture publik dibundel di wheel, berasal dari contoh kontrak SS-002. Service
mengikat waktu skenario sekali saat startup; harga/volume seluruhnya sintetis.
`as_of` menunjukkan waktu snapshot/phase skenario, `depth_as_of` tetap waktu book
awal, kualitas/feed tetap unavailable dengan alasan SIMULATION/MODEL_UNVALIDATED.
Waktu tidak bergeser pada setiap request. Saat batas horizon tercapai, kandidat
dihapus dan riwayat/detail mendapat versi EXPIRED baru; versi WATCH tetap tersimpan
dalam riwayat. Restart memulai skenario baru dan identitas stream baru.

Setiap respons sukses memiliki metadata kontrak/as_of/mode/data_origin/quality.
Expiry sinyal berada pada `valid_until`, `entry_until` dan `exit_deadline` sesuai
schema v1 beku. Header HTTP `Expires` mencatat batas skenario tanpa menambah field
wire; `Cache-Control: private, no-store` dan `Vary: Cookie` mencegah cache bersama.
Cache internal LRU maksimum 128 entri menggunakan akun, mode, nominal, horizon,
versi konfigurasi, resource, simbol dan interval; pergantian phase expiry
membatalkan hasil lama. Caller mendapat salinan independen. SS-018 menambahkan
query opsional `/candidates?nominal_idr=2500000.00`: decimal positif dengan dua
angka pecahan, maksimum 16 digit bilangan bulat, tanpa key duplikat. Default tetap
`MARKET_NOMINAL_IDR` bila belum ada profil SS-020. Profil tersimpan selalu menjadi
sumber nominal/versi biaya/konfigurasi pada query dan stream. Nominal query hanya
memilih scope sementara pada akun yang belum memiliki profil; tidak mengubah
setting global, akun, mode, horizon atau scope WebSocket. Query akun/mode/horizon
dan nominal pada endpoint lain tetap ditolak. OpenAPI mendokumentasikan parameter
tambahan ini; schema respons v1 tidak berubah. Fixture menyajikan ulang skenario
WATCH dengan asumsi nominal terpilih, **bukan** perhitungan kapasitas/slippage atau
ranking personal tervalidasi. Estimasi yang belum tersedia tetap null. Integrasi
produksi tetap memerlukan sizing/ranking SS-015/016 dan gerbang yang disetujui.

## WebSocket `/api/v1/stream`

Sesi cookie dan Origin yang cocok `CORS_ORIGINS` wajib sebelum upgrade. Stream
mendukung topic `signals` dan `depth`; positions/alerts belum dikerjakan dan
menghasilkan DATA_UNAVAILABLE. Maksimum delapan subscription per koneksi.

```json
{"kind":"subscribe","contract_version":"1.0.0","subscription_id":"ui-1","topic":"signals","symbol":null,"resume_cursor":null}
```

Snapshot atomik mencakup stream_id, subscription_id, akun server, topic, simbol,
cursor opak, sequence `1` dan items lengkap. Depth wajib simbol TEST. Setiap
subscription baru mendapat stream_id/cursor baru. Perubahan state diperiksa
setiap 250 ms; expiry menghasilkan delta remove sinyal, sequence `2` dengan
previous_sequence `1`. Upsert mengganti entitas penuh, depth satu book penuh.
Tidak ada delta buatan saat data tidak berubah.

Server belum menyimpan rantai replay cursor. **Setiap resume_cursor non-null
menghasilkan RESYNC_REQUIRED**, termasuk cursor koneksi sebelumnya, cursor
tebakan, scope lain atau proses sebelum restart. Klien wajib menahan state live,
subscribe ulang dengan cursor null, mengganti seluruh state dari snapshot, lalu
menerapkan delta hanya bila stream/scope/previous_sequence cocok. Cursor bukan
credential; tidak ada lookup cursor yang membuka akun lain. Gap atau duplikat
ditangani consumer mengikuti [kontrak](../../packages/contracts/README.md).

Payload masuk divalidasi sebagai Subscribe; field tambahan/user_id ditolak.
Payload keluar divalidasi schema canonical tertutup, termasuk nested; data
NewsEvent, Experiment, source_ref atau field internal tambahan gagal tertutup,
tanpa mencetak isi upstream. Tidak ada endpoint berita/internal.

## Validasi

`tests/test_market_api.py` memeriksa seluruh respons dengan schema SS-002, sesi,
mode, expiry/cache, interval hilang, data null, error aman, Origin, snapshot depth,
delta expiry, reconnect, batas subscription dan penolakan field internal.
Smoke wheel menjalankan HTTP dan handshake WebSocket sungguhan melalui Uvicorn
dengan dependency runtime saja. Kelulusan test/CI bukan kelulusan G0/G1/G2/G3.
