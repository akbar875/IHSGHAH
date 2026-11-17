# Bundled public daily research data

`idx-daily.json` is an actual validated Aethereal IDX Stock Features snapshot,
distributed under CC BY 4.0, not simulation data. Attribution and source links are
included in the file and displayed with stock details.

- Source: https://dataset.aethereal.top/datasets/idx-stock-features
- Download: https://dataset.aethereal.top/files/idx-stock-features.csv
- License: https://creativecommons.org/licenses/by/4.0/
- Observed import: 2026-11-17 13:33:58 UTC
- Latest daily date: 2026-11-16; 114 symbols; 303,857 accepted rows.
- Original source SHA-256: `8696a6df0c14b3aafc535220733f6b417eb9168e6f8a351e1a3c2f1a49250b4e`

The snapshot contains daily close/volume history and exploratory backtests. It
does not contain intraday prices, OHLC candles, an order book, or personal data.
Dates and stale-data warnings remain visible. The API uses this file when no
existing operator snapshot is configured; corrupt configured files still fail.

To update explicitly, from `services/api`, run:

```sh
python -m saham_signal.eod --download --output src/saham_signal/resources/idx-daily.json
```

Review the validation receipt, update this note, and redeploy. Refresh in the
browser reloads the deployed snapshot; it does not download a newer provider file.
