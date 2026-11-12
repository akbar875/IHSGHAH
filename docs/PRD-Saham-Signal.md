# PRD — Aplikasi Analisis Saham Intraday BEI

Versi: 1.0 — 12 November 2026  
Status: spesifikasi produk untuk implementasi; kelayakan strategi belum terbukti  
Nama kerja: Saham Signal  
Zona waktu produk: Asia/Jakarta (WIB)

## 1. Ringkasan keputusan

Bangun aplikasi web minimalis untuk memeringkat saham BEI berdasarkan estimasi hasil bersih, peluang target tercapai, dan kemudahan eksekusi untuk nominal transaksi pengguna. Produk menyajikan zona entry, jendela waktu entry, stop loss, take profit, dan kondisi exit yang diperbarui mengikuti pasar. Pengguna membuka detail saham untuk melihat chart, proyeksi probabilistik, order book, serta tekanan beli/jual.

Berita, analisis informasi perusahaan, dan konteks global diproses di backend. Tidak ada feed berita atau panel penjelasan model di halaman pengguna. Status data, keterbatasan estimasi, dan perubahan rencana transaksi tetap terlihat agar informasi tidak menyesatkan.

MVP adalah alat bantu keputusan dan paper trading. Tidak ada eksekusi broker otomatis. Keuntungan, ARA, harga pengisian pesanan, dan waktu terbaik tidak dijamin. Peluncuran antarmuka tidak boleh disamakan dengan strategi yang terbukti menghasilkan keuntungan.

## 2. Tujuan, pengguna, dan asumsi

### Tujuan

1. Memudahkan pengguna menemukan kandidat kenaikan dengan risiko dan likuiditas terukur.
2. Menyajikan rencana transaksi bersyarat yang dapat diikuti dan kedaluwarsa secara jelas.
3. Mengukur hasil sinyal setelah biaya dan kendala eksekusi secara prospektif.
4. Menahan sinyal ketika data, kualitas model, atau kondisi pasar tidak memadai.

### Pengguna utama

Investor ritel saham Indonesia yang mengambil keputusan intraday secara manual. Diasumsikan transaksi long-only, menggunakan dana tunai, tanpa margin atau short selling. Pengguna memahami bahwa rekomendasi exit bukan pesanan yang sudah dieksekusi.

### Asumsi MVP

- Horizon utama sampai akhir sesi reguler hari yang sama. Horizon 15, 30, dan 60 menit digunakan untuk evaluasi dan tampilan yang memenuhi kualitas model.
- Cakupan awal saham pasar reguler dengan data dan likuiditas memadai. Papan atau mekanisme khusus, saham tersuspensi, dan instrumen lain dikecualikan sampai didukung serta diuji terpisah.
- Pemantauan di luar jam bursa terbatas pada informasi dan persiapan; tidak diberi label perdagangan real-time aktif.
- Pengguna memasukkan nominal rencana transaksi. Untuk pemantauan posisi, pengguna mengonfirmasi harga beli rata-rata, jumlah lot, dan waktu pengisian aktual.
- Kebutuhan akun multi-pengguna, penyedia data, dan anggaran belum diputuskan. Arsitektur mendukung pemisahan akun; pilot dapat digunakan secara pribadi.

### Di luar cakupan MVP

Auto-trading, jaminan profit, rekomendasi dengan informasi nonpublik, pengelolaan dana, prediksi harga pasti, sosial trading, berita pada UI, dan klaim jumlah pembeli/penjual unik tanpa data identitas yang mendukung.

## 3. Alur pengguna

1. Pengguna mengatur nominal transaksi, biaya broker, dan batas risiko.
2. Dashboard menampilkan kandidat yang lolos kriteria. Daftar boleh kosong.
3. Pengguna memilih saham untuk melihat chart dan rencana transaksi.
4. Pengguna mengaktifkan pemantauan. Saat pemicu entry terpenuhi, sistem mengirim notifikasi.
5. Setelah membeli di broker, pengguna mencatat pengisian aktual. Sistem menghitung ulang rencana berdasarkan posisi nyata.
6. Sistem mengirim perubahan penting: target, stop, exit waktu, pelemahan tren, pembatalan, atau data terputus.
7. Pengguna mengonfirmasi penjualan aktual atau posisi tersisa. Hasil aktual dan simulasi disimpan terpisah.

