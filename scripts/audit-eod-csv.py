"""Offline research audit. Never promotes a dataset to a live feed or G0 PASS."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def audit(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as raw:
        for block in iter(lambda: raw.read(65536), b""):
            digest.update(block)
    counts: Counter = Counter()
    symbols: Counter = Counter()
    dates: set[str] = set()
    seen: set[tuple[str, str]] = set()
    previous: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != FIELDS:
            raise ValueError("Unexpected EOD schema")
        for row in reader:
            counts["rows"] += 1
            if None in row or any(not row.get(field) for field in FIELDS):
                counts["missing_or_extra_fields"] += 1
                continue
            symbol, day = row["ticker"], row["date"]
            try:
                parsed_day = date.fromisoformat(day)
                if parsed_day.isoformat() != day:
                    raise ValueError("Noncanonical date")
            except ValueError:
                counts["invalid_date"] += 1
                continue
            symbols[symbol] += 1
            dates.add(day)
            key = (symbol, day)
            if key in seen:
                counts["duplicate_symbol_date"] += 1
            seen.add(key)
            if symbol in previous and day < previous[symbol]:
                counts["out_of_order_within_symbol"] += 1
            previous[symbol] = day
            if parsed_day.weekday() >= 5:
                counts["weekend_rows"] += 1
            try:
                values = {field: Decimal(row[field]) for field in FIELDS[2:]}
                if not all(value.is_finite() for value in values.values()):
                    raise InvalidOperation
            except InvalidOperation:
                counts["invalid_numeric"] += 1
                continue
            if any(values[field] <= 0 for field in FIELDS[2:7]):
                counts["nonpositive_price"] += 1
            if values["volume"] < 0 or values["volume"] % 1:
                counts["invalid_volume"] += 1
            if values["volume"] == 0:
                counts["zero_volume"] += 1
            if not (
                values["low"]
                <= min(values["open"], values["close"])
                <= max(values["open"], values["close"])
                <= values["high"]
            ):
                counts["invalid_ohlc_bounds"] += 1
            if values["adj_close"] != values["close"]:
                counts["adjusted_close_differs"] += 1
    if not counts["rows"]:
        raise ValueError("Empty dataset")
    metrics = [
        "rows",
        "missing_or_extra_fields",
        "invalid_date",
        "duplicate_symbol_date",
        "out_of_order_within_symbol",
        "weekend_rows",
        "invalid_numeric",
        "nonpositive_price",
        "invalid_volume",
        "zero_volume",
        "invalid_ohlc_bounds",
        "adjusted_close_differs",
    ]
    return {
        "schema_version": "ss008-eod-audit-1",
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
        "metrics": {name: counts[name] for name in metrics},
        "symbols": len(symbols),
        "distinct_dates": len(dates),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "min_rows_per_symbol": min(symbols.values()) if symbols else 0,
        "max_rows_per_symbol": max(symbols.values()) if symbols else 0,
        "g0": "PENDING",
        "live_eligible": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.csv_path), indent=2))
