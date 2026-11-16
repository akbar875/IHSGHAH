"""Offline daily research; adjusted fractional exposures are never Fill records."""

import csv
import hashlib
import json
import random
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from saham_signal.application.eod import import_csv, number

Row = dict[str, Any]
Panel = dict[date, dict[str, Row]]


def fingerprint(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path: Path) -> tuple[Panel, dict[str, int]]:
    audited = import_csv(path, datetime.now(UTC))
    if audited.quality["rejected_rows"]:
        raise ValueError("Study requires a fully valid source, not silently filtered history")
    panel: Panel = defaultdict(dict)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            panel[date.fromisoformat(row["date"])][row["ticker"]] = {
                k: (float(number(v)) if v else None)
                for k, v in row.items()
                if k not in {"date", "ticker"}
            }
    return dict(panel), audited.quality


def select(rows: dict[str, Row], rule: str, p: Row, equity: float) -> list[str]:
    if rule == "cash":
        return []
    if rule not in {"liquid_equal_weight", "momentum20", "low_vol_positive"}:
        raise ValueError("Unknown baseline")
    eligible = {
        symbol: r
        for symbol, r in rows.items()
        if all(
            r.get(k) is not None
            for k in ("close", "volume", "avg_value_20d_idr", "sma_200", "ret_20d", "vol_20d")
        )
        and r["close"] >= p["minimum_close_idr"]
        and r["volume"] > 0
        and r["avg_value_20d_idr"] >= p["minimum_avg_value_20d_idr"]
        and equity / p["slots"] <= p["maximum_participation"] * r["avg_value_20d_idr"]
        and (rule == "liquid_equal_weight" or r["ret_20d"] > 0)
    }
    field = {
        "liquid_equal_weight": "avg_value_20d_idr",
        "momentum20": "ret_20d",
        "low_vol_positive": "vol_20d",
    }[rule]
    direction = 1 if rule == "low_vol_positive" else -1
    return sorted(eligible, key=lambda s: (direction * eligible[s][field], s))[: p["slots"]]


def evaluate(panel: Panel, bounds: list[str], rule: str, p: Row, cost_scale: int = 1) -> Row:
    start, end = map(date.fromisoformat, bounds)
    days = sorted(d for d in panel if start <= d < end)
    equity = float(p["initial_capital_idr"])
    peak = equity
    drawdown = 0.0
    cycles: list[Row] = []
    contributions: dict[str, float] = defaultdict(float)
    buy = cost_scale * (p["buy_fee"] + p["slippage_each_side"])
    sell = cost_scale * (p["sell_fee"] + p["slippage_each_side"])
    if p["signal_to_entry_sessions"] != 1 or p["holding_sessions"] != 5:
        raise ValueError("This study implements only the frozen one/five session timing")
    for i in range(p["purge_sessions"], len(days) - 6, 5):
        chosen = select(panel[days[i]], rule, p, equity)
        before = equity
        allocation = equity / p["slots"]
        positions = dict.fromkeys(chosen, allocation / (1 + buy))
        cash = equity - allocation * len(chosen)
        entry = positions.copy()
        equity = cash + sum(positions.values())
        peak = max(peak, equity)
        drawdown = max(drawdown, 1 - equity / peak)
        # Entry at i+1 close: its return is unavailable to this position.
        for day in days[i + 2 : i + 7]:
            for symbol in positions:
                r = panel[day].get(symbol)
                if r is None or r.get("ret_1d") is None:
                    raise ValueError("Missing held return; study aborted, never drop the position")
                positions[symbol] *= 1 + r["ret_1d"]
            equity = cash + sum(positions.values())
            peak = max(peak, equity)
            drawdown = max(drawdown, 1 - equity / peak)
        equity = cash + sum(v * (1 - sell) for v in positions.values())
        drawdown = max(drawdown, 1 - equity / peak)
        if equity <= 0:
            raise ValueError("Portfolio exhausted")
        for symbol, value in positions.items():
            contributions[symbol] += value * (1 - sell) - entry[symbol] * (1 + buy)
        available = [r["ret_20d"] for r in panel[days[i]].values() if r["ret_20d"] is not None]
        cycles.append(
            {
                "decision": days[i].isoformat(),
                "entry": days[i + 1].isoformat(),
                "exit": days[i + 6].isoformat(),
                "net_return": equity / before - 1,
                "regime": "positive" if available and mean(available) > 0 else "nonpositive",
                "symbols": chosen,
            }
        )
    returns = [c["net_return"] for c in cycles]
    by_year: dict[str, list[float]] = defaultdict(list)
    by_regime: dict[str, list[float]] = defaultdict(list)
    for c in cycles:
        by_year[c["entry"][:4]].append(c["net_return"])
        by_regime[c["regime"]].append(c["net_return"])
    total_abs = sum(abs(v) for v in contributions.values())
    return {
        "cycles": cycles,
        "count": len(cycles),
        "invested_cycles": sum(bool(c["symbols"]) for c in cycles),
        "initial_capital_idr": p["initial_capital_idr"],
        "ending_capital_idr": equity,
        "total_net_return": equity / p["initial_capital_idr"] - 1,
        "mean_cycle_net_return": mean(returns) if returns else None,
        "mean_cycle_95_block_ci": block_ci(returns, p),
        "maximum_daily_mtm_drawdown": drawdown,
        "win_frequency": mean(v > 0 for v in returns) if returns else None,
        "years": {
            k: {"count": len(v), "mean_cycle_net_return": mean(v)} for k, v in by_year.items()
        },
        "regimes": {
            k: {"count": len(v), "mean_cycle_net_return": mean(v)} for k, v in by_regime.items()
        },
        "symbols": len(contributions),
        "largest_absolute_symbol_pnl_share": max(
            (abs(v) / total_abs for v in contributions.values()), default=0
        ),
        "cost_scale": cost_scale,
    }