Tidak ada posisi nyata yang dianggap terbuka hanya karena harga chart menyentuh entry. Pesanan dapat tidak terisi atau terisi sebagian.

## 4. Struktur antarmuka

### A. Dashboard

Header ringkas: pencarian ticker, status sesi, status Live/Delayed/Terputus, waktu data terakhir, dan pengaturan nominal.

Setiap baris atau kartu saham menampilkan:

| Elemen | Definisi |
|---|---|
| Kode dan harga | Harga transaksi terakhir dan perubahan hari ini |
| Mini chart | Riwayat harga singkat; tidak mencampur harga aktual dengan proyeksi |
| Estimasi kenaikan | Median estimasi return dari entry acuan ke horizon yang disebutkan, dengan rentang ketidakpastian |
| Peluang target | Probabilitas TP1 tercapai sebelum stop dan batas waktu setelah pengisian entry, sesuai asumsi simulasi |
| Peluang masuk | Estimasi pesanan terisi sesuai nominal, tipe order, batas slippage, dan tenggat |
| Peluang keluar | Estimasi penjualan posisi terisi dalam kondisi pasar saat penilaian; bukan janji likuiditas masa depan |
| Entry | Zona harga dan status Tunggu/Siap masuk/Kedaluwarsa |
| Stop dan target | Stop loss, TP1, TP2 jika didukung, dalam rupiah dan persentase |
| Waktu | Jendela entry dan batas waktu exit dalam WIB |

Urutan default memakai estimasi nilai hasil bersih yang mempertimbangkan risiko serta fill, bukan persentase kenaikan terbesar. Filter minimal: pencarian, watchlist, dan kandidat aktif. Filter lanjutan tidak memenuhi halaman utama.

### B. Detail saham

- Chart candlestick dengan volume; interval 1m, 5m, 15m jika data mendukung.
- Garis entry, stop, TP, serta waktu kedaluwarsa.
- Area proyeksi setelah waktu sekarang dengan median dan rentang prediksi berlabel tingkat cakupan. Proyeksi menggunakan garis putus-putus dan latar berbeda.
- Zoom chart atau pergantian interval tidak otomatis mengubah horizon prediksi.
- Kartu rencana: harga, estimasi hasil setelah biaya, nominal/lot, jendela entry, deadline exit, dan status.
- Order book minimal 5 tingkat jika feed tersedia: harga, lot, total kumulatif, spread, waktu snapshot. Kedalaman terbatas diberi label.
- Tekanan beli/jual berbasis volume transaksi agresif dalam jendela 1/5/15 menit.
- Riwayat singkat perubahan sinyal dan notifikasi posisi.

Tidak menampilkan berita, sentimen mentah, daftar sumber berita, atau detail komputasi pada halaman pengguna. Jejak sumber tetap tersedia untuk audit internal.

### C. Bahasa dan keadaan kosong

Gunakan “Estimasi”, “Peluang”, dan “Jendela entry”, bukan “Pasti naik” atau “Jam profit”. Keadaan wajib: memuat, belum ada kandidat, pasar tutup, data delayed, data kedaluwarsa, model belum tervalidasi, dan koneksi terputus. Nilai yang tidak tersedia ditampilkan “Tidak tersedia”; tidak diganti angka rekaan.

## 5. Definisi angka agar tidak menyesatkan

### Estimasi kenaikan

Rujukan harga adalah entry yang diusulkan sebelum transaksi, atau harga pengisian aktual setelah transaksi. Selalu cantumkan horizon dan apakah hasil sudah dikurangi biaya. Harga terakhir tidak boleh diam-diam digunakan sebagai pengganti entry.

### Peluang masuk dan keluar

Probabilitas hanya ditampilkan jika model fill sudah dikalibrasi dengan data yang memadai. Kondisikan pada nominal, jenis limit order, snapshot pasar, tenggat, dan batas slippage. Dengan snapshot dangkal yang tidak mendukung inferensi antrean, tampilkan kategori likuiditas berdasarkan ukuran posisi, bukan persentase fill yang tidak teruji.

Peluang keluar saat ini tidak berarti peluang keluar di masa depan ketika harga ARB. Nilai dapat berubah cepat ketika likuiditas menghilang.

### Persentase beli/jual

Setiap transaksi memiliki pembeli dan penjual. Yang dapat diestimasi adalah pihak agresor transaksi, bukan proporsi jumlah orang yang membeli dibanding menjual.

