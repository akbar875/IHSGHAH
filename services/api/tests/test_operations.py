"""SS-025 synthetic operations qualification, never vendor/live gate evidence."""

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from time import perf_counter

import psycopg
import pytest
from fastapi.testclient import TestClient
from preference_store import MemoryPreferences
from psycopg.conninfo import conninfo_to_dict
from pydantic import SecretStr
from test_alerts import STOP, MemoryAlerts
from test_feed import NOW, messages, setup
from test_feed_quality import ready, send
from test_instruments import refs as refs  # noqa: F401
from test_news import ingest as ingest_news
from test_persistence import (
    database,  # noqa: F401
    disposable_database,
    record,
)
from test_positions import NOW as POSITION_NOW
from test_positions import OPEN, SCOPE, MemoryPositions, command
from test_preferences import settings as personal_settings
from test_risk import FEE, INPUTS, SPEC

from saham_signal.adapters.alerts import PostgresAlerts
from saham_signal.adapters.backup import TABLES, backup, restore
from saham_signal.adapters.instrument_references import MemoryReferences
from saham_signal.adapters.news import NewsRepository
from saham_signal.adapters.operations import PostgresControl
from saham_signal.adapters.persistence import Journal
from saham_signal.adapters.positions import PostgresPositions
from saham_signal.adapters.preferences import PostgresPreferences
from saham_signal.application.market import FixtureMarket
from saham_signal.application.operations import Action, Control, Operations, Telemetry, change
from saham_signal.application.risk import Plan, PlanCommand, transition
from saham_signal.application.security import session_cookie
from saham_signal.config import Settings
from saham_signal.domain.mode import Mode
from saham_signal.domain.persistence import digest


class MemoryControl:
    def __init__(self, value: Control | None = None) -> None:
        self.value = value or Control()

    def read(self, mode: Mode) -> Control:
        return self.value

    def write(
        self, mode: Mode, expected: int, action: Action, release: str, evidence: str, actor: str
    ) -> Control:
        if expected != self.value.revision:
            raise ValueError("revision conflict")
        self.value = change(self.value, action, release, evidence)
        return self.value


def test_kill_drift_rollback_and_missing_control_hold_ready_without_position_effects(
    refs: MemoryReferences,
) -> None:
    control = MemoryControl(INPUTS.operations)
    ops = Operations(control, "research")
    plan = transition(Plan(SPEC), PlanCommand("ready", 0, "evaluate", INPUTS), refs, [FEE])
    assert plan.state == "READY"
    for action in ("pause", "drift", "rollback"):
        control.write(
            "research", control.value.revision, action, "old-reviewed-sha", "incident-1", "op"
        )
        held = transition(
            plan,
            PlanCommand(action, 1, "evaluate", replace(INPUTS, operations=ops.control())),
            refs,
            [FEE],
        )
        assert held.state == "WATCH" and held.decision and held.decision.shares == 0
        assert held.decision.reason == "operations_blocked"
    ops.observe_drift("holdout-monitor-report-sha")
    assert ops.entry_blocked() and ops.control().reason == "drift"
    assert ops.telemetry.snapshot()["counters"]["drift"] == 1
    default = transition(
        Plan(SPEC),
        PlanCommand("default", 0, "evaluate", replace(INPUTS, operations=Control())),
        refs,
        [FEE],
    )
    assert default.state == "WATCH"


def test_control_failure_and_failed_drift_write_never_open_entry() -> None:
    class Broken(MemoryControl):
        def read(self, mode: Mode) -> Control:
            raise RuntimeError("private-dsn-must-not-leak")

    ops = Operations(Broken(), "research")
    assert ops.entry_blocked() and ops.control().reason == "control_unavailable"
    with pytest.raises(RuntimeError):
        ops.observe_drift("monitor-evidence")
    assert ops.entry_blocked() and ops.local_drift


def test_bounded_telemetry_and_unknown_values() -> None:
    stats = Telemetry()
    assert stats.snapshot()["internal_p95_seconds"] is None
    assert stats.snapshot()["gauges"]["cost_idr"] is None
    for i in range(3000):
        stats.latency(i / 1000)
    assert stats.snapshot()["latency_samples"] == 2048
    assert stats.snapshot()["internal_p95_seconds"] == 2.897
    for value in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            stats.gauge("cost_idr", value)
    with pytest.raises(ValueError):
        stats.count("account-secret")


