"""Synthetic evidence only; tests never supply prospective G2 credit."""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest

from saham_signal.application.observation import Campaign, Entry, Session, append, report

D = Decimal
START = datetime(2026, 11, 16, 2, tzinfo=UTC)


def campaign(**changes: Any) -> Campaign:
    return Campaign.model_validate(
        {
            "campaign_id": "test-only-27",
            "origin": "simulation",
            "frozen_at": START - timedelta(days=1),
            "starts_at": START,
            "ends_at": START + timedelta(days=120),
            "model_version": "model-test",
            "fee_version": "fees-test",
            "assumptions_ref": "synthetic-assumptions",
            "holdout_sha256": "a" * 64,
            "calendar_ref": "synthetic-weekdays",
            "validation_ref": "synthetic-validation",
            "maximum_brier": "0.1",
            "maximum_fill_rate_error": "0.3",
            "maximum_drawdown_idr": "100",
            "bootstrap_samples": 100,
            **changes,
        }
    )


def session(index: int, **changes: Any) -> Session:
    day = START + timedelta(days=index)
    return Session.model_validate(
        {
            "session": day.date(),
            "completed_at": day + timedelta(hours=9),
            "source_receipt": f"session-{index}",
            "model_version": "model-test",
            "fee_version": "fees-test",
            "closing_equity_idr": str(index),
            "trials": [
                {
                    "trial_id": f"{index}-{j}",
                    "signal_cluster": f"cluster-{index}",
                    "decision_at": day,
                    "resolved_at": day + timedelta(minutes=30),
                    "evidence_ref": f"paper-receipt-{index}-{j}",
                    "eligible": True,
                    "filled": True,
                    "target_hit": True,
                    "probability": "0.8",
                    "predicted_fill": "0.8",
                    "net_equity_idr": "1",
                    "symbol": "TEST",
                    "regime": "synthetic-trend",
                    "liquidity": "synthetic-liquid",
                    "nominal_idr": "1000000",
                }
                for j in range(5)
            ],
            **changes,
        }
    )


def journal(c: Campaign, count: int) -> tuple[Entry, ...]:
    entries: tuple[Entry, ...] = ()
    i = 0
    while len(entries) < count:
        if (START + timedelta(days=i)).weekday() < 5:
            entries = append(c, entries, session(i))
        i += 1
    return entries


def test_empty_report_has_zero_credit_and_no_promotion() -> None:
    c = campaign(validation_ref=None, maximum_brier=None)
    r = report(c, (), START)
    assert r["g2"] == "pending"
    assert r["observed_sessions"] == r["eligible_paper_trades"] == 0
    assert r["metrics"]["brier"] is None
    assert "VALIDATION_TOLERANCES_MISSING" in r["reasons"]
    assert not r["model_promoted"] and not r["paper_live_enabled"]


def test_minimums_uncertainty_and_determinism_never_auto_pass() -> None:
    c = campaign()
    entries = journal(c, 60)
    r = report(c, entries, c.ends_at)
    assert r == report(c, entries, c.ends_at)
    assert r["observed_sessions"] == 60 and r["eligible_paper_trades"] == 300
    assert r["signal_clusters"] == 60 and D(r["cluster_effective_sample"]) == 60
    assert D(r["metrics"]["brier"]) == D("0.04")
    assert D(r["metrics"]["fill_rate_error"]) == D("0.2")
    assert all(v == "within_tolerance" for v in r["checks"].values())
    assert r["g2"] == "pending" and r["g2_credited_trades"] == 0
    assert r["breakdown"]["symbol"] == {"TEST": 300}
    assert r["elapsed_calendar_days"] > 60


def test_both_minimums_are_required_and_unfilled_attempts_do_not_count() -> None:
    c = campaign()
    s = session(0)
    trials = tuple(t.model_copy(update={"filled": False, "target_hit": None}) for t in s.trials)
    entries = append(c, (), s.model_copy(update={"trials": trials}))
    r = report(c, entries, c.ends_at)
    assert r["eligible_attempts"] == 5 and r["eligible_paper_trades"] == 0
    assert "MINIMUM_OBSERVATION_INCOMPLETE" in r["reasons"]
    assert r["checks"]["brier"] == "pending"
    # Plenty of fills on one session still cannot satisfy the duration.
    lots = tuple(
        s.trials[0].model_copy(update={"trial_id": str(i), "evidence_ref": f"receipt-{i}"})
        for i in range(300)
    )
    r = report(c, append(c, (), s.model_copy(update={"trials": lots})), c.ends_at)
    assert r["eligible_paper_trades"] == 300
    assert "MINIMUM_OBSERVATION_INCOMPLETE" in r["reasons"]
    assert "DEPENDENT_SAMPLE_INSUFFICIENT" in r["reasons"]