buy_pressure = volume transaksi buyer-initiated / volume transaksi yang berhasil diklasifikasikan. sell_pressure = 1 - buy_pressure. Tampilkan cakupan klasifikasi dan periode waktunya. Jika feed tidak memberi agresor, gunakan metode klasifikasi teruji dengan label “Estimasi”; trade ambigu masuk kategori tidak diketahui. Jika cakupan kurang dari ambang validasi, sembunyikan persentase.

Order-book imbalance adalah metrik berbeda: jumlah lot bid / (jumlah lot bid + jumlah lot ask) pada kedalaman yang tersedia. Bila ditampilkan, namai “Komposisi antrean”, jangan “Persentase pembeli”.

### Waktu entry/exit

Tampilkan jendela probabilistik, misalnya “Pantau entry 10.00–10.15 WIB, jika pemicu terpenuhi”. Waktu tertentu hanya boleh diusulkan bila ada model atau kebijakan yang tervalidasi. Jika bukti tidak memadai, tampilkan kondisi harga/tren dan batas berlaku, tanpa membuat jam presisi palsu.

## 6. Persyaratan fungsional

| ID | Persyaratan | Kriteria penerimaan |
|---|---|---|
| FR-01 | Screener memperbarui seluruh universe yang didukung | Setiap kandidat memiliki snapshot data, versi model, horizon, dan valid_until |
| FR-02 | Filter kelayakan data dan perdagangan | Saham dengan data tidak cukup, suspensi, aturan belum didukung, atau spread/likuiditas tidak layak tidak mendapat sinyal entry aktif |
| FR-03 | Ranking sesuai nominal pengguna | Perubahan nominal memicu perhitungan ulang kapasitas, slippage, dan kelayakan; hasil tidak menggunakan cache nominal pengguna lain |
| FR-04 | Rencana entry bersyarat | Terdapat zona harga, pemicu, invalidasi, dan waktu kedaluwarsa |
| FR-05 | Stop dan TP | Seluruh level valid terhadap fraksi, rentang harga, biaya, dan kebijakan risiko; rencana ditolak jika target tidak layak |
| FR-06 | Pemantauan posisi nyata | Gunakan harga/lot pengisian pengguna dan dukung posisi parsial |
| FR-07 | Chart aktual dan proyeksi | Pemisahan visual jelas dan proyeksi tidak mengubah data historis |
| FR-08 | Order book | Harga/lot berasal dari snapshot konsisten; missing update memicu resinkronisasi |
| FR-09 | Tekanan beli/jual | Metode, jendela, serta cakupan klasifikasi benar; tidak mengklaim jumlah investor |
| FR-10 | Notifikasi | Entry aktif, invalidasi, TP, stop, time exit, dan gangguan data; deduplikasi per sinyal/peristiwa |
| FR-11 | Mode replay/paper trading | Terpisah jelas dari live; tidak menghasilkan notifikasi live atau order nyata |
| FR-12 | Audit | Semua versi sinyal dan pembatalan tersimpan append-only beserta alasan internal |

## 7. Kebijakan keputusan dan risiko

Sinyal memiliki status: WATCH → READY → EXPIRED/CANCELLED. Posisi merupakan entitas terpisah: OPEN/PARTIAL → EXIT_REQUESTED → CLOSED. READY tidak otomatis membuka posisi. Pencatatan fill aktual memulai pemantauan posisi. State transition harus deterministik, dapat direplay, dan idempotent.

Kandidat lolos jika estimasi keuntungan bersih, ketidakpastian, likuiditas, risiko penurunan, dan kualitas data memenuhi kebijakan yang dibekukan sebelum pengujian akhir. Target ARA menjadi atribut tambahan bila modelnya tervalidasi; ARA bukan tujuan wajib ranking.

Ukuran posisi dibatasi minimum dari: kapasitas kas, anggaran risiko dibagi jarak stop plus estimasi friksi, dan kapasitas likuiditas. Pembulatan lot serta biaya dihitung kembali. Parameter awal paper trading: risiko rencana 0,5% modal per posisi, maksimum 1% jika disetujui kebijakan, maksimum tiga posisi, maksimum risiko rencana gabungan 2%. Parameter ini adalah batas desain, bukan batas kerugian yang dijamin; gap dan kegagalan exit dapat melampauinya.

