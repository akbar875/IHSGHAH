# Kualitas feed dan abstention — SS-012

Status 13 November 2026: kebijakan kualitas dan pengaman input diimplementasikan
di backend, dengan acceptance sintetis. **G0 tetap PENDING**. Dependency #11
menyediakan normalisasi/recovery book; decoder dan sampel vendor, transport,
checkpoint restart dan candle durable tetap terbuka pada issue tersebut.

## Hasil inspeksi issue #12

Sebelumnya adapter sudah memisahkan heartbeat dari trade, membatalkan book saat
gap/reconnect dan menolak pencampuran koneksi. Belum ada timer kualitas, ambang
SLA, pengaman entry atau event gangguan posisi. Implementasi ini menambahkan
`application/feed_quality.py` dan menghubungkannya ke `FeedIngestor` tanpa
mengubah kontrak v1, menambah feed, atau mengaktifkan jalur transaksi.

## Status dan ambang

`FeedSLA` immutable dipasang ketika membuat `FeedIngestor(..., sla=...)`. Simpan
reference bukti SLA bersama konfigurasi deployment. Default berlabel
`PRD-8/provisional`: heartbeat timeout >10 detik, stale >30 detik, disconnected
>60 detik, lag sumber >10 detik dan toleransi clock skew 1 detik. Nilai 30/60/1
adalah pilihan simulasi, bukan janji vendor. Ambang harus positif/berurutan;
ganti dengan SLA sumber yang disetujui serta hasil uji beban sebelum produksi.

| Status | Makna dan kebijakan |
|---|---|
| live | Heartbeat sehat/segar, book tersinkronisasi, delivery live |
| delayed | Input tersinkronisasi tetapi sumber memang delayed; entry real-time ditahan |
| degraded | Heartbeat melewati ambang, lag/skew sumber, status upstream buruk, gap atau resync belum selesai |
| stale | Umur heartbeat melewati stale_after; entry dan exit berbasis harga ditahan |
| disconnected | Belum ada heartbeat, upstream disconnected, reconnect atau melewati disconnected_after |

Prioritas status: disconnected, stale, degraded, lalu delivery live/delayed.
Asal simulation tetap tercantum dan selalu menahan entry, termasuk profil
simulasi yang diberi delivery live. `entry_allowed` hanyalah kelayakan input;
lisensi/G0, aturan instrumen, validasi model, risiko dan gerbang lain tetap wajib.

Umur stream berasal dari **waktu heartbeat sumber**, bukan waktu receipt pesan
yang diputar ulang. Timestamp heartbeat sumber juga mengukur keterlambatan
provider secara konservatif; latency pipeline dapat tetap diukur dari envelope
ingest. Heartbeat dari channel bersama harus dirutekan decoder ke simbol yang
benar-benar dicakup channel tersebut. Umur transaksi (`last_trade_at`,
`trade_age`) dilaporkan terpisah dan tidak mematikan saham sepi. Timestamp trade
late/correction tidak memundurkan waktu transaksi terakhir.

## Pemakaian dan recovery

Caller runtime wajib menjalankan timer (misalnya setiap 1 detik) **walaupun tidak
ada pesan**. Panggil juga tepat sebelum menggunakan input untuk entry/exit:

```python
assessment = ingestor.assess_quality(
    symbol, now_utc,
    active_positions=account_scoped_position_ids,
    emit=durable_position_warning_sink,
)
if not assessment.entry_allowed:
    return  # abstain; jangan membuat rekomendasi entry
```

Semua waktu harus aware dan clock evaluasi tidak boleh mundur dalam sesi.
Ingest ikut mengevaluasi timer sebelum memproses pesan; state positif hanya maju
setelah commit sukses. Duplicate, heartbeat lama, pesan dari koneksi sebelumnya,
atau commit gagal tidak menyegarkan kesehatan. Feed yang belum dikenal ditutup.

Timeout mengunci pengaman, membatalkan book yang sebelumnya layak, dan meminta
snapshot. Heartbeat sehat saja, trade, delta atau snapshot lama tidak dapat
membuka pengaman. Diperlukan heartbeat sehat lalu **snapshot baru yang segar**
pada koneksi aktif, mencakup sequence tertinggi yang ditolak. Snapshot dipasang
utuh oleh SS-011. Delta out-of-order/kedaluwarsa mengunci pengaman; resnapshot
wajib sebelum input layak lagi. Reconnect membuang kesehatan heartbeat dan book;
data dari koneksi lama tidak dapat memulihkannya.

`PositionDataDisruption` dikirim ke sink caller untuk tiap posisi aktif saat
input tidak layak. Event membawa source, simbol, position_id, episode,
assessment, mode dan provenance. Tidak ada harga exit, order atau fill dan tidak
ada mutasi posisi. `price_exit_allowed=False` menahan rekomendasi exit berbasis
harga tak sehat; posisi tetap terbuka. Warning timeout diterbitkan sebelum
request snapshot agar transport yang gagal tidak menghilangkan peringatan.

Deduplikasi berlaku per posisi/episode dalam sesi. Posisi baru saat gangguan
ikut diperingatkan; kegagalan sink diteruskan dan pengiriman dapat dicoba ulang.
Sink harus atomik/idempotent dan caller harus menyimpan scope akun, identitas sesi
serta dedup durable untuk integrasi notifikasi/restart. Modul ini tidak mengklaim
delivery lintas kanal/restart; runtime transport, engine sinyal/posisi dan kanal
notifikasi belum ada. Metadata `quality` pada MarketEvent SS-011 tetap metadata
ingest; keputusan runtime wajib memakai assessment terbaru, bukan status event
historis atau `Book.synchronized` saja.

## Bukti acceptance dan G0

`services/api/tests/test_feed_quality.py` memverifikasi PRD 1 (timeout/disconnect,
entry ditahan, warning posisi, exit ditahan), 2 (heartbeat sehat pada saham sepi,
umur trade tetap terlihat), dan 7 (gap/reconnect, snapshot recovery dan book tidak
bercampur). Suite SS-011 tetap memverifikasi dedup, out-of-order, unit dan
snapshot atomik. Tes tambahan mencakup delayed/simulation, batas SLA, gagal sink,
gagal commit, isolasi simbol, source lag dan clock evaluasi mundur.

Pengujian adalah simulasi milik proyek. Belum ada sampel berizin, kontrak SLA,
metrik beban/latensi vendor, hak penyimpanan atau bukti recovery vendor nyata.
Audit [G0](vendor-audit.md) diperbarui dengan batas ini. Keberhasilan acceptance
sintetis tidak meluluskan G0 dan tidak menutup pekerjaan vendor pada #8/#11.
