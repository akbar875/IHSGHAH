# SS-015 — Risk engine dan state rencana

`saham_signal.application.risk` menyediakan reducer rencana long-only deterministik
untuk research/paper. Dependensi SS-009, SS-010 dan SS-012 tersedia. Implementasi ini
tidak membuka posisi, membuat Fill, mengirim order, atau menyalakan alert live.
G0/G1 serta bukti vendor tetap pending; kelulusan test simulasi tidak melewati gerbang.

## Input dan ukuran rencana

`PlanSpec` memuat akun/mode, simbol, harga entry/stop/target IDR integer, pemicu,
invalidasi, jendela entry, expiry, cutoff, deadline exit, dan estimasi friksi Decimal.
Jendela bersifat half-open; pada expiry/cutoff rencana kedaluwarsa. Seluruh tenggat
berada pada tanggal WIB yang sama. Tidak ada jam entry/exit default yang diklaim
tervalidasi: pemanggil memasok tenggat dari kebijakan yang dibekukan sebelum evaluasi.

`RiskInputs` memuat waktu keputusan, snapshot portofolio, assessment SS-012,
bid/ask dan timestamp snapshot yang juga menyediakan kapasitas saham executable,
serta hasil evaluasi pemicu/invalidasi. Kapasitas harus sudah konservatif terhadap
antrean, partisipasi dan slippage; raw displayed depth bukan jaminan fill.
Portofolio, assessment dan quote harus tersedia pada waktu keputusan dan tidak
lebih tua dari batas konfigurasi. Referensi instrumen dan biaya dipilih point-in-time.

Engine menolak data buruk/delayed, lingkup akun/mode salah, suspensi, board/sesi
tak didukung, aksi korporasi unresolved, tick/limit salah, bracket tak berurutan,
spread berlebih, ask di atas limit entry, biaya hilang/ambigu atau tidak mencakup
deadline, serta deadline exit di luar sesi kontinu. Data sintetis hanya diterima
di research/paper bila satu-satunya alasan SS-012 adalah `SIMULATION`; gangguan
feed tambahan tetap menahan entry. Mode live selalu ditolak sampai gerbang terkait
diimplementasikan dan dibuktikan terpisah.

Untuk `q = lots × lot_shares`:

```text
cash   = entry × q + buy_fee(entry × q)
friksi = (ask - bid + friction_per_share) × q
risk   = (entry - stop) × q + buy_fee + sell_fee(stop × q) + friksi
reward = (target - entry) × q - buy_fee - sell_fee(target × q) - friksi
budget = min(capital × risk_fraction,
             capital × combined_fraction - committed_risk_other)
```

Binary search lot integer mencari ukuran terbesar yang memenuhi kas bebas,
budget dan kapasitas likuiditas. Minimum fee serta pembulatan ke atas 0,01 IDR
dihitung ulang pada setiap kandidat menggunakan `FeeSchedule` SS-014. Keputusan
ditolak bila reward bersih tidak positif atau reward/risk kurang dari policy.
Tidak ada float dalam perhitungan uang. Estimasi satu entry/satu exit ini bukan
jaminan biaya: partial execution berulang, gap, slippage dan gagal exit dapat
membuat kerugian aktual melampaui estimasi.

`Portfolio` memasok kas bebas setelah reservasi, risiko dan slot dari **seluruh
posisi serta READY lain**, mengecualikan reservasi rencana yang sedang dievaluasi.
Partial fill dihitung atas saham aktual yang masih dipegang; failed exit tetap
terbuka dan memakai risiko/slot. Pemanggil wajib mengunci transaksi per akun/mode,
memuat snapshot terbaru, lalu mengganti reservasi lama dengan keputusan baru secara
atomik. Pure reducer ini tidak menggantikan ledger atau kontrol konkurensi database.

## State, versi dan replay