Stop menggunakan struktur harga dan volatilitas yang diuji. TP mempertimbangkan distribusi hasil, resistansi, batas perdagangan, dan biaya. Model boleh menolak transaksi walaupun peluang kenaikan tinggi. Stop tidak diperlebar otomatis untuk menyembunyikan kerugian. Perubahan stop/target untuk posisi aktif memiliki versi dan notifikasi; trailing stop hanya bergerak memperkecil risiko sesuai kebijakan.

Menjelang penutupan, blok entry baru sesuai cutoff yang tervalidasi dan sarankan exit sebelum tenggat internal. Posisi yang gagal keluar tetap ditandai terbuka beserta risiko overnight; sistem tidak menganggap posisi terjual pada harga penutupan.

## 8. Data dan pemrosesan real-time

### Sumber

1. Feed pasar berlisensi: transaksi, harga, order book, referensi instrumen, kalender, sesi dan status perdagangan.
2. Historis point-in-time: tick/order book jika tersedia, candle, perubahan simbol, delisting, dan aksi korporasi.
3. Keterbukaan emiten dan informasi resmi.
4. Berita berizin dan data global yang relevan terhadap emiten/sektor.

Satu feed bursa otoritatif yang memenuhi kebutuhan lebih berguna daripada kewajiban tiga situs harga yang mungkin berbagi upstream dan berbeda timestamp. Hak penyimpanan, penggunaan analitis/non-display, display, dan redistribusi harus dikonfirmasi pada kontrak vendor.

### Timestamp dan kualitas

Simpan event_time, provider_time bila ada, received_at, available_at, processed_at, serta sequence. Waktu disimpan UTC, ditampilkan WIB. Backtest hanya menggunakan informasi setelah available_at. Tangani pesan ganda, out-of-order, clock skew, corporate action, gap, dan koreksi sumber.

Adapter harus menyediakan heartbeat/status feed. Saham sepi transaksi tidak otomatis dianggap feed mati hanya karena harga terakhir lama. Freshness dinilai melalui kesehatan stream, snapshot, dan timestamp yang sesuai.

### Target awal operasional, bukan janji vendor

- Pemrosesan sinyal setiap 5 detik untuk universe yang didukung; pembaruan segera untuk peristiwa risiko penting.
- Pembaruan UI dibatasi sekitar 1 detik agar stabil; peristiwa kritis diprioritaskan.
- Latensi received_at ke tampilan p95 ≤2 detik pada beban pilot yang ditetapkan.
- Feed live dengan gap/heartbeat melewati 10 detik masuk status degraded sementara sampai resinkronisasi; nilai final ditentukan kontrak feed dan uji beban.
- Keterlambatan provider dipantau terpisah dari latensi internal. Mode delayed selalu diberi label dan tidak menghasilkan sinyal entry real-time.
- Berita diproses event-driven atau polling sesuai izin dan SLA sumber; tidak diklaim tersedia seketika setelah kejadian dunia.

Jika input kritis tidak sehat, tahan sinyal baru dan beri peringatan pada posisi aktif. Jangan menciptakan rekomendasi keluar dari data kedaluwarsa. Jangan otomatis mengganti feed dengan sumber yang berbeda semantik tanpa validasi.

## 9. Mesin analisis internal

Baseline pertama: aturan tren/momentum/volatilitas sederhana dan model statistik terkalibrasi. Model yang lebih kompleks hanya dipromosikan bila memberikan perbaikan out-of-sample setelah biaya.

Kelompok fitur: return dan volatilitas, volume relatif terhadap jam yang sama, spread/depth/imbalance, laju transaksi, konteks indeks/sektor, aksi korporasi, serta peristiwa berita. Ketersediaan fitur harus identik antara riset dan live.

Model terpisah untuk distribusi return, TP-before-stop, risiko penurunan, dan fill/likuiditas bila data mendukung. Menggabungkan probabilitas wajib menguji ketergantungan antar-kejadian; jangan mengalikan peluang seolah independen tanpa bukti.

LLM hanya membantu ekstraksi emiten/peristiwa dari teks dan ringkasan internal. Harga, biaya, sizing, fraksi, dan hasil simulasi dihitung kode deterministik. Berita dideduplikasi, dipetakan ke entitas, dinilai kredibilitas/relevansi dan waktu pertamanya; informasi tanpa verifikasi diperlakukan berbeda. Konten eksternal adalah data tidak tepercaya, tidak boleh menjadi instruksi sistem atau memicu tool/action.

