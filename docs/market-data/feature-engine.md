# SS-013 — Feature engine point-in-time

`application/features.py` adalah reducer yang sama untuk riset, replay dan stream.
`adapters/features.py` memvalidasi kontrak MarketEvent v1 sebelum memasukkan data.
Tidak ada endpoint baru, model, sinyal, investor count, atau izin entry/live.
Data pengujian seluruhnya simulasi; validasi vendor SS-011 dan G0 tetap pending.

## Integrasi

Buat `FeatureEngine(profile, mode, FeaturePolicy(...))` dan
`FeatureConsumer(engine)` per source, semantik feed, dan mode. Pada jalur stream,
panggil sink journal terlebih dahulu, kemudian `consumer.committed(observation)`.
Jika proses terhenti di antara keduanya, bangun ulang consumer dari journal.
Jangan mengganti sink durable dengan consumer in-memory.

Pada replay, untuk setiap row dari `Journal.replay(cutoff)`, panggil
`consumer.journal_row(row)`. Adapter hanya menerima MarketEvent market-scope
(`user_id` kosong) dalam mode engine. Candle tidak dipakai karena transaksi yang
sama tidak boleh dihitung lagi sebagai volume candle. Kontrak candle durable
tetap mengikuti keterbatasan SS-011.

Panggil `engine.snapshot(symbol, cutoff, baseline_sessions=..., quality=...)`.
Snapshot berupa dataclass immutable dengan Decimal, datetime bertimezone, unit
eksplisit, policy, source, mode, origin dan delivery. Belum menjadi kontrak REST;
serialisasi/penyimpanan output memerlukan kontrak berversi tersendiri.

Sediakan assessment SS-012 dari source/session yang sama, tepat pada cutoff,
dengan mode/origin/symbol yang sama. Runtime tetap wajib melakukan polling
kualitas dan seluruh gate risiko sebelum memakai fitur. Assessment live/delayed
tanpa alasan gangguan (label SIMULATION/DELAYED_FEED diperbolehkan untuk riset)
dibutuhkan untuk menampilkan book; status buruk, assessment hilang atau berbeda
cutoff menyembunyikan spread/depth/imbalance. Harga transaksi historis bukan
indikator freshness. Output fitur sendiri tidak mengotorisasi trading.

Replay dan stream identik bila menerima event/revisi, cutoff, policy, sesi
baseline, dan assessment point-in-time yang sama. Tidak boleh memakai assessment
hari ini untuk snapshot historis. Semua versi disimpan in-memory; caller membatasi
retensi/session dan memuat histori baseline yang cukup dari journal. Ini reducer
referensi, belum benchmark throughput atau penjadwalan worker produksi.

## Definisi fitur versi 1

- Filter `available_at <= cutoff`; pilih revisi tertinggi yang sudah tersedia
  per event ID, baru filter `event_time <= cutoff`. Event terlambat/koreksi tidak
  mengubah cutoff lama. Duplikat identik idempotent, konflik ditolak. Urutan
  perhitungan deterministik: event time, sequence numerik, event ID.
- Jendela transaksi `(cutoff - window, cutoff]`, default 5 menit. Return fraksi
  adalah harga transaksi terakhir / pertama - 1, null jika kurang dari 2 transaksi.
  Volatilitas adalah simpangan baku populasi return sederhana antartransaksi,
  null jika kurang dari 2 return. Tidak diannualisasi atau dianggap return candle;
  batas sesi/aksi korporasi wajib ditangani caller saat memilih jendela penelitian.
- Volume adalah jumlah lot transaksi. Relative volume membagi volume jendela
  sekarang dengan rata-rata jendela berakhir pada jam WIB yang sama pada daftar
  sesi terdahulu eksplisit. Caller memilih sesi kalender SS-009; duplikat/tanggal
  sekarang/masa depan ditolak. Histori kosong pada salah satu sesi atau rata-rata
  nol menghasilkan null, bukan volume nol rekaan. Revisi baseline juga memakai
  cutoff availability yang sama. Tidak ada baseline default yang mengasumsikan
  akhir pekan/libur sebagai sesi perdagangan.
- Agresor berasal dari field feed ternormalisasi `buyer`/`seller`/`unknown`.
  Metode `feed-aggressor-v1` tidak mengubah trade ambigu menjadi buyer/seller.
  Tanpa agresor vendor, adapter harus mengirim `unknown`; algoritme inferensi
  “Estimasi” baru boleh ditambah setelah validasi tersendiri, bukan fallback diam-diam.
- Coverage = (buyer lots + seller lots) / seluruh lot. Buy pressure = buyer lots /
  classified lots, sell pressure = 1 - buy pressure. Volume unknown tetap dilaporkan.
  Keduanya null saat tidak ada volume atau coverage di bawah ambang policy
  (default simulasi 0,8, inklusif). Alasan tersembunyi dan jendela tetap tersedia.
  Angka default belum ambang validasi produksi.
- Spread adalah best ask - best bid dalam IDR. Depth adalah jumlah lot masing-masing
  sisi pada maksimum N level (default 5) dari snapshot penuh terbaru. Delta feed
  sudah dinormalisasi menjadi snapshot penuh oleh SS-011. Book tidak dicampur.
  Snapshot harus segar (default simulasi 10 detik) dan memiliki kedua sisi.
  `available_levels` menghitung minimum level kedua sisi sampai N, `limited_depth`
  mengungkap kedalaman kurang dari N. Sisi kosong menyembunyikan metrik book.
- Book imbalance = bid depth / (bid depth + ask depth), bernama **Komposisi antrean**.
  Ini berbeda dari pressure transaksi dan tidak memberi jumlah/persentase investor.

## Bukti acceptance

`services/api/tests/test_features.py` menguji angka rumus, paritas replay/stream
termasuk book, availability, future event, duplikat, out-of-order, koreksi dan
cutoff lama, baseline jam WIB, coverage tepat ambang/kurang/unknown/kosong,
book stale/kualitas buruk, isolasi source/mode/origin, alias payload dan presisi.
Jalankan pemeriksaan backend pada [panduan CI](../RUNTIME-CI.md).
Kelulusan uji ini tidak meluluskan G0/G1/G2/G3 atau validasi klasifikasi vendor.
