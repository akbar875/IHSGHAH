"""Reproducible SS-016 fixture. All sessions, prices and features are invented."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from saham_signal.adapters.instrument_references import MemoryReferences
from saham_signal.application.evaluation import (
    Baseline,
    Case,
    Protocol,
    Study,
    context_hash,
    dataset_hash,
)
from saham_signal.application.features import FeatureEngine, FeaturePolicy
from saham_signal.application.feed import FeedProfile
from saham_signal.application.feed_quality import FeedAssessment
from saham_signal.application.operations import Control
from saham_signal.application.replay import FeeSchedule, Frame, ReplayPolicy
from saham_signal.application.risk import PlanSpec, Portfolio, RiskInputs, RiskPolicy
from saham_signal.domain.instruments import (
    CalendarDay,
    DailyLimits,
    InstrumentRule,
    Session,
    TickBand,
    TradingState,
    Version,
)

D = Decimal


def at(day: int) -> datetime:
    return datetime(2026, 10, day, 2, 30, tzinfo=UTC)


def fixture() -> tuple[Protocol, tuple[Case, ...], MemoryReferences, tuple[FeeSchedule, ...]]:
    """Historical weekdays are fixture labels, not an exchange calendar assertion."""
    v = Version(
        "sim-reference-v1",
        at(1) - timedelta(days=1),
        at(31) + timedelta(days=1),
        at(1) - timedelta(days=2),
        "simulation:SS-016",
        "simulation",
    )
    symbols = ("SIMA", "SIMB")
    days = [date(2026, 10, day) for day in range(1, 31) if date(2026, 10, day).weekday() < 5]
    refs = MemoryReferences(
        tuple(
            InstrumentRule(
                v, s, "main", "regular", 100, (TickBand(1, None, 5),), "sim-limits", "SIM"
            )
            for s in symbols
        ),
        tuple(CalendarDay(v, "SIM", day, (Session("I", time(9), time(11, 30)),)) for day in days),
        tuple(TradingState(v, s, "regular", "active", (), True) for s in symbols),
        tuple(
            DailyLimits(v, s, "regular", day, "sim-limits", 1000, 850, 1250)
            for s in symbols
            for day in days
        ),
    )
    fees = (FeeSchedule(v, D("0.001"), D("0.001"), D("0.0001"), D("0.001")),)
    engine = FeatureEngine(
        FeedProfile("simulation:SS-016", "simulation-v1", "simulation", "live", "shares"),
        "research",
        FeaturePolicy(),
    )
    cases = []
    for day in days:
        for index, symbol in enumerate(symbols):
            stamp = at(day.day)
            identity = f"{symbol}-{day}"
            spec = PlanSpec(
                identity,
                "simulation-account",
                "research",
                symbol,
                1005,
                950,
                1150,
                stamp,
                stamp + timedelta(minutes=3),
                stamp + timedelta(minutes=5),
                stamp + timedelta(minutes=10),
                D(5),
                "synthetic-rule",
                "synthetic-invalidation",
            )
            feed = FeedAssessment(
                symbol,
                stamp,
                "live",
                ("SIMULATION",),
                stamp,
                stamp,
                timedelta(0),
                False,
                False,
                "synthetic",
                "research",
                "simulation",
            )
            inputs = RiskInputs(
                stamp,
                Portfolio("simulation-account", "research", stamp, D(10000000), D(1000000)),
                feed,
                stamp,
                995,
                1000,
                10000,
                True,
                operations=Control(1, False, "resume", "SS-016-simulation-only"),
            )
            features = replace(
                engine.snapshot(symbol, stamp),
                return_fraction=D("0.01"),
                volatility_fraction=D("0.002"),
                relative_volume=D("1.5"),
                buy_pressure=D("0.6"),
                pressure_hidden_reason=None,
            )
            buy_at = stamp + timedelta(seconds=1)
            sell_at = stamp + timedelta(seconds=3)
            # Mix closed target/stop, unfilled, partial, and failed-exit cases.
            scenario = (day.day + index) % 8
            depth = 200 if scenario == 3 else 10000
            frames = [
                Frame(
                    identity + "-entry",
                    symbol,
                    buy_at,
                    buy_at,
                    ((995, 10000),),
                    ((1000, depth),) if scenario != 2 else (),
                )
            ]
            bid = 940 if scenario in (0, 1, 4) else 1160
            frames.append(
                Frame(
                    identity + "-exit",
                    symbol,
                    sell_at,
                    sell_at,
                    ((bid, 10000),) if scenario != 5 else (),
                    ((bid + 5, 10000),),
                    low_idr=bid,
                    high_idr=bid,
                )
            )
            frames.append(
                replace(
                    frames[-1],
                    id=identity + "-post-trigger",
                    event_time=sell_at + timedelta(seconds=1),
                    available_at=sell_at + timedelta(seconds=1),
                )
            )
            cases.append(
                Case(
                    identity,
                    features,
                    spec,
                    inputs,
                    tuple(frames),
                    stamp + timedelta(minutes=15),
                    "ranging" if index else "trending",
                    "shallow" if scenario == 3 else "deep",
                )
            )
    rows = tuple(cases)
    baselines = (
        Baseline("trend", "trend", D("0.001"), D("0.02")),
        Baseline("momentum", "momentum", D("0.001"), D("0.02")),
        Baseline("volatility", "volatility", D("0.001"), D("0.02")),
        Baseline("trend-no-pressure", "trend", D("0.001"), D("0.02"), use_pressure=False),
        Baseline("trend-no-volume", "trend", D("0.001"), D("0.02"), use_volume=False),
    )
    protocol = Protocol(
        id="SS-016-simulation-v1",
        dataset_version="invented-2026-10-v1",
        dataset_hash=dataset_hash(rows),
        context_hash=context_hash(rows, refs, fees),
        code_version="SS-016-v1",
        universe_evidence="invented SIMA/SIMB; no licensed universe",
        frozen_at=at(15),
        train_start=at(1) - timedelta(hours=1),
        train_end=at(8),
        validation_end=at(15),
        test_end=at(22),
        holdout_start=at(23),
        holdout_end=at(31),
        label_horizon=timedelta(minutes=15),
        purge=timedelta(minutes=15),
        embargo=timedelta(minutes=5),
        baselines=baselines,
        champion="trend",
        nominals_idr=(D(200000), D(1000000)),
        risk=RiskPolicy(),
        execution=ReplayPolicy(),
        max_drawdown_idr=D(50000),
        minimum_sessions=4,
        minimum_calibration=3,
        maximum_brier=D("0.25"),
        bootstrap_block_sessions=2,
    )
    return protocol, rows, refs, fees


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key != "experiments"} | {
        "experiments": [
            {
                key: value
                for key, value in experiment.items()
                if key not in ("rows", "ranking", "walk_forward")
            }
            for experiment in report["experiments"]
        ]
    }


def main() -> None:
    p, cases, refs, fees = fixture()
    report = Study(p).run(cases, refs, fees, evaluated_at=at(31))
    print(json.dumps(summary(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