Model memprediksi informasi yang mungkin belum tercermin dalam harga; sentimen positif saja tidak cukup untuk entry. Ukur kontribusi berita terhadap baseline melalui ablation test. Jika berita tidak menambah kualitas, jangan memaksakan penggunaannya sebagai sumber sinyal.

## 10. Pengujian strategi dan gerbang peluncuran

### Protokol wajib

- Pembagian waktu train/validation/test, dengan holdout akhir terkunci; gunakan walk-forward dan purge/embargo sesuai horizon label yang tumpang tindih.
- Universe historis mencakup emiten yang keluar/suspensi; hindari survivorship bias.
- Versikan fraksi, batas ARA/ARB, kalender, dan aksi korporasi berdasarkan tanggal berlaku. Jangan hardcode satu aturan untuk semua masa.
- Biaya broker/pajak/levy sesuai konfigurasi berlaku, spread, slippage, latensi, dampak posisi, antrean, partial fill, unfilled, dan gagal keluar disimulasikan.
- Bila stop dan TP tersentuh dalam satu candle tanpa urutan intrabar, gunakan data lebih rinci atau asumsi konservatif yang dilaporkan.
- Rekam seluruh eksperimen dan parameter agar pemilihan hasil terbaik tidak tersembunyi.
- Monte Carlo hingga 100.000 skenario bila dibutuhkan: bootstrap blok untuk ketergantungan waktu, variasi biaya/latensi/fill, dan stress likuiditas. Jumlah simulasi bukan jumlah observasi pasar independen dan tidak menggantikan holdout.

### Metrik

Hasil bersih setelah biaya, expectancy, distribusi kerugian dan drawdown, tail loss, turnover, fill rate, time-to-fill, slippage, precision kandidat, TP-before-stop, coverage/abstention, Brier score/reliability probabilitas, serta cakupan rentang proyeksi. Laporkan menurut kondisi pasar, likuiditas, horizon dan ukuran posisi. Win rate bukan sasaran tunggal.

### Gerbang terurut

G0 Data: kontrak/hak data jelas; feed dan historis lolos quality check; biaya vendor serta batas kapasitas diketahui.

G1 Riset: baseline dan model diuji pada holdout terkunci. Kandidat hanya maju bila expectancy bersih positif dengan interval keyakinan yang memperhitungkan dependensi waktu, kinerja risiko memenuhi anggaran yang dibekukan sebelum evaluasi, dan hasil tidak hanya bergantung pada satu periode/saham. Jika bukti belum cukup, tetap berstatus eksperimen.

G2 Paper live: minimum awal 60 sesi bursa dan 300 transaksi simulasi yang layak dieksekusi, mana yang lebih lama. Jumlah ini batas observasi awal, bukan bukti otomatis. Periksa ketergantungan antarsinyal dan kecukupan sampel efektif. Tetapkan toleransi kalibrasi/fill/drawdown dari validasi sebelum mulai periode ini; semua nilai dan hasil wajib dicatat.

G3 Pilot: seluruh kriteria terukur dipenuhi, gangguan feed/recovery lolos, pembatasan penggunaan dan kajian legal sesuai distribusi produk selesai. Jika tidak lolos, UI riset boleh berjalan dengan label eksperimen dan tanpa klaim sinyal layak transaksi nyata.

Tidak ada auto-promotion berdasarkan training harian. Gunakan model champion/challenger, persetujuan rilis internal, canary, dan rollback. Drift memicu evaluasi atau abstention, bukan retraining tanpa pengawasan lalu langsung dipakai.

## 11. Arsitektur yang disarankan

Mulai dengan modular monolith dan worker, hindari microservices berlebihan untuk pilot.

Feed vendor → adapter/normalisasi → event log → feature engine → model/risk engine → snapshot sinyal → API/WebSocket → web.

Informasi resmi/berita → ekstraksi/deduplikasi/penilaian → penyimpanan point-in-time → fitur internal. Jalur berita tidak menghambat ingest pasar.

Pilihan awal: Next.js + TypeScript untuk UI; Python/FastAPI untuk API analisis dan worker; PostgreSQL dengan dukungan time-series bila volume memerlukannya; Redis untuk cache/publish; object storage untuk data mentah, dataset, dan artefak model. Chart candlestick memakai library yang lisensinya sesuai. Pilihan versi library dibekukan pada implementasi setelah verifikasi dokumentasi terkini.

