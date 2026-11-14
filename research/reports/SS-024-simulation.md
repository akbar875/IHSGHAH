# SS-024 — Bukti ablation simulasi

Seluruh dokumen, grant dan transaksi pada laporan ini **simulasi buatan**. Tidak
ada data vendor, izin produksi, model berita tervalidasi atau klaim profit.
G0–G3 tetap pending dan ranking berita disabled.

Reproduksi 14 November 2026 (SS-025) memperbarui fingerprint protokol/laporan
karena snapshot kontrol operasi menjadi input risiko SS-016. Metrik paired
holdout dan keputusan kedua varian tetap sama; bukan holdout pasar baru.

Reproduksi dari environment backend:

```sh
python -m saham_signal.adapters.news_simulation
```

[Receipt JSON](SS-024-simulation.json) menyimpan hash protokol/dataset/laporan
serta metrik holdout dari lima baseline SS-016 dan dua nominal (Rp200.000 dan
Rp1.000.000) pada masing-masing varian. Protokol pasar, simulator, biaya, sizing,
split/purge/embargo dan seed tidak diubah.

| Varian | Hasil | Keputusan |
|---|---|---|
| `absent` | Tidak ada berita; gate menahan semua entry. Tidak ada manfaat positif terukur terhadap baseline pada fixture ini. | Ranking berita disabled. |
| `all_mapped` | Satu event simulasi terverifikasi tersedia pada waktu keputusan setiap kasus; metrik eksekusi sama dengan baseline. Delta bersih nol pada perbandingan tertutup. | Tidak ada manfaat tambahan; ranking berita disabled. |

Sebagian baseline/nominal memiliki posisi simulasi belum tertutup; paired delta
dan intervalnya `null` dengan alasan `unclosed_positions`. Laporan tidak mengarang
hasil exit untuk membuat perbandingan terlihat lengkap. Perbandingan tertutup
menggunakan CI bootstrap blok sesi; flag manfaat hanya benar jika lower bound >0.
Dataset buatan ini tidak membuktikan kontribusi berita pada saham nyata.

Pengujian `tests/test_news.py` mencakup source grant dan batas LLM, pemetaan emiten,
input tak tepercaya, batas byte/MIME, waktu pertama tersedia termasuk latency
ekstraksi, koreksi/revisi, dedup/sindikasi tanpa menyegarkan event lama, receipt
PostgreSQL concurrent dan immutable, kegagalan CLI tersanitasi, hash manifest,
holdout sekali, hasil deterministik serta isolasi transport/feed pasar.

Sebelum riset produksi, bekukan protokol dan receipt konsumsi holdout dalam journal
eksperimen; jangan mengulang dataset holdout yang sama untuk memilih aturan berita.
Pemilihan vendor, sampel berizin, evaluasi OOS/prospektif dan kajian independen
tetap terpisah. Lihat [panduan SS-024](../../docs/market-data/internal-news.md).