def test_signed_ops_read_and_kill_preserve_manual_positions_and_risk_alerts() -> None:
    config = Settings(
        market_fixture_enabled=True,
        market_fixture_token=SecretStr("fixture-token-12345678901234567890"),
        session_secret=SecretStr("signed-session-secret-12345678901234567890"),
        pilot_account_id="alice",
    )
    positions, alerts = MemoryPositions(), MemoryAlerts()
    positions.execute(SCOPE, "open-1", command("open", OPEN), POSITION_NOW)
    before = deepcopy(positions.rows)
    control = MemoryControl()
    ops = Operations(control, "research")
    from saham_signal.transport.http import create_app

    with TestClient(
        create_app(
            config,
            market=FixtureMarket(lambda: POSITION_NOW),
            positions=positions,
            preferences=MemoryPreferences(),
            alerts=alerts,
            operations=ops,
        )
    ) as client:
        assert client.get("/api/ops/status").status_code == 401
        assert config.market_fixture_token is not None
        client.cookies.set("saham_session", config.market_fixture_token.get_secret_value())
        assert client.get("/api/ops/status").status_code == 401
        client.cookies.set("saham_session", session_cookie(config))
        status = client.get("/api/ops/status")
        assert status.status_code == 200 and status.json()["control"]["blocked"]
        assert "private-dsn" not in status.text
        assert client.get("/api/v1/positions").json()["data"][0]["remaining_lots"] == 2
        first = client.get("/api/v1/alerts").json()["data"]
        assert first and all(a["type"] != "ENTRY_READY" for a in first)
        assert client.get("/api/v1/alerts").json()["data"] == first
        assert positions.rows == before
        assert client.post("/api/ops/status", json={"blocked": False}).status_code == 405


def test_outage_reconnect_has_fresh_book_and_no_duplicate_risk_alert() -> None:
    feed = ready()
    ops = Operations(MemoryControl(), "research")
    feed.operations = ops
    feed.assess_quality("SIM", NOW)
    send(feed, 1, 1, sequence=3)  # dropped delta; never merge across gap
    assert not feed.assess_quality("SIM", NOW + timedelta(seconds=1)).entry_allowed
    feed.reconnect()
    send(feed, 0, 2, connection=2)
    assert (
        not feed.books["SIM"].synchronized
        or not feed.assess_quality("SIM", NOW + timedelta(seconds=2)).entry_allowed
    )
    send(feed, 4, 3, connection=2)
    send(feed, 0, 4, sequence=2, connection=2)
    assert feed.assess_quality("SIM", NOW + timedelta(seconds=4)).entry_allowed
    assert feed.books["SIM"].bids == {"1000.00": 5}
    assert "995.00" not in feed.books["SIM"].bids
    feed.assess_quality("SIM", NOW + timedelta(seconds=65))
    assert not feed.books["SIM"].synchronized
    assert ops.telemetry.snapshot()["counters"]["feed_gap"] >= 1
    assert ops.telemetry.snapshot()["gauges"]["feed_lag_seconds"] == 62


def test_pilot_synthetic_burst_latency_and_five_second_cycle() -> None:
    """100 symbols / 5s cycle, 20 cycles, 1 operator / <=3 open positions.

    Measure validated ingest -> committed in-memory book consumer. This is a
    component stress target; browser received_at-to-display still needs SS-026.
    """
    feed, _, _ = setup()
    durations, cycles = [], []
    template = messages()[0]
    for cycle in range(20):
        started = perf_counter()
        for symbol in range(100):
            at = NOW + timedelta(seconds=cycle * 5)
            message = replace(
                template,
                symbol=f"S{symbol:03}",
                sequence=cycle + 1,
                event_id=f"{cycle}-{symbol}",
                event_time=at,
            )
            received = perf_counter()
            feed.ingest(message, received_at=at, available_at=at, processed_at=at)
            assert feed.books[message.symbol].synchronized
            assert feed.books[message.symbol].bids == {"1000.00": 5}
            durations.append(perf_counter() - received)
        cycles.append(perf_counter() - started)
    p95 = sorted(durations)[1899]
    assert p95 <= 2 and max(cycles) <= 5
    report = {
        "data_origin": "simulation",
        "symbols": 100,
        "cycles": 20,
        "messages": 2000,
        "component_p95_seconds": p95,
        "max_cycle_seconds": max(cycles),
        "browser_display_tested": False,
        "vendor_sla_tested": False,
    }
    if path := os.environ.get("OPERATIONS_REPORT"):
        Path(path).write_text(json.dumps(report, indent=2), encoding="utf-8")


def test_postgres_cas_restart_mode_and_immutable_audit(database: tuple[str, str]) -> None:  # noqa: F811
    owner, runtime = database
    store = PostgresControl(runtime)
    assert store.read("research").blocked
    store.write("research", 0, "resume", "reviewed-sha", "approved-evaluation", "operator")
    assert not PostgresControl(runtime).read("research").blocked

    def pause(_: int) -> bool:
        try:
            store.write("research", 1, "pause", "reviewed-sha", "incident", "operator")
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(pause, range(8))) == 1
    assert store.read("research").blocked and store.read("research").revision == 2
    with pytest.raises(ValueError, match="Database"):
        store.read("paper")
    with psycopg.connect(owner) as conn, pytest.raises(psycopg.Error):
        conn.execute("UPDATE operation_events SET blocked=false")


@pytest.fixture
def restore_target() -> Iterator[tuple[str, str]]:
    with disposable_database() as pair:
        yield pair