WebSocket memakai snapshot awal + delta dengan sequence/cursor. Setelah reconnect, klien resinkronisasi sebelum menampilkan data live. Pisahkan lingkungan riset, paper, dan produksi; paper/live memiliki namespace data dan alert berbeda.

## 12. Kontrak data minimum

| Entitas | Field penting |
|---|---|
| InstrumentRule | symbol, board, effective_from/to, tick_rule, limit_rule, session/calendar, tradability |
| MarketEvent | symbol, event_type, event_time, received_at, sequence, source, payload, quality |
| NewsEvent internal | entity_ids, published_at, first_seen_at, available_at, source_ref, dedup_id, event_type, confidence |
| SignalVersion | signal_id, version, symbol, generated_at, data_as_of, valid_until, horizon, model_version, state, entry_zone, trigger, stop, targets, return_quantiles, target_probability, assumptions |
| LiquidityEstimate | signal_version, nominal, lots, depth_as_of, order_policy, deadline, slippage_cap, category, fill_probability nullable, quality |
| Position | user_id, symbol, fills, remaining_lots, average_price, fees, opened_at, plan_version, status |
| Alert | event_id, user_id, signal/position_ref, type, created_at, delivered_at, status |
| Experiment | dataset_version, code_version, split, parameters, assumptions, metrics, promotion_decision |

Nilai uang memakai tipe desimal presisi tetap atau satuan integer yang sesuai; jangan float untuk pembukuan. Harga, persentase, dan unit lot diberi tipe/unit eksplisit. Probability nullable ketika belum tervalidasi; tidak diisi nol seolah hasil model.

API minimum: daftar kandidat, detail saham, snapshot/depth, chart aktual/proyeksi, watchlist, konfigurasi risiko, pencatatan fill, riwayat sinyal, dan stream peristiwa. Respons mencantumkan as_of, mode, kualitas, serta versi kontrak. Jangan mengirim dokumen berita internal ke browser.

## 13. Notifikasi dan keamanan

Notifikasi in-app wajib; browser push opsional dengan izin pengguna. Alert tidak menjamin diterima tepat waktu ketika perangkat offline. Gunakan deduplikasi, cooldown untuk perubahan kecil, hysteresis agar sinyal tidak berkedip, serta prioritas untuk risiko/data terputus.

Rahasia vendor hanya di server; autentikasi, otorisasi per pengguna, TLS, rate limit, validasi input, dan audit akses. Data posisi pengguna diisolasi dan dapat diekspor/dihapus sesuai kebijakan retensi. Log tidak menyimpan token. Batasi akses dokumen eksternal, ukuran, format, dan URL untuk mencegah injeksi serta akses jaringan internal. Anggaran pemanggilan sumber/LLM dibatasi dan dimonitor.

Admin memantau feed lag/gap, kandidat aktif, alert gagal, input missing, drift, latency, kapasitas dan biaya. Kill switch menahan rekomendasi baru sambil mempertahankan visibilitas posisi dan status gangguan. Backup dan restore diuji sebelum pilot.

## 14. Acceptance test utama

1. Feed putus: dalam ambang deteksi yang disepakati, status berubah, entry dibekukan, posisi mendapat peringatan; tidak ada angka pengganti rekaan.
2. Saham tidak bertransaksi tetapi heartbeat sehat: tidak salah ditandai koneksi terputus; usia transaksi tetap terlihat.
3. Nominal diperbesar: sistem mengubah estimasi kapasitas/slippage atau menolak kandidat ketika melewati likuiditas.
4. Antrean ARA tanpa penjual: simulasi tidak menganggap pembelian otomatis berhasil.
5. ARB tanpa pembeli: stop terpicu tidak dianggap penjualan berhasil; posisi tetap terbuka.
6. Berita terlambat masuk: backtest tidak memakai informasi sebelum available_at.
7. Reconnect/out-of-order: book direkonsiliasi dan tidak menampilkan depth campuran versi.
8. Pengguna mencatat partial fill: risiko dan exit dihitung atas lot nyata, bukan seluruh rencana.
9. Proyeksi: riwayat sinyal tidak berubah mengikuti hasil yang sudah diketahui; proyeksi kedaluwarsa diarsipkan.
10. Tekanan beli/jual: data tidak terklasifikasi tidak disulap menjadi jumlah investor.
11. Sinyal berubah: versi baru tercatat dan notifikasi penting diterima maksimal satu kali per event di tiap kanal.
12. Layar mobile 360px: angka inti terbaca, chart dapat disentuh, detail book tidak menutupi rencana.

