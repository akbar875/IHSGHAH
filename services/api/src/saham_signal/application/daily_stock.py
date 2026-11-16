"""Market-origin daily history and historical trade replay, without invented depth."""

from datetime import datetime
from pathlib import Path
from typing import Any

from saham_signal.application.eod import read_snapshot
from saham_signal.application.screener import screen


def stock_detail(snapshot: dict[str, Any], symbol: str) -> dict[str, Any]:
    row = next((row for row in snapshot["rows"] if row["symbol"] == symbol), None)
    if row is None:
        raise KeyError(symbol)
    plan = next((item for item in screen(snapshot)["rows"] if item["symbol"] == symbol), None)
    return {
        "origin": "market",
        "feed": "daily",
        "symbol": symbol,
        "date": row["date"],
        "as_of": snapshot["as_of"],
        "available_at": snapshot["available_at"],
        "stale": row["stale"],
        "close_idr": row["close_idr"],
        "history": row.get("history", []),
        "plan": plan,
        "backtest": row.get("backtest"),
        "order_book": None,
        "individual_queue": None,
        "depth_status": "feed_not_connected",
        "source": snapshot["source"],
        "license_url": snapshot["license_url"],
        "attribution": snapshot["attribution"],
    }


def read_daily_stock(path: Path, at: datetime, symbol: str) -> dict[str, Any]:
    return stock_detail(read_snapshot(path, at), symbol)
