# Research

Status: evaluasi baseline SS-016 tersedia sebagai modul research internal dan
fixture simulasi yang dapat direproduksi. G1 **no-go**, hasil tetap eksperimen.

Mulai evaluasi vendor dari [audit SS-008](../docs/market-data/vendor-audit.md) dan
[protokol sampel](../docs/market-data/vendor-evaluation.md). Belum ada sampel vendor
berizin yang diukur; G0 pending.

Lihat [protokol, ranking nominal dan evaluasi](../docs/market-data/baseline-evaluation.md)
serta [bukti simulasi SS-016](reports/SS-016-simulation.md). Model, nominal,
split/holdout dan kebijakan dibekukan; tidak ada auto-promotion atau probabilitas
produk yang belum disetujui bukti kalibrasinya.

Jangan commit data vendor atau artefak model besar. Protokol/hasil harus mencatat versi dataset, kode, split, asumsi, dan keputusan promosi.

SS-024 menambah [ablation berita internal](../docs/market-data/internal-news.md)
dengan hash dataset/protokol, gate tetap dan paired delta setelah biaya. Jalankan
`python -m saham_signal.adapters.news_simulation` dari environment backend untuk
[bukti simulasi](reports/SS-024-simulation.md). Ranking berita tetap disabled;
tidak ada manfaat produksi yang telah dibuktikan.
