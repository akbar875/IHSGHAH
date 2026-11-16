"""Chronological, non-overlapping long-only EOD replay; never live Fill records."""

from datetime import date
from typing import Any

from saham_signal.application.screener import screen

TARGET = 1000
BUY_FEE = 0.0015
SELL_FEE = 0.0025
SLIPPAGE = 0.001


class DailyReplay:
    def __init__(self) -> None:
        self.trades: list[dict[str, Any]] = []
        self.pending: dict[str, Any] | None = None
        self.position: dict[str, Any] | None = None
        self.previous: date | None = None
        self.first: str | None = None
        self.last: str | None = None
        self.invalid = False
        self.equity = 1.0
        self.peak = 1.0
        self.drawdown = 0.0

    def observe(self, row: dict[str, Any]) -> None:
        day = date.fromisoformat(row["date"])
        self.first = self.first or row["date"]
        self.last = row["date"]
        gap = self.previous is not None and (day - self.previous).days > 7
        self.previous = day
        if self.invalid or len(self.trades) >= TARGET:
            return
        if self.position is not None:
            change = row["return_1d"]
            if (
                gap
                or float(row["volume"]) <= 0
                or change is None
                or not -0.5 <= float(change) <= 0.5
            ):
                self.invalid = True
                return
            p = self.position
            p["gross"] *= 1 + float(change)
            p["sessions"] += 1
            net = p["gross"] * (1 - SELL_FEE - SLIPPAGE) / (1 + BUY_FEE + SLIPPAGE)
            mark = self.equity * net
            self.peak = max(self.peak, mark)
            self.drawdown = max(self.drawdown, 1 - mark / self.peak)
            reason = (
                "stop_close"
                if p["gross"] <= p["stop_ratio"]
                else "target_close"
                if p["gross"] >= p["target_ratio"]
                else "time_exit"
                if p["sessions"] >= 15
                else None
            )
            if reason is None:
                return
            self.equity *= net
            self.trades.append(
                {
                    "signal_date": p["signal_date"],
                    "entry_date": p["entry_date"],
                    "exit_date": row["date"],
                    "entry_close": p["entry_close"],
                    "exit_close": row["close_idr"],
                    "net_return_pct": (net - 1) * 100,
                    "equity": self.equity,
                    "exit_reason": reason,
                }
            )
            self.position = None
        elif self.pending is not None:
            plan, self.pending = self.pending, None
            entry = float(row["close_idr"])
            stop, target = float(plan["stop_loss"]), float(plan["take_profit"])
            if not gap and float(row["volume"]) > 0 and stop < entry < target:
                self.position = {
                    "signal_date": plan["date"],
                    "entry_date": row["date"],
                    "entry_close": row["close_idr"],
                    "gross": 1.0,
                    "sessions": 0,
                    "stop_ratio": stop / entry,
                    "target_ratio": target / entry,
                }
                mark = self.equity * (1 - SELL_FEE - SLIPPAGE) / (1 + BUY_FEE + SLIPPAGE)
                self.drawdown = max(self.drawdown, 1 - mark / self.peak)
                return
        if len(self.trades) < TARGET:
            result = screen(
                {
                    "rows": [{**row, "stale": False}],
                    "stale": False,
                    "latest_date": row["date"],
                    "available_at": "",
                    "source": "",
                    "license_url": "",
                    "attribution": "",
                }
            )
            new_plan = next(iter(result["rows"]), None)
            if new_plan and new_plan["direction"] == "bullish":
                self.pending = new_plan

    def report(self) -> dict[str, Any]:
        count = len(self.trades)
        return {
            "origin": "simulation",
            "method": "ma-rsi-close-replay-v1",
            "direction": "long_only",
            "sample": "exploratory_in_sample",
            "target_trades": TARGET,
            "completed_trades": count,
            "target_reached": count >= TARGET,
            "status": "data_gap"
            if self.invalid
            else "complete"
            if count >= TARGET
            else "insufficient_trades",
            "start_date": self.first,
            "end_date": self.last,
            "unclosed_position": self.position is not None,
            "win_count": sum(t["net_return_pct"] > 0 for t in self.trades),
            "loss_count": sum(t["net_return_pct"] < 0 for t in self.trades),
            "flat_count": sum(t["net_return_pct"] == 0 for t in self.trades),
            "total_return_pct": (self.equity - 1) * 100 if count and not self.invalid else None,
            "max_drawdown_pct": self.drawdown * 100 if count and not self.invalid else None,
            "buy_fee": BUY_FEE,
            "sell_fee": SELL_FEE,
            "slippage_each_side": SLIPPAGE,
            "holding_sessions": 15,
            "trades": self.trades,
        }
