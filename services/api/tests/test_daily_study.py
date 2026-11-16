"""Timing, missing exposure and consumed-holdout safeguards with synthetic data."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from saham_signal.application.daily_study import block_ci, consume, evaluate, select


def protocol() -> dict[str, Any]:
    return {
        "slots": 1,
        "holding_sessions": 5,
        "signal_to_entry_sessions": 1,
        "purge_sessions": 0,
        "minimum_close_idr": 200,
        "minimum_avg_value_20d_idr": 1e9,
        "maximum_participation": 0.01,
        "initial_capital_idr": 1e6,
        "buy_fee": 0.0015,
        "sell_fee": 0.0025,
        "slippage_each_side": 0.001,
        "bootstrap_block_cycles": 2,
        "minimum_holdout_cycles": 4,
        "bootstrap_draws": 100,
        "seed": 12,
    }


def panel() -> dict[date, dict[str, Any]]:
    return {
        date(2025, 1, 1) + timedelta(days=i): {
            "SIM": {
                "close": 1000,
                "volume": 1000,
                "avg_value_20d_idr": 1e10,
                "sma_200": 900,
                "ret_20d": 0.1,
                "vol_20d": 0.2,
                "ret_1d": 0.01,
            }
        }
        for i in range(7)
    }


def test_entry_lag_excludes_entry_return_and_five_daily_returns_compound() -> None:
    data = panel()
    data[date(2025, 1, 2)]["SIM"]["ret_1d"] = 9
    p = protocol()
    result = evaluate(data, ["2025-01-01", "2025-02-01"], "momentum20", p)
    expected = (1.01**5) / 1.0025 * 0.9965 - 1
    assert result["count"] == 1
    assert result["cycles"][0]["net_return"] == pytest.approx(expected)
    assert result["cycles"][0]["entry"] == "2025-01-02"
    assert result["cycles"][0]["exit"] == "2025-01-07"


def test_missing_held_row_aborts_instead_of_removing_loss() -> None:
    data = panel()
    del data[date(2025, 1, 4)]["SIM"]
    with pytest.raises(ValueError, match="Missing held return"):
        evaluate(data, ["2025-01-01", "2025-02-01"], "momentum20", protocol())


def test_cash_stays_cash_and_cost_stress_reduces_returns() -> None:
    p = protocol()
    cash = evaluate(panel(), ["2025-01-01", "2025-02-01"], "cash", p)
    assert cash["total_net_return"] == 0 and cash["invested_cycles"] == 0
    regular = evaluate(panel(), ["2025-01-01", "2025-02-01"], "momentum20", p)
    stressed = evaluate(panel(), ["2025-01-01", "2025-02-01"], "momentum20", p, 2)
    assert stressed["total_net_return"] < regular["total_net_return"]


def test_selection_uses_only_decision_rows_and_capacity() -> None:
    rows = panel()[date(2025, 1, 1)]
    assert select(rows, "momentum20", protocol(), 1e6) == ["SIM"]
    assert select(rows, "momentum20", protocol(), 1e12) == []
    rows["SIM"]["ret_20d"] = -0.1
    assert select(rows, "momentum20", protocol(), 1e6) == []


def test_block_bootstrap_is_deterministic_and_insufficient_sample_is_null() -> None:
    p = protocol()
    assert block_ci([0.1], p) is None
    returns = [-0.01, 0.01, 0.02, 0.03] * 4
    assert block_ci(returns, p) == block_ci(returns, p)
    assert block_ci(returns, p) != block_ci([0.1] * 16, p)


def test_consumed_receipt_is_exclusive_and_failure_does_not_release_it(tmp_path: Path) -> None:
    path = tmp_path / "consumed.json"
    consume(path, {"protocol": "fixed"})
    with pytest.raises(FileExistsError):
        consume(path, {"protocol": "changed"})
    assert json.loads(path.read_text()) == {"protocol": "fixed"}