def test_backup_restore_positions_inbox_gates_and_identity(
    database: tuple[str, str],  # noqa: F811
    restore_target: tuple[str, str],
) -> None:
    source, runtime = database
    target, target_runtime = restore_target
    positions = PostgresPositions(runtime)
    opened = positions.execute(SCOPE, "manual-open", command("open", OPEN), POSITION_NOW)
    store = PostgresControl(runtime)
    store.write("research", 0, "resume", "approved-sha", "review", "operator")
    Journal(runtime, "research", "pilot-sim").append([record()])
    inbox = PostgresAlerts(runtime).refresh(SCOPE, [STOP], POSITION_NOW)
    assert len(inbox) == 1
    PostgresPreferences(runtime).put(SCOPE, "RiskSettings", "settings", personal_settings())
    ingest_news(NewsRepository(runtime))
    with psycopg.connect(source) as conn:
        conn.execute(
            "INSERT INTO retention_policy(mode,source,retain_days,legal_hold,approval_ref) "
            "VALUES ('research','sim-fixture',NULL,true,'simulation-only-hold')"
        )

    document = backup(source, "research")
    invalid = deepcopy(document)
    invalid["tables"]["operation_events"][0]["revision"] = -1
    invalid["sha256"] = digest({k: v for k, v in invalid.items() if k != "sha256"})
    with pytest.raises(psycopg.Error):
        restore(target, "research", invalid, "empty:saham_signal_research")
    assert all(not rows for rows in backup(target, "research")["tables"].values())
    counts = restore(target, "research", document, "empty:saham_signal_research")
    assert set(counts) == set(TABLES) and counts["manual_position_events"] == 1
    assert PostgresPositions(target_runtime).list(SCOPE) == positions.list(SCOPE)
    assert PostgresControl(target_runtime).read("research").blocked
    assert PostgresAlerts(target_runtime).refresh(SCOPE, [STOP], POSITION_NOW) == inbox
    # Retry after restore reuses the original event; no duplicate position or inbox event.
    assert (
        PostgresPositions(target_runtime).execute(
            SCOPE, "manual-open", command("open", OPEN), POSITION_NOW
        )
        == opened
    )
    recovered = backup(target, "research")
    for name in TABLES:
        if name != "operation_events":
            assert recovered["tables"][name] == document["tables"][name]
    second = PostgresPositions(target_runtime).execute(
        SCOPE, "manual-second", command("open", OPEN), POSITION_NOW
    )
    assert second["position"]["position_id"] != opened["position"]["position_id"]
    assert len(PostgresPositions(target_runtime).list(SCOPE)) == 2
    assert len(positions.list(SCOPE)) == 1
    with pytest.raises(ValueError, match="not empty"):
        restore(target, "research", document, "empty:saham_signal_research")
    bad = deepcopy(document)
    bad["tables"]["journal"] = []
    bad["sha256"] = "broken"
    with pytest.raises(ValueError, match="integrity"):
        restore(target, "research", bad, "empty:saham_signal_research")
    with pytest.raises(ValueError, match="BYPASSRLS"):
        backup(runtime, "research")
    if path := os.environ.get("OPERATIONS_RESTORE_REPORT"):
        Path(path).write_text(
            json.dumps(
                {
                    "data_origin": "simulation",
                    "tables_restored": counts,
                    "all_rows_equal_except_appended_pause": True,
                    "restored_entry_blocked": True,
                    "retry_deduplicated": True,
                    "nonempty_target_rejected": True,
                    "checksum_tamper_rejected": True,
                    "runtime_role_backup_rejected": True,
                    "failed_restore_atomic": True,
                    "new_identity_after_restore": True,
                    "source_unchanged": True,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def test_operator_cli_scope_revision_and_sanitized_failure(
    database: tuple[str, str],  # noqa: F811
    tmp_path: Path,
) -> None:
    source, _ = database
    options = conninfo_to_dict(source)["options"]
    assert isinstance(options, str)
    env = {
        **os.environ,
        "APP_MODE": "research",
        "DATABASE_URL": os.environ["PERSISTENCE_TEST_DSN"],
        "PGOPTIONS": options,
    }
    args = [sys.executable, "-m", "saham_signal.operations"]
    changed = subprocess.run(
        [
            *args,
            "control",
            "pause",
            "--expected-revision",
            "0",
            "--release",
            "reviewed-sha",
            "--evidence",
            "incident",
            "--actor",
            "operator",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert changed.returncode == 0 and json.loads(changed.stdout)["blocked"]
    path = tmp_path / "backup.json"
    saved = subprocess.run(
        [*args, "backup", str(path)], env=env, capture_output=True, text=True, timeout=15
    )
    assert saved.returncode == 0 and json.loads(path.read_text())["sha256"]
    failed = subprocess.run(
        [*args, "backup", str(path)], env=env, capture_output=True, text=True, timeout=15
    )
    assert failed.returncode != 0 and "Operation failed" in failed.stderr
    assert "postgresql://" not in failed.stderr and "Traceback" not in failed.stderr
