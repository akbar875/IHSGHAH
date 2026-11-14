"""Cross-component paper qualification; never licensed-feed or G2 evidence."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_persistence import disposable_database

from saham_signal.adapters.backup import backup, restore
from saham_signal.adapters.paper import PostgresPaper
from saham_signal.adapters.paper_simulation import SimulationControl, run, scenario
from saham_signal.application.operations import Operations
from saham_signal.application.paper import qualify, readiness
from saham_signal.application.security import session_cookie
from saham_signal.config import Settings
from saham_signal.domain.persistence import digest
from saham_signal.transport.http import create_app


def test_feed_baseline_risk_execution_report_is_deterministic_and_separate() -> None:
    report = run()
    assert report == run()
    assert report["plan"]["plan"]["state"] == "READY"
    assert report["features"]["mode"] == "paper"
    assert report["features"]["return_fraction"] is not None
    assert report["baseline_score"] is not None
    assert [f["side"] for f in report["paper_fills"]] == ["buy", "sell"]
    assert report["paper_positions"] == {"SIMA": 0}
    assert report["actual_fills"] == []
    assert report["alert_preview"] is None  # One observation cannot satisfy hysteresis.
    assert not report["live_alerts_enabled"]
    assert not report["readiness"]["paper_live_enabled"]
    assert report["readiness"]["eligible_prospective_trades"] == 0
    assert digest({k: v for k, v in report.items() if k != "sha256"}) == report["sha256"]
    path = os.environ.get("PAPER_SIMULATION_REPORT")
    if path:
        Path(path).write_text(json.dumps(report, indent=2), encoding="utf-8")


def test_future_messages_cannot_change_features_ranking_or_risk() -> None:
    args = scenario()
    original = qualify(**args)
    args["messages"] = [(m, at) for m, at in args["messages"] if at <= args["inputs"].at]
    past = qualify(**args)
    assert original["features"] == past["features"]
    assert original["plan"] == past["plan"]
    assert original["baseline_score"] == past["baseline_score"]
    assert past["paper_fills"] == []  # No book after execution latency.


def test_missing_feed_and_paused_controls_cannot_produce_paper_fills() -> None:
    args = scenario()
    args["messages"] = []
    assert qualify(**args)["paper_fills"] == []

    class Paused(SimulationControl):
        def read(self, mode: Any) -> Any:
            return replace(super().read(mode), blocked=True, reason="pause")

    args = scenario()
    args["operations"].store = Paused()
    paused = qualify(**args)
    assert paused["paper_fills"] == []
    assert paused["plan"]["plan"]["decision"]["reason"] == "operations_blocked"


def test_namespace_and_flat_start_guards() -> None:
    for mode in ("research", "live"):
        args = scenario()
        args["spec"] = replace(args["spec"], mode=mode)
        with pytest.raises(ValueError, match="isolated"):
            qualify(**args)
    args = scenario()
    args["profile"] = replace(args["profile"], origin="market", approval_ref="fake")
    with pytest.raises(ValueError, match="isolated"):
        qualify(**args)
    args = scenario()
    args["inputs"] = replace(
        args["inputs"], portfolio=replace(args["inputs"].portfolio, occupied_slots=1)
    )
    with pytest.raises(ValueError, match="isolated"):
        qualify(**args)


def test_old_candle_and_missing_heartbeat_cannot_fabricate_exit() -> None:
    args = scenario()
    args["messages"] = [
        (
            replace(m, payload={**m.payload, "at": "2026-10-01T02:29:00Z"})
            if m.kind == "candle"
            else m,
            at,
        )
        for m, at in args["messages"]
    ]
    report = qualify(**args)
    assert [f["side"] for f in report["paper_fills"]] == ["buy"]
    assert report["paper_positions"]["SIMA"] > 0
    args = scenario()
    args["messages"] = [
        (m, at)
        for m, at in args["messages"]
        if not (m.kind == "heartbeat" and at > args["inputs"].at)
    ]
    report = qualify(**args)
    assert [f["side"] for f in report["paper_fills"]] == ["buy"]
    assert report["paper_positions"]["SIMA"] > 0


def test_fractional_execution_price_is_rejected_without_rounding() -> None:
    args = scenario()
    args["messages"] = [
        (
            replace(m, payload={**m.payload, "asks": [{"price_idr": "1005.50", "quantity": 10000}]})
            if m.kind == "book_snapshot"
            else m,
            at,
        )
        for m, at in args["messages"]
    ]
    with pytest.raises(ValueError, match="integral IDR"):
        qualify(**args)


def test_observation_freeze_and_critical_failures_never_open_gates() -> None:
    protocol = scenario()["protocol"]
    assert not protocol.document()["budgets_complete"]
    complete = replace(
        protocol,
        validation_ref="synthetic-validation-only",
        maximum_brier=Decimal("0.2"),
        maximum_fill_rate_error=Decimal("0.1"),
        maximum_drawdown_idr=Decimal("1000"),
    )
    assert complete.document()["budgets_complete"]
    assert protocol.document()["sha256"] != complete.document()["sha256"]
    passed = {i: "passed" for i in range(1, 13)}
    assert readiness(complete, passed)["missing_scenarios"] == []
    assert not readiness(complete, passed)["paper_live_enabled"]
    passed[7] = "failed"
    assert "CRITICAL_ACCEPTANCE_INCOMPLETE" in readiness(complete, passed)["reasons"]
    with pytest.raises(ValueError, match="Freeze"):
        replace(protocol, frozen_at=protocol.starts_at)
    with pytest.raises(ValueError, match="60 sessions"):
        replace(protocol, minimum_sessions=59)
    with pytest.raises(ValueError, match="300 eligible"):
        replace(protocol, minimum_trades=299)
    with pytest.raises(ValueError, match="finite"):
        replace(protocol, maximum_brier=Decimal("NaN"))
    with pytest.raises(ValueError, match="exceed"):
        replace(protocol, maximum_fill_rate_error=Decimal("1.1"))


def config() -> Settings:
    return Settings(
        app_mode="paper",
        database_url=SecretStr("postgresql://unused@localhost/saham_signal_paper"),
        redis_namespace="saham-signal:paper:",
        session_secret=SecretStr("paper-secret-123456789012345678901234567890"),
        pilot_account_id="simulation-account",
    )


def test_signed_paper_receipt_api_and_database_outage(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = config()
    with TestClient(
        create_app(settings, operations=Operations(SimulationControl(), "paper"))
    ) as client:
        assert client.get("/api/ops/paper").status_code == 401
        client.cookies.set("saham_session", session_cookie(settings))
        monkeypatch.setattr(PostgresPaper, "latest", lambda _: run())
        response = client.get("/api/ops/paper")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["receipt"]["actual_fills"] == []

        def unavailable(_: Any) -> None:
            raise psycopg.OperationalError("private-dsn")

        monkeypatch.setattr(PostgresPaper, "latest", unavailable)
        failed = client.get("/api/ops/paper")
        assert failed.status_code == 503 and "private-dsn" not in failed.text


def test_postgres_paper_receipt_retry_rls_immutability_and_restore() -> None:
    with disposable_database("paper") as (owner, runtime):
        report = run()
        repo = PostgresPaper(runtime, report["account"])
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert len(set(pool.map(lambda _: repo.append(report), range(4)))) == 1
        assert repo.latest() == report
        assert PostgresPaper(runtime, "another-account").latest() is None
        tampered = deepcopy(report)
        tampered["actual_fills"] = ["invented"]
        with pytest.raises(ValueError):
            repo.append(tampered)
        for statement in (
            "UPDATE paper_qualification SET user_id='another-account'",
            "DELETE FROM paper_qualification",
            "TRUNCATE paper_qualification",
        ):
            with psycopg.connect(runtime) as conn:
                conn.execute("SELECT set_config('ss.mode','paper',true)")
                conn.execute("SELECT set_config('ss.user_id',%s,true)", (report["account"],))
                with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                    conn.execute(statement)
        snapshot = backup(owner, "paper")
        assert len(snapshot["tables"]["paper_qualification"]) == 1
        with disposable_database("paper") as (target, reader):
            restore(target, "paper", snapshot, "empty:saham_signal_paper")
            assert PostgresPaper(reader, report["account"]).latest() == report
