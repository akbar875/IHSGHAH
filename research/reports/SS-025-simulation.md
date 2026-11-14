# SS-025 — Receipt operasi simulasi

Tanggal: 14 November 2026. **Seluruh input buatan; G0–G3 tetap pending.**
[Receipt JSON](SS-025-simulation.json) memuat pengukuran lokal Windows/Chromium
serta hasil restore PostgreSQL 18.7. Angka bergantung mesin dan bukan SLA pasar.
[Runbook](../../docs/market-data/operations.md) menjelaskan scope, operasi dan
reproduksi; CI menyimpan receipt pengukuran barunya selama 14 hari.

## Beban dan hasil

Pilot sintetis: satu owner, universe 100 simbol, maksimum desain tiga posisi,
20 siklus pembaruan setiap lima detik waktu simulasi (2.000 snapshot buku).
Stress memproses siklus tanpa menunggu lima detik wall-clock untuk mengukur
kapasitas burst. Setiap pesan melewati validasi kontrak, commit memory sink,
normalisasi dan pembacaan book. Database/network tidak termasuk sink komponen ini.

| Pemeriksaan | Sasaran sementara PRD | Hasil lokal |
|---|---|---|
| Siklus 100 simbol | ≤5 detik | Maksimum sekitar 0,463 detik |
| Validated ingest→book consumer | p95 ≤2 detik | Sekitar 0,00491 detik |
| Mock received_at→browser, 100 kartu ×20 snapshot | p95 ≤2 detik | Sekitar 0,460 detik |
| Heartbeat melewati 10 detik | Degraded/entry ditahan | Lulus tes batas 10s dan 10s+1µs SS-012 |
| Stale/disconnected | 30s/60s provisional | Lulus, posisi tidak ditutup oleh warning |
| Gap/reconnect | Heartbeat sehat + snapshot connection baru | Lulus; level book lama tidak tercampur |
| Inbox reconnect/retry | Tidak ada alert risiko ganda | Source key/channel persisten, retry setelah restore sama |
| Drift/kill/rollback | Abstention dan posisi utuh | READY→WATCH; saham rencana nol; tidak ada fill sintetis |

Browser test memakai endpoint fixture yang dimock, refresh eksplisit, waktu
monotonic satu clock host dan dua animation frame sesudah DOM 100 kartu terbarui.
Tidak mengukur upstream vendor, automatic polling 15s, rendering tab background,
mobile hardware, atau jalur feed→DB→API→WebSocket→browser terpadu. Interval
tampilan sekitar satu detik/prioritas event kritis pada transport nyata masih
perlu integrasi SS-026. Kedua angka p95 membuktikan komponen terpisah, bukan angka
end-to-end produksi yang dijumlahkan atau diklaim lulus.

## Restore PostgreSQL nyata

Dua schema disposable dalam database research yang sama dimigrasikan terpisah.
Setiap dari delapan tabel berisi satu baris: journal, retention policy,
preferences, ledger manual, inbox, gate alert, receipt berita dan control event.
Source di-snapshot repeatable-read; target kosong dipulihkan dengan checksum
migrasi identik. Tes memakai operator dan role runtime non-owner.

Hasil yang diperiksa otomatis:

- Semua baris sama setelah restore, kecuali satu event pause tambahan.
- Posisi tetap dua lot; retry key fill sama tidak menciptakan posisi/alert baru.
- Refresh alert risiko yang sama tetap satu alert, dengan gate yang dipulihkan.
- Penulisan posisi baru setelah restore menghasilkan identity cursor berikutnya.
- Source tetap satu posisi ketika target diberi posisi tambahan.
- Kegagalan constraint pada akhir restore membatalkan seluruh insert; target kosong.
- Target berisi, checksum rusak dan backup via role runtime ditolak.
- Kontrol bertahan pada instance repository baru; delapan writer dengan revision
  sama menghasilkan tepat satu perubahan. UPDATE audit ditolak.

Ini membuktikan restore logical pada fixture kecil, bukan RTO/RPO produksi,
disaster recovery lintas host, retensi vendor atau recovery WAL. Redis/book cache
harus dibangun ulang dari snapshot baru, bukan dipulihkan dari cursor lama.

## Validasi regresi dan batas rilis

Ruff lint/format, mypy, backend pytest dengan PostgreSQL disposable dan
Playwright diuji; CI juga menjalankan wheel/smoke, kontrak, build web, scaffold
dan integrasi PostgreSQL/Redis. SIGTERM diuji di Linux CI, dilewati di Windows.
Tes CLI memeriksa perintah operator, backup eksklusif dan error tersanitasi.

SS-016 dan SS-024 direproduksi setelah snapshot kontrol masuk audit input:
fingerprint berubah, metrik eksekusi/paired holdout tetap sama. G1 tetap no-go,
ranking berita disabled dan tidak ada auto-promotion.

Dependency #11 masih menunggu vendor/sampel berizin. Bukti ini tidak menutup #11
atau membuka gerbang lain. Paper penuh, kapasitas/biaya nyata, drift model
tervalidasi, deployment rollback/canary dan SLA received_at→display terpadu harus
dibuktikan sebelum pilot digunakan.
