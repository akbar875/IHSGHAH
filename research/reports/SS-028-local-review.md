# SS-028 — Penutupan research lokal dengan keputusan no-go

Tanggal: 15 November 2026 (Asia/Jakarta). Pemilik memilih cakupan **research
lokal; pilot tetap no-go** dalam percakapan pekerjaan #28. Keputusan teknis G3
tetap no-go, dengan akbar875 sebagai penanggung jawab keputusan rilis.
Pemilihan cakupan bukan persetujuan menyalakan pilot.

## Batas penggunaan dan keputusan

- G0 intraday pending, G1 no-go dan G2 pending dengan nol kredit prospektif.
  Sumber Aethereal EOD hanya untuk evaluasi riset sesuai keputusan #8.
- Fixture/simulasi tidak dianggap feed pasar, persetujuan gerbang atau transaksi
  pengguna. Probabilitas belum tervalidasi unavailable/null; posisi manual dan
  paper tidak digabung. Tidak ada broker, promosi model atau canary pilot.
- Akun/mode diverifikasi server; sesi invalid/expired, TLS tidak sesuai dan
  akses runtime ke operasi operator ditolak. Kill switch/restore menahan entry
  dan tidak menutup posisi hanya karena warning atau stop terpicu.
- [Dokumen keputusan dan runbook](../../docs/market-data/pilot-readiness.md)
  tetap memuat prasyarat deployment/canary bila pilot kelak diusulkan. Bukti
  lokal di sini hanya mengkualifikasi pengembangan research.

## Bukti research lokal

PR #60 telah di-merge pada **`3fc42689a6dd94a719c5686ec8c9d3d09ae0de54`**
sebelum verifikasi final #28. Drill memakai PostgreSQL 18.7 ber-digest yang sama
dengan CI, container disposable dengan tmpfs dan port loopback. Tidak ada volume
pengguna, data posisi nyata atau database pilot yang dibaca/dimodifikasi.
Data pengujian sepenuhnya sintetis. Namespace paper dipakai hanya untuk tes
isolasi/bukti, tanpa mengaktifkan paper live.

Regresi `test_operations.py`, `test_security.py`, `test_observation.py`,
`test_market_api.py`, `test_paper_evidence.py`, dan `test_paper.py`:
**81 passed, 0 skipped**. Build web hasil PR #60 mempunyai tree `apps/web`
yang identik dengan merge tersebut (`d83c142e57ae25eb49118c5bdc512cfc14bf7b27`).
Tes browser label eksperimen/probabilitas unavailable dan kegagalan acceptance
kritis: **2 passed**. Bukti ini memperbarui drill awal 20 tes pada `741ec2c`.

Receipt restore final memeriksa **sepuluh tabel**, termasuk `paper_evidence`,
serta membuktikan baris sumber tidak berubah, target kembali
pause, retry tidak menggandakan event, cursor identity diteruskan, checksum
rusak/target berisi ditolak dan rollback transaksi restore bersifat atomik.
Role runtime tidak dapat mengambil backup operator. Bukti ini tidak mengukur
SLA/RTO/RPO atau deployment pilot. Uji evidence paper terpisah mengisi review
serta receipt, memverifikasi RLS/CAS dan memulihkannya ke schema kosong; laporan
fill tetap identik dan status tetap blocked setelah restore.

[Receipt agregat lokal](SS-028-local-qualification.json) mencatat jumlah tes,
hash artefak sumber, hasil restore dan dua fill replay versus satu fill manual
**sintetik**. Setelah satu skenario kritis dibuat gagal, acceptance_passed dan
can_advance menjadi false. Sebelum kegagalan pun can_advance tetap false karena
G0/G1 dan E2E berizin belum tersedia. Tidak ada angka hasil fixture yang
dikreditkan ke G2 atau diperlakukan sebagai hasil aktual pemilik.

## Reproduksi

Gunakan PostgreSQL disposable 18.7 dengan database `saham_signal_research` dan
`saham_signal_paper`. Set `PERSISTENCE_TEST_DSN` dan `PERSISTENCE_PAPER_TEST_DSN`
ke instance disposable, serta `OPERATIONS_RESTORE_REPORT` dan
`PAPER_EVIDENCE_REPORT` ke direktori artefak lokal di luar Git. Jangan gunakan
database berisi data pengguna. Dari root, gunakan Python environment backend
terkunci dan source/resource kontrak dari commit yang diuji:

```sh
python -m pytest services/api/tests/test_operations.py services/api/tests/test_security.py services/api/tests/test_observation.py services/api/tests/test_market_api.py services/api/tests/test_paper_evidence.py services/api/tests/test_paper.py -q --junitxml=.work/issue28-local-final.xml
```

Dari `apps/web`, sesudah build pada source yang sama dan Chromium tersedia:

```sh
node node_modules/@playwright/test/cli.js test tests/dashboard.spec.ts tests/paper.spec.ts --grep "simulation, null probabilities|critical acceptance failure"
```

Saat penutupan drill, container disposable dihentikan sehingga data tmpfs
hilang. Tidak ada backup pribadi, DSN, cookie atau salinan CSV vendor di repo.

## Penilaian acceptance dalam cakupan yang dipilih

| Kriteria | Hasil |
|---|---|
| Keputusan tertulis dan penanggung jawab | G3 no-go; akbar875 pemilik keputusan rilis |
| Recovery/rollback dan pembatasan penggunaan | Drill lokal pada hasil merge #60 lulus, termasuk restore/evidence/RLS/pause; bukan rollback binary/schema atau sertifikasi deployment pilot |
| UI tetap eksperimen | Dua tes browser lulus: label research/simulasi/probabilitas unavailable dan penahanan kegagalan kritis |
| Dokumentasi dan retensi disetujui | Default SS028-local-retention-v1 ditetapkan agen melalui delegasi pemilik untuk memilih best practice dan finalisasi research lokal/no-go |

## Paket persetujuan pemilik

Paket untuk review mencakup laporan ini, keputusan/runbook pilot dan kebijakan
retensi SS-023 yang dirujuk di sana. Lingkup persetujuannya menerima **no-go dan
research lokal**, termasuk batas sumber EOD, pencatatan manual yang terpisah,
retensi pribadi, serta larangan distribusi/retensi vendor yang belum berizin.
Approval ini tidak boleh ditulis sebagai G0/G1/G2 passed atau izin pilot.

Status paket lokal: **diterima melalui delegasi pemilihan kebijakan** pada
15 November 2026. Setelah paket commit `80b8029` dan seluruh CI tersedia, pemilik
menjawab permintaan persetujuan dengan “berikan best practice yang auto”. Agen
menafsirkan instruksi ini sebagai delegasi untuk memilih default dan menyelesaikan
#28 tanpa konfirmasi tambahan, lalu mencatat default SS-023 dalam
[SS028-local-retention-v1](../../docs/market-data/pilot-readiness.md).

Record ini menyimpan dasar delegasi apa adanya; tidak mengklaim tanda tangan
persetujuan legal/pilot atau bahwa pemilik memeriksa setiap nilai secara manual.
G0/G1/G2 dan persetujuan pilot tetap mengikuti bukti terpisah. Tidak ada janitor
terjadwal baru atau penghapusan ledger pengguna yang dijalankan.
