"""Deterministic daily technical scenarios; targets are 2R, not price forecasts."""

from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

from saham_signal.application.eod import number, read_snapshot

METHOD = "ma-rsi-momentum-2r-v1"


def tick(price: Decimal) -> Decimal:
    for boundary, step in ((200, 1), (500, 2), (2000, 5), (5000, 10)):
        if price < boundary:
            return Decimal(step)
    return Decimal(25)


def rounded(price: Decimal, up: bool) -> Decimal:
    # Iterate when rounding crosses a price-band boundary.
    for _ in range(3):
        step = tick(price)
        price = (price / step).to_integral_value(
            rounding=ROUND_CEILING if up else ROUND_FLOOR
        ) * step
    return price


def screen(snapshot: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for row in snapshot["rows"]:
        if snapshot["stale"] or row["stale"] or row["date"] != snapshot["latest_date"]:
            continue
        technical = row.get("technical")
        if not technical or row["rsi_14"] is None or number(row["volume"]) <= 0:
            continue
        keys = ("sma_20", "sma_50", "sma_200", "ret_20d", "avg_value_20d_idr")
        if any(technical.get(key) is None for key in keys):
            continue
        try:
            ma20, ma50, ma200, momentum, turnover = (number(technical[k]) for k in keys)
        except (ValueError, TypeError):
            continue
        close, rsi = number(row["close_idr"]), number(row["rsi_14"])
        if close < 50 or min(ma20, ma50, ma200) <= 0 or turnover < 1_000_000_000:
            continue
        if close > ma20 > ma50 > ma200 and 50 <= rsi <= 70 and momentum > 0:
            direction = "bullish"
            stop = rounded(ma20 * Decimal("0.99"), False)
            risk = close - stop
            target = rounded(close + 2 * risk, True)
        elif close < ma20 < ma50 < ma200 and 30 <= rsi < 50 and momentum < 0:
            direction = "bearish"
            stop = rounded(ma20 * Decimal("1.01"), True)
            risk = stop - close
            target = rounded(close - 2 * risk, False)
        else:
            continue
        if not Decimal("0.01") <= risk / close <= Decimal("0.10") or target < 50:
            continue
        reward = abs(target - close)
        candidates.append(
            {
                "symbol": row["symbol"],
                "date": row["date"],
                "direction": direction,
                "reference": str(close),
                "take_profit": str(target),
                "stop_loss": str(stop),
                "potential_pct": str((target / close - 1) * 100),
                "risk_pct": str(risk / close * 100),
                "reward_risk": str(reward / risk),
                "rsi_14": str(rsi),
                "momentum_20d_pct": str(momentum * 100),
            }
        )
    # Alphabetical display, without an unvalidated probability/score.
    candidates.sort(key=lambda row: row["symbol"])
    return {
        "method": METHOD,
        "latest_date": snapshot["latest_date"],
        "available_at": snapshot["available_at"],
        "stale": snapshot["stale"],
        "source": snapshot["source"],
        "license_url": snapshot["license_url"],
        "attribution": snapshot["attribution"],
        "rows": candidates,
        "universe_count": len(snapshot["rows"]),
        "needs_reimport": any(not row.get("technical") for row in snapshot["rows"]),
    }


def read_screener(path: Path, at: datetime) -> dict[str, Any]:
    return screen(read_snapshot(path, at))
