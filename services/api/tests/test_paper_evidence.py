"""Test-only assertions exercise admission; none are vendor/model approval evidence."""

import hashlib
import json
import os
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from test_paper import config
from test_persistence import disposable_database
from test_positions import NOW as FILL_NOW
from test_positions import OPEN, command

from saham_signal.adapters.backup import backup, restore
from saham_signal.adapters.paper import PostgresPaper
from saham_signal.adapters.paper_evidence import PostgresPaperEvidence, fill_reports
from saham_signal.adapters.paper_simulation import SimulationControl, run
from saham_signal.adapters.positions import PostgresPositions
from saham_signal.application.acceptance import (
    REQUIREMENTS,
    GateDecision,
    assess,
    require_admission,
    validate_acceptance,
)
from saham_signal.application.market import MarketScope
from saham_signal.application.operations import Operations
from saham_signal.application.paper import ObservationProtocol
from saham_signal.application.security import session_cookie
from saham_signal.domain.persistence import digest
from saham_signal.transport.http import create_app

NOW = datetime(2026, 11, 15, 0, tzinfo=UTC)
RELEASE = "f" * 40


def seal(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt.pop("sha256", None)
    receipt["sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    return receipt


def acceptance() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    result = json.loads((root / "research/reports/SS-026-acceptance.json").read_text())
    return seal({**result, "revision": RELEASE, "revision_kind": "commit"})


def review(gate: str, decision: str = "passed") -> dict[str, Any]:
    # These invented market-origin claims are unit inputs, not production artifacts.
    return {
        "gate": gate,
        "decision": decision,
        "release": RELEASE,
        "reviewer": "test-reviewer",
        "reviewed_at": (NOW - timedelta(days=1)).isoformat(),
        "valid_until": (NOW + timedelta(days=2)).isoformat(),
        "reason": "synthetic unit-test assertion; never licensed or approved",
        "data_manifest_sha256": "1" * 64,
        "model_artifact_sha256": "2" * 64,
        "proofs": [
            {
                "check": name,
                "passed": True,
                "origin": "market",
                "reference": f"test-only:{name}",
                "sha256": "0" * 64,
            }
            for name in sorted(REQUIREMENTS[gate])
        ],
        "validation_ref": "test-only:validation",
        "maximum_brier": "0.2",
        "maximum_fill_rate_error": "0.1",
        "maximum_drawdown_idr": "1000",
    }


def evidence() -> dict[str, dict[str, Any]]:
    protocol = ObservationProtocol(
        NOW - timedelta(hours=1),
        NOW + timedelta(days=1),
        "test-only:validation",
        Decimal("0.2"),
        Decimal("0.1"),
        Decimal("1000"),
    )
    receipt = acceptance()
    return {
        "G0": review("G0"),
        "G1": review("G1"),
        "acceptance": receipt,
        "protocol": protocol.document(),
    }


def test_every_scenario_has_named_evidence_and_critical_failure_blocks_progression() -> None:
    values = evidence()
    report = assess(RELEASE, NOW, values, paused=False)
    assert len(report["scenarios"]) == 12
    assert all(s["status"] == "passed" and s["evidence"] for s in report["scenarios"])
    assert report["acceptance_passed"]
    assert not report["can_advance"]  # Component/browser evidence is not licensed E2E.
    values["acceptance"]["origin"] = "market"
    values["acceptance"]["scope"] = "licensed-feed-e2e"
    with pytest.raises(ValueError, match="relabelled"):
        validate_acceptance(seal(values["acceptance"]))
    values["acceptance"]["format"] = "SS-026-reviewed-e2e-v2"
    values["acceptance"]["reviewer"] = "test-reviewer"
    values["acceptance"]["reviewed_at"] = (NOW - timedelta(hours=2)).isoformat()
    values["acceptance"]["gate_review_sha256"] = {g: digest(values[g]) for g in REQUIREMENTS}
    values["acceptance"]["data_manifest_sha256"] = "1" * 64
    values["acceptance"]["model_artifact_sha256"] = "2" * 64
    seal(values["acceptance"])
    ready = assess(RELEASE, NOW, values, paused=False)
    require_admission(ready)
    for number in range(12):
        failed = deepcopy(values)
        failed["acceptance"]["scenarios"][number]["status"] = "blocked"
        failed["acceptance"]["scenarios"][number]["evidence"][0]["status"] = "blocked"
        failed["acceptance"]["acceptance_passed"] = False
        seal(failed["acceptance"])
        blocked = assess(RELEASE, NOW, failed, paused=False)
        assert not blocked["can_advance"]
        with pytest.raises(ValueError, match="blocked"):
            require_admission(blocked)


def test_g0_g1_reviews_expiry_release_tolerances_and_control_are_required() -> None:
    values = evidence()
    for gate in ("G0", "G1"):
        for field, value in (
            ("decision", "no-go"),
            ("release", "a" * 40),
            ("valid_until", NOW.isoformat()),
        ):
            changed = deepcopy(values)
            changed[gate][field] = value
            assert not assess(RELEASE, NOW, changed, paused=False)["can_advance"]
        forged = review(gate)
        forged["proofs"][0]["origin"] = "simulation"
        with pytest.raises(ValueError, match="market evidence"):
            GateDecision.model_validate(forged)
    missing = review("G1")
    missing["maximum_brier"] = None
    with pytest.raises(ValueError, match="tolerances"):
        GateDecision.model_validate(missing)
    assert "OPERATIONS_BLOCKED" in assess(RELEASE, NOW, values, paused=True)["reasons"]
    values["G1"]["maximum_brier"] = "0.1"
    assert "PROTOCOL_VALIDATION_MISMATCH" in assess(RELEASE, NOW, values, paused=False)["reasons"]
    receipt = acceptance()
    receipt["scenarios"].pop()
    with pytest.raises(ValueError):
        validate_acceptance(seal(receipt))


def test_actual_and_paper_fills_have_distinct_sources_and_no_combined_pnl() -> None:
    scope = MarketScope("alice", "paper", "1000000.00", 30)
    from saham_signal.application.positions import transition

    state = transition(scope, None, command("open", OPEN), FILL_NOW, "confirmed")
    reports = fill_reports(run(), [state])
    assert reports["paper"]["fill_count"] == 2
    assert reports["actual"]["fill_count"] == 1
    assert reports["actual"]["buy_lots"] == 2
    assert reports["actual"]["origin"] == "manual"
    assert reports["combined_pnl"] is None


def test_database_evidence_operator_cas_report_snapshot_rls_and_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with disposable_database("paper") as (owner, runtime):
        account = "simulation-account"
        operator = PostgresPaperEvidence(owner, account)
        reader = PostgresPaperEvidence(runtime, account)
        receipt = acceptance()
        cursor = operator.record("acceptance", receipt, 0, "test-reviewer")
        assert cursor == operator.record("acceptance", receipt, 0, "test-reviewer")
        with pytest.raises(ValueError, match="operator"):
            reader.record("acceptance", receipt, 0, "test-reviewer")
        g0_cursor = operator.record("G0", review("G0", "pending"), 0, "test-reviewer")
        with pytest.raises(ValueError, match="revision"):
            operator.record("G0", review("G0", "no-go"), 0, "test-reviewer")
        operator.record("G0", review("G0", "no-go"), g0_cursor, "test-reviewer")
        assert operator.record("G0", review("G0", "pending"), 0, "test-reviewer") == g0_cursor
        simulation = run()
        PostgresPaper(runtime, account).append(simulation)
        scope = MarketScope(account, "paper", "1000000.00", 30)
        PostgresPositions(runtime).execute(
            scope, "manual-confirmation", command("open", OPEN), FILL_NOW
        )
        result = reader.report(RELEASE, NOW, paused=False)
        assert result["acceptance"]["acceptance_passed"]
        assert not result["acceptance"]["can_advance"]
        assert result["acceptance"]["gates"]["G0"]["decision"] == "no-go"
        assert result["fill_reports"]["paper"]["fill_count"] == 2
        assert result["fill_reports"]["actual"]["fill_count"] == 1
        from fastapi.testclient import TestClient

        real_report = reader.report
        settings = config()
        with monkeypatch.context() as patch:
            patch.setattr(
                PostgresPaperEvidence,
                "report",
                lambda *a, **k: real_report(RELEASE, NOW, paused=False),
            )
            with TestClient(
                create_app(settings, operations=Operations(SimulationControl(), "paper"))
            ) as client:
                client.cookies.set("saham_session", session_cookie(settings))
                response = client.get("/api/ops/paper")
                assert response.status_code == 200
                assert response.json()["fill_reports"]["actual"]["fill_count"] == 1
                assert response.json()["fill_reports"]["paper"]["fill_count"] == 2
        assert not PostgresPaperEvidence(runtime, "other").report(RELEASE, NOW, paused=False)[
            "acceptance"
        ]["acceptance_passed"]
        with psycopg.connect(runtime) as conn:
            conn.execute("SELECT set_config('ss.mode','paper',true)")
            conn.execute("SELECT set_config('ss.user_id',%s,true)", (account,))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO paper_evidence(mode,user_id,kind,content_digest,actor,payload) "
                    "VALUES ('paper',%s,'G1',%s,'intruder','{}'::jsonb)",
                    (account, "0" * 64),
                )
        for statement in (
            "DELETE FROM paper_evidence",
            "TRUNCATE paper_evidence",
            "UPDATE paper_evidence SET actor='edited'",
        ):
            with psycopg.connect(owner) as conn:
                with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                    conn.execute(statement)
        blocked = deepcopy(receipt)
        blocked["scenarios"][0]["status"] = "blocked"
        blocked["scenarios"][0]["evidence"][0]["status"] = "blocked"
        blocked["acceptance_passed"] = False
        operator.record("acceptance", seal(blocked), cursor, "test-reviewer")
        with pytest.raises(ValueError, match="blocked"):
            reader.require_admission(RELEASE, NOW, paused=False)
        held = reader.report(RELEASE, NOW, paused=False)
        assert "CRITICAL_ACCEPTANCE_INCOMPLETE" in held["acceptance"]["reasons"]
        if path := os.environ.get("PAPER_EVIDENCE_REPORT"):
            Path(path).write_text(
                json.dumps(
                    {
                        "origin": "simulation",
                        "scope": "synthetic PostgreSQL integration; not gate approval",
                        "before_critical_failure": result,
                        "after_critical_failure": held,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        snapshot = backup(owner, "paper")
        with disposable_database("paper") as (target, restored):
            restore(target, "paper", snapshot, "empty:saham_signal_paper")
            report = PostgresPaperEvidence(restored, account).report(RELEASE, NOW, paused=False)
            assert report["fill_reports"] == result["fill_reports"]
            assert "OPERATIONS_BLOCKED" in report["acceptance"]["reasons"]


def test_signed_paper_cors_and_separate_account_report(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    settings = config()
    report = {
        "receipt": run(),
        "acceptance": assess(RELEASE, NOW, evidence(), paused=True),
        "fill_reports": fill_reports(run(), []),
    }
    monkeypatch.setattr(PostgresPaperEvidence, "report", lambda *a, **k: report)
    with TestClient(
        create_app(settings, operations=Operations(SimulationControl(), "paper"))
    ) as client:
        client.cookies.set("saham_session", session_cookie(settings))
        response = client.get("/api/ops/paper", headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-credentials"] == "true"
        assert len(response.json()["acceptance"]["scenarios"]) == 12