| State awal | Kondisi/perintah | State hasil |
|---|---|---|
| WATCH/READY | evaluate, seluruh syarat terpenuhi | READY |
| WATCH/READY | evaluate, syarat tidak terpenuhi | WATCH, lot reservasi nol |
| WATCH/READY | cancel atau invalidasi | CANCELLED |
| WATCH/READY | waktu mencapai expiry/cutoff | EXPIRED |
| EXPIRED/CANCELLED | perintah baru | tetap terminal |
| READY | trail valid dan syarat tetap terpenuhi | READY dengan stop/versi baru |

READY adalah rencana bersyarat, bukan pembelian. Posisi nyata hanya berasal dari
fill yang dicatat pengguna melalui batas pencatatan terpisah. Expiry/cancel rencana
tidak menghapus posisi atau fill yang sudah terjadi. Pemanggil harus mengirim
evaluasi berbasis jam walaupun tidak ada tick, agar READY tidak bertahan melewati
expiry. Pada expiry/cancel keputusan reservasi dibersihkan.

`PlanCommand` membawa ID idempotensi, expected_version, aksi dan snapshot input.
ID yang sama/payload sama tidak menambah versi; payload berbeda ditolak. Versi
optimistis dan waktu monoton mencegah stale update/out-of-order. Setiap perintah
unik yang diterima menambah versi, termasuk evaluasi tanpa perubahan state.
Policy lengkap dibekukan pada plan; perubahan policy membutuhkan plan baru.

Trailing stop hanya boleh naik, tetap di bawah entry serta valid terhadap tick dan
limit. Ukuran tidak boleh melebihi lot READY sebelumnya maupun kapasitas terbaru.
Seluruh pemeriksaan risiko dijalankan ulang. Ini adalah trailing **rencana**;
perubahan stop posisi aktual dan notifikasinya harus melalui service posisi/alert
terpisah, bukan menulis ulang fill historis.

`audit_document(plan)` menghasilkan JSON internal dengan versi engine, policy,
initial_spec, spec terkini, command/input lengkap, hasil, versi referensi/biaya dan
SHA-256. Simpan artefak bersama snapshot referensi/fee immutable melalui pola
artefak riset SS-010; ini bukan payload langsung `Signal` v1 dan tidak mengubah
kontrak publik. Jangan menaruh artefak akun pribadi di Git. Untuk replay:

```python
replayed = Plan(plan.initial_spec, policy=plan.policy)
for command in plan.commands:
    replayed = transition(replayed, command, frozen_references, frozen_fees)
assert audit_document(replayed) == audit_document(plan)
```

Service pemanggil wajib commit jurnal, versi plan dan reservasi sebelum
mempublikasikan READY. Endpoint bisnis, adapter ledger/reservasi dan notifikasi
runtime bukan bagian modul ini; tidak ada jalur produksi yang diaktifkan otomatis.

## Konfigurasi dan verifikasi

| Parameter | Default desain/provisional |
|---|---|
| Risiko rencana | 0,5% modal |
| Maksimum risiko per rencana | 1%, hanya melalui policy eksplisit |
| Risiko gabungan | 2% modal |
| Slot posisi dan READY | 3 |
| Minimum reward/risk bersih | 1 |
| Maksimum spread/ask | 1% |
| Umur maksimum input | 5 detik |

Parameter PRD adalah batas desain paper, **bukan batas kerugian yang dijamin**.
Reward/risk, spread, umur input, kapasitas, friksi, cutoff/deadline dan tarif biaya
memerlukan pembekuan/validasi tersendiri sebelum evaluasi holdout atau penggunaan
live; tidak ada klaim kualitas strategi dari nilai default ini.

Dari `services/api`, jalankan `uv run --locked pytest tests/test_risk.py -q`.
Skenario sintetis meliputi READY tanpa posisi, replay/idempotensi/konflik, terminal
state dan waktu, exact cash/risk/aggregate caps sampai pecahan IDR, lot/likuiditas,
biaya bertanggal/minimum, input buruk/future/stale, target tidak layak, policy
freeze, trailing tanpa pelebaran risiko/ukuran, serta audit yang dapat diulang.
