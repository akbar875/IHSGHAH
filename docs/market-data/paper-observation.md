# SS-027 — Laporan observasi G2

Inspeksi 15 November 2026: issue #27 bergantung pada #26 yang masih **open**.
#8/G0 masih open, G1 SS-016 no-go; adapter prospektif, reservasi modal bersama,
toleransi hasil validasi dan acceptance E2E prospektif belum tersedia.
Tidak ada observasi prospektif yang dapat dikreditkan. Issue #27 tetap open.

## Cakupan implementasi

`application.observation` menyediakan penilaian internal atas manifest kampanye
dan receipt sesi yang diimpor. Ini fondasi pelaporan, bukan collector paper live.
Tidak ada akses feed, broker, ledger manual, kontrol operasi atau promosi model.
Kontrak v1 dan UI tidak berubah; rincian model tetap di artefak operator.

`Campaign` membekukan batas waktu, referensi validasi, tiga toleransi SS-026,
versi model/biaya, hash holdout, referensi asumsi dan kalender, minimum sesi/fill,
minimum sampel efektif, panjang blok bootstrap, jumlah draw dan seed.
Hash seluruh manifest harus disimpan **sebelum** observasi dimulai. Pembekuan
wajib mendahului waktu mulai. Minimum tidak bisa diturunkan dari **60 sesi DAN
300 transaksi paper layak eksekusi yang mendapat fill**. Percobaan tanpa fill
tetap dihitung untuk galat fill, tetapi tidak memenuhi minimum transaksi.

Toleransi yang belum diturunkan dari validasi tetap null, tanpa nilai default
buatan. Ubah model, biaya, holdout, toleransi, metode statistik atau jendela
observasi hanya lewat kampanye baru dengan alasan/review terpisah. Jangan
menghapus kampanye gagal atau memindahkan transaksi ke holdout baru diam-diam.

`append` mengembalikan rantai receipt baru, tanpa mengedit receipt lama.
Setiap entry mengikat nomor urut, hash kampanye, hash sebelumnya dan isi sesi.
Duplikat sesi/source receipt/trial, urutan mundur, versi berbeda, akhir pekan,
waktu tanpa zona, data masa depan dan outcome sebelum keputusan ditolak.
Tanggal keputusan dikelompokkan menurut Asia/Jakarta.

Rantai hash **bukan** penyimpanan WORM, autentikasi sumber atau bukti lisensi.
Operator harus mempertahankan manifest/head sebelumnya di penyimpanan audit
independen, memverifikasi receipt sumber dan sesi terhadap kalender BEI berizin.
Penggantian seluruh rantai beserta hash tidak dapat dideteksi tanpa anchor luar.
Integrasi journal persisten prospektif masih pekerjaan tersisa bersama #26.

## Ukuran dan ketidakpastian

Laporan mencatat rentang sesi, hari kalender inklusif, jumlah sesi/attempt/fill,
cluster sinyal, cluster terbesar dan ukuran efektif Kish `(sum n)^2 / sum(n^2)`.
Seluruh fill dalam cluster diperlakukan saling bergantung, termasuk lintas sesi.
Nilai ini diagnosis konsentrasi, bukan bukti independensi statistik; review
autokorelasi dan driver pasar bersama tetap diperlukan. Sesi tanpa trade dapat
dicatat, tetapi tidak menambah jumlah transaksi atau sampel efektif.

Brier memakai probabilitas dan label target dari fill terselesaikan. Probabilitas
null tidak diganti skor baseline. Galat fill adalah nilai absolut rata-rata
`filled - predicted_fill` pada **seluruh** attempt layak, termasuk unfilled;
ini probabilitas fill biner per attempt, bukan share-fill ratio. Breakdown jumlah
fill mencakup simbol, kondisi pasar, likuiditas dan nominal IDR.

Drawdown memakai snapshot ekuitas neto penutupan sesi relatif modal awal yang
dinormalisasi nol. Receipt harus mencakup biaya dan mark-to-market posisi terbuka
yang dibawa lintas sesi. Angka ini **tidak mencakup puncak intraday**; bukti jalur
ekuitas intraday/stress test tetap diperlukan sebelum penilaian operasional G2.
`Trial.net_equity_idr` hanya metadata kontribusi audit, bukan pengganti snapshot
portofolio atau sumber untuk menjumlahkan hasil manual dan paper.

Moving session-block bootstrap deterministik memberikan interval persentil 95%
untuk Brier, galat fill dan drawdown. Rekonstruksi drawdown memakai perubahan
ekuitas sesi, bukan level ekuitas yang diacak. Blok mempertahankan dependensi
lokal; tidak menjamin dependensi lintas blok atau kondisi pasar belum terlihat.
Interval baru dihitung setelah minimum sesi dan dua blok tersedia. Minimum
jumlah fill, sampel efektif dan kelengkapan outcome tetap diperiksa terpisah.

Nilai titik melebihi toleransi menghasilkan `breach`, G2 `no-go` dan alasan
stop/review. Nilai titik di bawah batas tetapi interval atas melewati batas,
atau interval belum tersedia, menghasilkan `uncertain`. Toleransi/ukuran kosong
menghasilkan `pending`. `within_tolerance` pada ukuran bukan keputusan lulus G2.
Sampel kurang, konsentrasi cluster, outcome hilang atau jendela belum berakhir
selalu tampil sebagai alasan belum cukup bukti.

Status maksimum implementasi ini **pending** meskipun semua ukuran berada dalam
toleransi. Label input `prospective` tidak membuktikan G0/G1/#26. Kredit G2 selalu
nol, `paper_live_enabled=false` dan `model_promoted=false`. Pelanggaran toleransi
menghasilkan no-go bahkan pada fixture, tanpa membuka jalur eksekusi.

## Command operator

Dari `services/api`, gunakan environment backend terkunci:

```sh
uv run --locked python -m saham_signal.observation ../../research/protocols/SS-027-empty.json --as-of 2026-11-15T00:00:00+00:00
uv run --locked pytest tests/test_observation.py
```

Input JSON hanya berisi `campaign`, `campaign_sha256`, dan `entries`.
Schema tersedia lewat `Campaign.model_json_schema()` dan `Entry.model_json_schema()`.
Gunakan `append` untuk membuat entry baru; simpan hasil dan anchor hash ke journal
operator. CLI hanya membaca input, memverifikasi seal/rantai, dan mencetak JSON
laporan dengan hash. Gagal validasi menghasilkan exit nonzero dengan pesan yang
tidak mencetak payload pribadi. Tidak ada opsi untuk memulai paper live.

Fixture kosong pada repo berlabel simulation dan tidak memiliki toleransi atau
referensi validasi. Contoh laporan ada di [SS-027-pending.json](../../research/reports/SS-027-pending.json).
Tanggal jendelanya hanya contoh format, bukan jadwal observasi yang disetujui.

## Syarat penyelesaian issue

Selesaikan dependency #26 dan bukti G0/G1, turunkan/review toleransi dari validasi,
bekukan manifest dan review desain dependensi/ketidakpastian sebelum mulai.
Hubungkan collector serta penyimpanan append-only terverifikasi ke jalur paper
prospektif; kumpulkan sekurangnya 60 sesi dan 300 transaksi layak selama jendela
beku, lanjutkan jika bukti efektif belum cukup. Sertakan kalender, provenance,
versi, biaya, kondisi pasar, ekuitas intraday, kasus unfilled/open dan receipt
stop/review. Buat laporan review G2 berbasis bukti tersebut; minimum hitungan
dan status closed issue implementasi tidak otomatis meluluskan gerbang.