## 15. Tahapan implementasi dan deliverable

Fase A — Data dan spesifikasi: pilih vendor, uji sample feed/historis, pastikan lisensi, tetapkan biaya dan universe, definisikan label serta kebijakan risiko. Hasil: adapter proof-of-concept, audit data, dan protokol evaluasi terkunci.

Fase B — Baseline dan simulator: penyimpanan point-in-time, replay, biaya/fill, model baseline, dan laporan holdout. Hasil: keputusan lanjut/perbaiki berdasarkan G1.

Fase C — Web minimalis: dashboard, detail/chart/order book, watchlist, posisi manual, status data dan notifikasi. Data simulasi pengembangan harus berlabel dan tidak masuk jalur live.

Fase D — Integrasi live dan paper: monitoring, kalibrasi, stress test, serta observasi G2. Hasil: laporan prospektif dan bukti eksekusi simulasi.

Fase E — Pilot: rilis terbatas setelah G3; pemantauan hasil aktual dan rollback. Integrasi broker menjadi PRD terpisah jika kelak diminta.

Durasi dan biaya belum ditetapkan karena bergantung pada akses serta kualitas data. Pekerjaan UI dapat berjalan setelah kontrak data disepakati, tetapi tidak mendahului keputusan kelayakan strategi.

## 16. Keputusan terbuka dan default

| Keputusan | Default perencanaan | Syarat final |
|---|---|---|
| Vendor/data | Feed resmi atau redistributor resmi | Konfirmasi kemampuan, lisensi, SLA dan penawaran biaya |
| Kedalaman book | 5 tingkat untuk tampilan awal | Model fill numerik memerlukan bukti data lebih memadai |
| Modal/nominal | Wajib diatur sebelum estimasi eksekusi personal | Profil pilot pengguna |
| Biaya transaksi | Konfigurasi per broker | Tarif terverifikasi dan bertanggal berlaku |
| Distribusi | Pilot pribadi/terbatas | Kajian kewajiban bila publik/berbayar dan hak penayangan |
| Kanal alert | In-app | Push setelah izin pengguna |
| Horizon | Intraday, tanpa rencana overnight | Hasil validasi; posisi gagal exit tetap dilacak |
| Ambang model | Belum ditetapkan | Bekukan berdasarkan validasi sebelum holdout/paper |

## 17. Inspeksi repositori opsional

Repositori sapatekno/skill-saham ditinjau melalui halaman publik dan README, bukan audit kode lengkap. README mendeskripsikan analisis horizon tiga minggu; cakupan ini berbeda dari kebutuhan intraday dan eksekusi order book produk ini. Keputusan: tidak clone, install, menjalankan script, atau mengadopsi skill sebagai dependensi PRD. Jika dipertimbangkan saat implementasi, lakukan audit kode, dependensi, lisensi, sumber data, dan simulator terlebih dahulu. Tidak menganggap klaim README sebagai hasil pengujian independen.

## 18. Referensi dan batas verifikasi

- BEI — Layanan Data BEI: https://www.idx.id/id/produk/layanan-data-bei/ — dasar keberadaan produk real-time/delayed, market depth, data reference, dan lisensi display/non-display. Halaman juga mengumumkan penyesuaian katalog/biaya/ketentuan efektif 1 Januari 2027; kontrak yang melintasi tanggal itu harus diverifikasi ulang.
- BEI — Mekanisme dan Jam Perdagangan: https://www.idx.co.id/id/produk/mekanisme-dan-jam-perdagangan — rujukan untuk verifikasi aturan implementasi; PRD sengaja tidak membekukan persentase ARA/ARB.
- Repositori opsional: https://github.com/sapatekno/skill-saham — inspeksi terbatas halaman publik/README pada 12 November 2026.

Dokumen ini menetapkan kebutuhan dan gerbang keputusan. Belum ada vendor terhubung, model terlatih, backtest dijalankan, atau bukti profit. Klaim hasil hanya boleh diterbitkan setelah laporan pengujian yang dapat diaudit tersedia.
