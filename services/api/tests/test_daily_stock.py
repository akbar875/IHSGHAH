"""Temporal replay, fees/gaps, counts and authenticated real-origin detail."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_screener import data

from saham_signal.application.daily_backtest import BUY_FEE, SELL_FEE, SLIPPAGE, DailyReplay
from saham_signal.application.daily_stock import stock_detail
from saham_signal.application.security import session_cookie
from saham_signal.config import Settings
from saham_signal.transport.http import create_app


def trading_days(count: int) -> list[date]:
    result: list[date] = []
    day = date(2000, 1, 3)
    while len(result) < count:
        if day.weekday() < 5:
            result.append(day)
        day += timedelta(days=1)
    return result


def observation(day: date, close: str = "1000", change: str | None = "0") -> dict[str, Any]:
    return {
        "symbol": "SIM",
        "date": day.isoformat(),
        "close_idr": close,
        "volume": "100000",
        "return_1d": change,
        "rsi_14": "60",
        "technical": {
            "sma_20": "980",
            "sma_50": "950",
            "sma_200": "900",
            "ret_20d": "0.05",
            "avg_value_20d_idr": "2000000000",
        },
    }


def test_signal_enters_next_session_then_target_after_fees() -> None:
    days = trading_days(3)
    replay = DailyReplay()
    replay.observe(observation(days[0]))
    assert replay.position is None and replay.pending is not None
    replay.observe(observation(days[1]))
    assert replay.position is not None and not replay.trades
    replay.observe(observation(days[2], "1100", "0.10"))
    report = replay.report()
    trade = report["trades"][0]
    assert trade["signal_date"] < trade["entry_date"] < trade["exit_date"]
    assert trade["exit_reason"] == "target_close"
    expected = (1.1 * (1 - SELL_FEE - SLIPPAGE) / (1 + BUY_FEE + SLIPPAGE) - 1) * 100
    assert abs(trade["net_return_pct"] - expected) < 1e-9
    assert report["completed_trades"] == 1 and not report["target_reached"]


def test_gap_through_stop_loses_actual_close_and_never_fill_at_stop() -> None:
    replay = DailyReplay()
    days = trading_days(3)
    for day, price, change in zip(days, ["1000", "1000", "800"], ["0", "0", "-0.2"], strict=True):
        replay.observe(observation(day, price, change))
    trade = replay.trades[0]
    assert trade["exit_close"] == "800" and trade["exit_reason"] == "stop_close"
    assert trade["net_return_pct"] < -20


def test_missing_held_return_does_not_drop_or_complete_position() -> None:
    replay = DailyReplay()
    days = trading_days(3)
    for day in days[:2]:
        replay.observe(observation(day))
    replay.observe(observation(days[2], change=None))
    report = replay.report()
    assert report["status"] == "data_gap" and report["unclosed_position"]
    assert report["completed_trades"] == 0 and report["total_return_pct"] is None


def test_thousand_trades_are_unique_non_overlapping_and_never_padded() -> None:
    replay = DailyReplay()
    for index, day in enumerate(trading_days(3010)):
        replay.observe(
            observation(day, "1100" if index % 3 == 2 else "1000", "0.1" if index % 3 == 2 else "0")
        )
    report = replay.report()
    assert report["completed_trades"] == 1000 and report["target_reached"]
    assert len({t["entry_date"] for t in report["trades"]}) == 1000
    assert all(
        a["exit_date"] < b["entry_date"]
        for a, b in zip(replay.trades, replay.trades[1:], strict=False)
    )


def test_daily_detail_has_real_history_no_depth_and_actual_count(tmp_path: Path) -> None:
    snapshot = data(tmp_path)
    detail = stock_detail(snapshot, "SIM")
    assert detail["origin"] == "market" and detail["feed"] == "daily"
    assert len(detail["history"]) == 1 and detail["backtest"]["completed_trades"] == 0
    assert detail["order_book"] is None and detail["individual_queue"] is None


def test_daily_stock_api_requires_auth_and_rejects_query_or_unknown_symbol(tmp_path: Path) -> None:
    data(tmp_path)
    config = Settings(
        session_secret=SecretStr("daily-stock-research-test-secret-12345678901234567890"),
        pilot_account_id="research-test",
        eod_snapshot_path=tmp_path / "snapshot.json",
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/api/research/stocks/SIM").status_code == 401
        client.cookies.set("saham_session", session_cookie(config))
        result = client.get("/api/research/stocks/SIM")
        assert result.status_code == 200 and result.json()["symbol"] == "SIM"
        assert result.headers["cache-control"] == "private, no-store"
        assert client.get("/api/research/stocks/MISSING").status_code == 404
        assert client.get("/api/research/stocks/SIM?path=private").status_code == 422
        assert client.get("/api/research/stocks/bad").status_code == 422
