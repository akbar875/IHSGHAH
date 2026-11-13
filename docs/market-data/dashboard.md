# Dashboard kandidat — SS-018

Issue #18 mengganti shell persiapan dengan dashboard research. Dependency #3 dan
#17 tersedia. G0/G1 masih pending/no-go; dashboard tidak mengaktifkan paper/live.

Daftar mempertahankan urutan respons layanan, dengan nomor urut asal yang tidak
berubah saat difilter. Fixture hanya satu skenario TEST, bukan ranking model yang
tervalidasi. Setiap kartu memuat label simulasi, nominal, status, zona entry,
stop/target, horizon, peluang target, estimasi hasil, dan waktu WIB. Nilai null
ditulis **Tidak tersedia**. API kandidat belum menyediakan harga terakhir,
perubahan harian, mini chart atau peluang fill; UI tidak mengarang nilai tersebut.
Detail saham dan watchlist mengikuti issue #19/#20.

Input nominal rupiah bulat 1–999999999999 baru diterapkan setelah tombol Terapkan
atau Enter. UI mengirim decimal dua digit ke GET `/api/v1/candidates`, memakai
`credentials: include` dan `cache: no-store`. Input invalid tidak mengirim request.
Perubahan nominal membatalkan request sebelumnya, menyembunyikan hasil sebelumnya,
dan menolak respons dengan nominal berbeda. Akun/mode tetap milik server. Fixture
hanya menyesuaikan asumsi nominal, belum menghitung kapasitas/slippage/kelayakan
personal; seluruh probabilitas tetap null.

Pencarian ticker tidak peka huruf besar/kecil dan filter aktif menerima WATCH/READY
yang belum melewati `valid_until` maupun `entry_until`. Timer lokal menandai rencana
kedaluwarsa tanpa menunggu refresh. Permintaan snapshot penuh berjalan setiap 15
detik, timeout 10 detik, dengan maksimal satu request aktif. Polling dipilih untuk
scope nominal per request; dashboard tidak menggabungkan stream default nominal
server dengan daftar nominal pengguna. Unmount/pergantian input membersihkan timer
dan request; kegagalan membuang daftar lama dan menyediakan tombol Coba lagi.

Pesan pasar tutup, delayed, stale, terputus, unavailable dan model belum tervalidasi
berasal dari metadata kualitas. Sesi yang tidak disediakan kontrak tampil Tidak
tersedia, tidak ditebak dari jam perangkat. Status buruk/model belum tervalidasi
menampilkan Entry ditahan; READY tetap tidak membuka posisi. Tidak ada berita atau
detail model internal pada tampilan. Mode selain research/simulation, versi kontrak
lain, payload tambahan dan respons nominal salah ditolak sebelum render.

Tipe dihasilkan `json-schema-to-typescript` dari schema canonical SS-002. Generator
juga mengekstrak hanya definisi publik kandidat ke schema runtime lokal agar bundle
tidak membawa schema internal. Ajv2020 + ajv-formats memvalidasi setiap respons;
`npm run contracts:check` mendeteksi generated files yang tertinggal.

## Verifikasi

`npm --prefix apps/web run check` memeriksa generator, lint, tipe dan build.
`npm --prefix apps/web test` menguji browser produksi: loading/retry, empty,
closed/delayed/stale/disconnected, null, nominal/refetch, race, respons invalid,
expiry, pencarian/filter dan layout 360px. Jalankan `npx playwright install chromium`
dari apps/web sebelum test pertama. CI menginstal Chromium beserta dependency Linux.
Test memakai fixture sintetis yang dimock di batas HTTP, bukan feed vendor.

Test backend `test_market_api.py` menguji nominal valid/invalid/duplikat, default,
isolasi cache dan metadata. Setup API/sesi lokal mengikuti
[panduan API market](market-api.md). Gunakan hostname yang sama pada web dan API
(mis. keduanya `127.0.0.1`) agar cookie sesi loopback tersedia; token tidak boleh
masuk `NEXT_PUBLIC_*`, URL atau bundle. Tidak ada login atau auto-session baru.

Screenshot verifikasi: [mobile 360px](../screenshots/SS-018-mobile.png) dan
[desktop](../screenshots/SS-018-desktop.png), seluruhnya simulasi.