def block_ci(returns: list[float], p: Row) -> list[float] | None:
    block = p["bootstrap_block_cycles"]
    if len(returns) < max(p["minimum_holdout_cycles"], 2 * block):
        return None
    rng = random.Random(p["seed"])
    draws = []
    for _ in range(p["bootstrap_draws"]):
        sample: list[float] = []
        while len(sample) < len(returns):
            index = rng.randrange(len(returns) - block + 1)
            sample.extend(returns[index : index + block])
        draws.append(mean(sample[: len(returns)]))
    draws.sort()
    return [draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws))]]


def run(panel: Panel, p: Row) -> Row:
    reports = {}
    for rule in p["baselines"]:
        folds = {
            fold: evaluate(panel, p[fold], rule, p) for fold in ("validation", "test", "holdout")
        }
        probability = folds["validation"]["win_frequency"]
        for fold in ("test", "holdout"):
            cycles = folds[fold]["cycles"]
            folds[fold]["brier"] = (
                mean((probability - (c["net_return"] > 0)) ** 2 for c in cycles)
                if cycles and probability is not None
                else None
            )
            folds[fold]["research_probability"] = probability
        stress = evaluate(panel, p["holdout"], rule, p, cost_scale=2)
        h = folds["holdout"]
        ci = h["mean_cycle_95_block_ci"]
        checks = {
            "positive_expectancy_lower_ci": ci is not None and ci[0] > 0,
            "risk_budget": h["maximum_daily_mtm_drawdown"] <= p["maximum_drawdown"],
            "sample_size": h["invested_cycles"] >= p["minimum_holdout_cycles"],
            "calibration": h["brier"] is not None and h["brier"] <= p["maximum_brier"],
            "multiple_years_positive": len(h["years"]) >= 2
            and all(y["mean_cycle_net_return"] > 0 for y in h["years"].values()),
            "multiple_regimes_positive": len(h["regimes"]) >= 2
            and all(
                r["count"] >= 10 and r["mean_cycle_net_return"] > 0 for r in h["regimes"].values()
            ),
            "diversified": h["symbols"] >= 10 and h["largest_absolute_symbol_pnl_share"] <= 0.5,
            "double_cost_positive": stress["mean_cycle_net_return"] is not None
            and stress["mean_cycle_net_return"] > 0,
        }
        # Aggregate publication only; the consumed local report retains decision rows.
        reports[rule] = {
            "folds": folds,
            "double_cost_holdout": stress,
            "statistical_checks": checks,
        }
    return {
        "experiments": reports,
        "champion": p["champion"],
        "g1": {
            "scope": "daily-research",
            "decision": "NO-GO",
            "auto_promotion": False,
            "statistical_checks": reports[p["champion"]]["statistical_checks"],
            "evidence_checks": {
                "historical_point_in_time": False,
                "historical_universe": False,
                "verified_execution_and_costs": False,
                "independent_release_review": False,
            },
            "paper_live_enabled": False,
            "product_probability": None,
        },
    }


def consume(receipt: Path, identity: Row) -> None:
    receipt.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation happens BEFORE parsing/using returns. Failure also consumes this run.
    with receipt.open("x", encoding="utf-8") as target:
        json.dump(identity, target, indent=2)
        target.write("\n")
