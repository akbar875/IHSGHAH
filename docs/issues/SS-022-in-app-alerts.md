# SS-022 — Alert in-app dan deduplikasi event

Fase: C | Prioritas: P1

## Tujuan

Kirim notifikasi entry/risk/data dengan semantik yang tepat.

## Scope

- Implementasikan entry, invalidasi, target, stop, time exit dan gangguan feed.
- Tambahkan deduplikasi per event/kanal, cooldown/hysteresis dan prioritas.
- Push browser tetap opsional dan memerlukan izin jika dikerjakan berikutnya.

## Acceptance criteria

- [ ] Replay tidak mengirim alert live.
- [ ] Pengulangan event menghasilkan maksimal satu alert per kanal.
- [ ] Alert exit menjelaskan belum ada fill jual.
- [ ] Reconnect/retry tidak menggandakan notifikasi.
- [ ] Keterbatasan pengiriman ketika offline terlihat.

## Dependency

SS-005, SS-012, SS-015, SS-021

Dependency adalah prasyarat implementasi. Gerbang G0/G1/G2/G3 tetap mengikuti PRD dan harus dibuktikan terpisah sebelum pemakaian/rilis terkait.

## Referensi PRD

[PRD Saham Signal](../PRD-Saham-Signal.md): 13; FR-10; acceptance 1/11.

## Branch

`feat/<issue-number>-in-app-alerts`

Ganti `<issue-number>` dengan nomor issue GitHub sebenarnya. PR menautkan `Closes #<issue-number>`.
