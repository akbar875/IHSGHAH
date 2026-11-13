"""SS-016 regression evidence; all data is invented, never a profitability claim."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest

from saham_signal.adapters.evaluation_simulation import at, fixture
from saham_signal.application.evaluation import (
    Study,
    calibrate,
    context_hash,
    dataset_hash,
    execute,
    metrics,
    rank,
)

D = Decimal


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    p, cases, refs, fees = fixture()
    return Study(p).run(cases, refs, fees, evaluated_at=at(31))


def test_oos_report_and_gate_are_explicit(report: dict[str, Any]) -> None:
    assert report["status"] == "experiment"
    assert report["g1"]["decision"] == "no-go"
    assert not report["auto_promotion"] and not report["live_alerts_enabled"]
    assert len(report["experiments"]) == 10
    for experiment in report["experiments"]:
        h = experiment["metrics"]["holdout"]
        assert h["observations"] > 0
        assert h["expectancy_net_idr"] is not None
        assert h["expectancy_95_block_ci_idr"] is not None
        assert h["realized_plan_drawdown_idr"] is not None
        assert 0 < D(h["fill_share_rate"]) <= 1
        assert h["calibration"]["brier"] is not None
        assert h["calibration"]["reliability"]
        assert h["projection_interval_coverage"] is None
        assert set(experiment["holdout_breakdown"]) == {
            "regime",
            "liquidity",
            "symbol",
            "session",
            "horizon_seconds",
        }
        assert all(not fold["refit"] for fold in experiment["walk_forward"])
        for fold in experiment["rows"].values():
            assert all(
                row["probability"] is None and row["fill_probability"] is None for row in fold
            )


def test_protocol_is_sealed_and_holdout_consumed_once() -> None:
    p, cases, refs, fees = fixture()
    study = Study(p)
    with pytest.raises(ValueError, match="incomplete"):
        study.run(cases, refs, fees, evaluated_at=at(30))
    with pytest.raises(ValueError, match="manifest"):
        study.run(cases[:-1], refs, fees, evaluated_at=at(31))
    changed = (replace(fees[0], buy_broker=D("0.002")),)
    with pytest.raises(ValueError, match="Reference/fee"):
        study.run(cases, refs, changed, evaluated_at=at(31))
    result = study.run(cases, refs, fees, evaluated_at=at(31))
    assert result["protocol_hash"] == p.hash
    with pytest.raises(ValueError, match="already consumed"):
        study.run(cases, refs, fees, evaluated_at=at(31))
    assert replace(p, risk=replace(p.risk, risk_fraction=D("0.004"))).hash != p.hash
    assert replace(p, execution=replace(p.execution, latency_ms=500)).hash != p.hash


def test_purge_embargo_and_label_window_boundaries() -> None:
    p, cases, _, _ = fixture()
    assert {p.split(c) for c in cases} >= {"train", "validation", "test", "holdout", None}
    case = next(c for c in cases if p.split(c) == "validation")
    assert replace(p, embargo=timedelta(days=20)).split(case) is None
    assert replace(p, purge=timedelta(days=20)).split(case) is None
    assert p.split(replace(case, label_end=p.validation_end)) is None
    with pytest.raises(ValueError, match="Purge"):
        replace(p, purge=timedelta(seconds=1))
    with pytest.raises(ValueError, match="Freeze"):
        replace(p, frozen_at=p.holdout_start)
    with pytest.raises(ValueError, match="Chronological"):
        replace(p, train_end=p.validation_end)


def test_no_future_feature_or_live_mode() -> None:
    _, cases, _, _ = fixture()
    c = cases[0]
    with pytest.raises(ValueError, match="cutoff"):
        replace(c, features=replace(c.features, as_of=c.features.as_of + timedelta(seconds=1)))
    with pytest.raises(ValueError, match="research"):
        replace(c, spec=replace(c.spec, mode="live"))
    with pytest.raises(ValueError, match="Frame outside"):
        replace(c, frames=(replace(c.frames[0], symbol="OTHER"),))


def test_calibration_uses_validation_only_and_insufficient_is_null(report: dict[str, Any]) -> None:
    e = report["experiments"][0]
    p, _, _, _ = fixture()
    expected = calibrate(e["rows"]["validation"], p.minimum_calibration)
    assert e["calibration_bins"] == {key: str(value) for key, value in expected.items()}
    assert calibrate(e["rows"]["validation"], 10000) == {}
    changed = deepcopy(e["rows"]["holdout"])
    for row in changed:
        if row["target"] is not None:
            row["target"] = 1 - row["target"]
    assert calibrate(e["rows"]["validation"], p.minimum_calibration) == expected
    assert e["metrics"]["validation"]["calibration"]["brier"] is None


def test_nominal_recomputed_and_ranking_account_isolated(report: dict[str, Any]) -> None:
    small = report["experiments"][0]["rows"]["holdout"]
    large = report["experiments"][1]["rows"]["holdout"]
    assert small[0]["requested"] < large[0]["requested"]
    assert small[0]["risk"]["reward_idr"] != large[0]["risk"]["reward_idr"]
    assert rank(small, account="simulation-account", nominal=D(200000))
    for rows, account, nominal in (
        (small + large, "simulation-account", D(200000)),
        (small, "other-account", D(200000)),
    ):
        with pytest.raises(ValueError, match="scope"):
            rank(rows, account=account, nominal=nominal)


def test_partial_fill_failed_exit_and_loss_not_dropped(report: dict[str, Any]) -> None:
    rows = [row for fold in report["experiments"][1]["rows"].values() for row in fold]
    assert any(0 < row["filled"] < row["requested"] for row in rows)
    assert any(row["open"] > 0 and row["net_idr"] is None and row["target"] is None for row in rows)
    assert any(row["net_idr"] is not None and D(row["net_idr"]) < 0 for row in rows)
    assert any(row["filled"] == 0 for row in rows)
    h = report["experiments"][1]["metrics"]["holdout"]
    assert h["open_shares"] > 0
    assert not report["g1"]["checks"][1]["no_failed_exits"]


def test_ablations_abstain_on_missing_feature() -> None:
    p, cases, refs, fees = fixture()
    c = cases[0]
    missing = replace(c, features=replace(c.features, buy_pressure=None))
    normal = execute(missing, p.baselines[0], D(1000000), p, refs, fees)
    ablation = execute(missing, p.baselines[3], D(1000000), p, refs, fees)
    assert not normal["eligible"] and ablation["eligible"]
    assert not p.baselines[0].score(replace(c.features, return_fraction=None))


def test_reference_hash_and_dataset_order_are_reproducible() -> None:
    p, cases, refs, fees = fixture()
    assert dataset_hash(tuple(reversed(cases))) == p.dataset_hash
    assert context_hash(tuple(reversed(cases)), refs, fees) == p.context_hash
    with pytest.raises(ValueError, match="Duplicate"):
        dataset_hash(cases + cases[:1])
    changed = replace(refs, daily_limits=())
    assert context_hash(cases, changed, fees) != p.context_hash


def test_reproducible_report_independent_of_decimal_context(report: dict[str, Any]) -> None:
    p, cases, refs, fees = fixture()
    with localcontext() as context:
        context.prec = 6
        again = Study(p).run(tuple(reversed(cases)), refs, fees, evaluated_at=at(31))
    assert again == report


def test_insufficient_sessions_get_no_bootstrap_claim(report: dict[str, Any]) -> None:
    p, _, _, _ = fixture()
    rows = report["experiments"][0]["rows"]["holdout"][:1]
    assert metrics(rows, p)["expectancy_95_block_ci_idr"] is None
    assert metrics([], p)["expectancy_net_idr"] is None
    assert metrics([], p)["coverage"] is None


def test_committed_evidence_matches_replay(report: dict[str, Any]) -> None:
    path = Path(__file__).resolve().parents[3] / "research/reports/SS-016-simulation.json"
    evidence = json.loads(path.read_text())
    assert evidence["full_report_hash"] == report["report_hash"]
    assert evidence["protocol_hash"] == report["protocol_hash"]
    assert evidence["g1"] == report["g1"]
    assert [e["metrics"] for e in evidence["experiments"]] == [
        e["metrics"] for e in report["experiments"]
    ]