def test_cross_session_cluster_dependence_is_not_iid() -> None:
    c = campaign()
    entries: tuple[Entry, ...] = ()
    for i in range(3):
        s = session(i)
        s = s.model_copy(
            update={
                "trials": tuple(
                    t.model_copy(update={"signal_cluster": "one-shared-driver"}) for t in s.trials
                )
            }
        )
        entries = append(c, entries, s)
    r = report(c, entries, c.ends_at)
    assert r["cluster_effective_sample"] == "1"
    assert r["largest_cluster"] == 15


def test_missing_probabilities_and_short_history_remain_uncertain() -> None:
    c = campaign()
    s = session(0)
    r = report(c, append(c, (), s), c.ends_at)
    assert r["checks"]["brier"] == "uncertain"
    assert r["intervals_95"]["brier"] is None
    missing = s.model_copy(
        update={"trials": tuple(t.model_copy(update={"probability": None}) for t in s.trials)}
    )
    r = report(c, append(c, (), missing), c.ends_at)
    assert r["metrics"]["brier"] is None
    assert "CALIBRATION_OR_OUTCOMES_INCOMPLETE" in r["reasons"]


def test_report_is_independent_of_callers_decimal_precision() -> None:
    c = campaign()
    entries = append(c, (), session(0))
    expected = report(c, entries, c.ends_at)
    with localcontext() as context:
        context.prec = 3
        assert report(c, entries, c.ends_at) == expected


def test_breach_is_no_go_and_open_equity_is_included() -> None:
    c = campaign()
    entries = append(c, (), session(0, closing_equity_idr="-101"))
    r = report(c, entries, c.ends_at)
    assert r["g2"] == "no-go"
    assert r["checks"]["session_close_drawdown_idr"] == "breach"
    assert "TOLERANCE_BREACH_STOP_AND_REVIEW" in r["reasons"]


@pytest.mark.parametrize(
    "change",
    [
        {"model_version": "changed"},
        {"fee_version": "changed"},
        {"minimum_sessions": 59},
        {"minimum_trades": 299},
        {"maximum_brier": "NaN"},
        {"maximum_fill_rate_error": "1.01"},
        {"frozen_at": START},
        {"starts_at": START.replace(tzinfo=None)},
        {"ends_at": START},
        {"holdout_sha256": "changed"},
    ],
)
def test_protocol_changes_or_invalid_values_cannot_reuse_history(change: dict[str, Any]) -> None:
    c = campaign()
    entries = append(c, (), session(0))
    with pytest.raises(ValueError):
        report(campaign(**change), entries, c.ends_at)


def test_tampered_journal_duplicate_receipts_and_future_evidence_rejected() -> None:
    c = campaign()
    entries = append(c, (), session(0))
    with pytest.raises(ValueError, match="chain"):
        report(c, (entries[0].model_copy(update={"sha256": "tampered"}),), c.ends_at)
    with pytest.raises(ValueError, match="Duplicate"):
        append(c, entries, session(0))
    with pytest.raises(ValueError, match="Duplicate trial"):
        s = session(1)
        append(c, entries, s.model_copy(update={"trials": session(0).trials}))
    with pytest.raises(ValueError, match="outside observation"):
        report(c, entries, START)
    with pytest.raises(ValueError, match="Weekend"):
        append(c, entries, session(5))


def test_prospective_label_alone_does_not_open_gate() -> None:
    c = campaign(origin="prospective")
    r = report(c, (), c.ends_at)
    assert r["g2"] == "pending" and r["g2_credited_sessions"] == 0
    assert "G0_G1_AND_SS026_PROSPECTIVE_EVIDENCE_UNAVAILABLE" in r["reasons"]


def test_cli_sealed_input_and_invalid_seal(tmp_path: Path) -> None:
    c = campaign()
    data = {"campaign": c.model_dump(mode="json"), "campaign_sha256": c.seal(), "entries": []}
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    args = [
        sys.executable,
        "-m",
        "saham_signal.observation",
        str(path),
        "--as-of",
        c.ends_at.isoformat(),
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and json.loads(result.stdout)["g2"] == "pending"
    data["campaign_sha256"] = "tampered"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0 and "verify sealed inputs" in result.stderr
