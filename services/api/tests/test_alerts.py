"""SS-022: retry, replay isolation, hysteresis and durable concurrent delivery."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_persistence import database  # noqa: F401
from test_positions import BUY, NOW, OPEN, PLAN, SCOPE, MemoryPositions, command

from saham_signal.adapters.alerts import PostgresAlerts
from saham_signal.adapters.positions import PostgresPositions
from saham_signal.application.alerts import (
    PRIORITY,
    AlertEvent,
    delivery,
    feed_event,
    source_events,
)
from saham_signal.application.feed_quality import FeedAssessment, PositionDataDisruption
from saham_signal.application.market import FixtureMarket, MarketScope, validate
from saham_signal.application.positions import monitor, transition
from saham_signal.config import Settings
from saham_signal.transport.http import create_app

TOKEN = "alerts-research-test-session-1234567890"
STOP = AlertEvent("position:1:stop:1", "STOP", NOW, position_id="position-1")


class MemoryAlerts:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.gates: dict[tuple[str, str, str], dict[str, Any]] = {}

    def refresh(
        self, scope: MarketScope, events: list[AlertEvent], at: datetime
    ) -> list[dict[str, Any]]:
        for event in events:
            key = scope.mode, scope.account, event.key
            if key in self.items and event.active:
                continue
            gate = self.gates.setdefault((scope.mode, scope.account, event.group), {})
            result = delivery(scope, event, at, gate)
            if result:
                self.items.setdefault(key, result)
        return sorted(
            [
                v
                for (mode, account, _), v in self.items.items()
                if (mode, account) == (scope.mode, scope.account)
            ],
            key=lambda item: PRIORITY[item["type"]],
        )


@pytest.mark.parametrize("kind", list(PRIORITY))
def test_contract_and_isolation(kind: Any) -> None:
    event = replace(STOP, kind=kind)
    result = delivery(SCOPE, event, NOW + timedelta(seconds=4), {"since": NOW.isoformat()})
    assert result is not None
    validate("Alert", result)
    assert result["status"] == "pending" and result["delivered_at"] is None
    assert delivery(replace(SCOPE, mode="live"), event, NOW, {}) is None
    assert (
        delivery(replace(SCOPE, mode="live"), replace(event, origin="market", replay=True), NOW, {})
        is None
    )
    assert delivery(SCOPE, replace(event, replay=True), NOW, {}) is None


def test_hysteresis_reset_cooldown_and_risk_bypass() -> None:
    ready = replace(STOP, kind="ENTRY_READY")
    gate: dict[str, Any] = {}
    assert delivery(SCOPE, ready, NOW, gate) is None
    assert delivery(SCOPE, replace(ready, active=False), NOW + timedelta(seconds=2), gate) is None
    assert delivery(SCOPE, ready, NOW + timedelta(seconds=3), gate) is None
    assert delivery(SCOPE, ready, NOW + timedelta(seconds=5), gate) is None
    assert delivery(SCOPE, ready, NOW + timedelta(seconds=6), gate)
    assert (
        delivery(SCOPE, replace(ready, key="version-2"), NOW + timedelta(seconds=7), gate) is None
    )
    assert delivery(SCOPE, STOP, NOW + timedelta(seconds=7), gate)


def test_feed_recovery_episode_dedup_and_mode_origin_guards() -> None:
    assessment = FeedAssessment(
        "TEST",
        NOW,
        "disconnected",
        ("HEARTBEAT_TIMEOUT",),
        None,
        None,
        None,
        False,
        False,
        "test-only",
        "research",
        "simulation",
    )
    warning = PositionDataDisruption("fixture", "TEST", "position-1", 1, assessment)
    event = feed_event(warning)
    store = MemoryAlerts()
    assert len(store.refresh(SCOPE, [event, feed_event(warning)], NOW)) == 1
    assert len(store.refresh(SCOPE, [feed_event(replace(warning, episode=2))], NOW)) == 2
    assert delivery(SCOPE, replace(STOP, origin="market"), NOW, {}) is None
    assert (
        delivery(replace(SCOPE, mode="live"), replace(STOP, origin="market", mode="paper"), NOW, {})
        is None
    )
    assert (
        delivery(
            replace(SCOPE, mode="live"),
            replace(STOP, origin="market", mode="live", replay=True),
            NOW,
            {},
        )
        is None
    )
    assert (
        delivery(
            replace(SCOPE, mode="live"), replace(STOP, origin="simulation", mode="live"), NOW, {}
        )
        is None
    )


def test_projection_uses_latest_signal_and_confirmed_exit_not_prices() -> None:
    market = FixtureMarket(lambda: NOW)
    history = market.read(SCOPE, "history", "TEST")["data"]
    history[0]["state"] = "READY"
    old = {**history[0], "state": "EXPIRED", "version": 2}
    events = source_events([history[0], old], {"status": "healthy"}, [], NOW)
    assert not any(e.active for e in events if e.kind == "ENTRY_READY")
    assert any(e.kind == "INVALIDATED" for e in events)
    state = transition(SCOPE, None, command("open", OPEN), NOW)
    state = transition(SCOPE, state, command("plan", PLAN), NOW)
    assert not any(
        e.kind in {"STOP", "TP", "TIME_EXIT"}
        for e in source_events([], {"status": "healthy"}, [monitor(state, NOW)], NOW)
    )
    late = NOW + timedelta(days=1)
    events = source_events([], {"status": "disconnected"}, [monitor(state, late)], late)
    assert {e.kind for e in events} >= {"TIME_EXIT", "DATA_DISCONNECTED"}
    assert state["position"]["remaining_lots"] == BUY["lots"]


def test_api_auth_retry_expiry_and_fail_closed() -> None:
    clock = [NOW]
    store, positions = MemoryAlerts(), MemoryPositions()
    with TestClient(
        create_app(
            Settings(market_fixture_enabled=True, market_fixture_token=SecretStr(TOKEN)),
            market=FixtureMarket(lambda: clock[0]),
            positions=positions,
            alerts=store,
        ),
        raise_server_exceptions=False,
    ) as client:
        assert client.get("/api/v1/alerts").status_code == 401
        client.cookies.set("saham_session", TOKEN)
        first = client.get("/api/v1/alerts")
        assert first.status_code == 200
        validate("AlertsResponse", first.json())
        assert "no-store" in first.headers["cache-control"]
        assert first.json()["data"] == client.get("/api/v1/alerts").json()["data"]
        assert client.get("/api/v1/alerts?mode=live").status_code == 422
        assert client.post("/api/v1/alerts", json={}).status_code == 405
        clock[0] += timedelta(hours=1)
        data = client.get("/api/v1/alerts").json()["data"]
        assert len([a for a in data if a["type"] == "INVALIDATED"]) == 1
        assert data == client.get("/api/v1/alerts").json()["data"]


def test_database_failure_has_no_memory_fallback() -> None:
    class Unavailable:
        def refresh(
            self, scope: MarketScope, events: list[AlertEvent], at: datetime
        ) -> list[dict[str, Any]]:
            raise psycopg.OperationalError("unavailable")

    with TestClient(
        create_app(
            Settings(market_fixture_enabled=True, market_fixture_token=SecretStr(TOKEN)),
            market=FixtureMarket(lambda: NOW),
            positions=MemoryPositions(),
            alerts=Unavailable(),
        )
    ) as client:
        client.cookies.set("saham_session", TOKEN)
        response = client.get("/api/v1/alerts")
        assert response.status_code == 503
        assert response.json()["data"]["code"] == "DATA_UNAVAILABLE"
        validate("ErrorResponse", response.json())


def test_durable_races_restart_scope_and_immutability(database: tuple[str, str]) -> None:  # noqa: F811
    owner, runtime = database
    store = PostgresAlerts(runtime)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.refresh(SCOPE, [STOP], NOW), range(8)))
    assert all(len(items) == 1 for items in results)
    assert PostgresAlerts(runtime).refresh(SCOPE, [STOP], NOW) == results[0]
    other = replace(SCOPE, account="bob")
    assert store.refresh(other, [], NOW) == []
    assert store.refresh(other, [STOP], NOW)[0]["dedup_key"] != results[0][0]["dedup_key"]
    with psycopg.connect(owner) as connection:
        assert connection.execute("SELECT count(*) FROM in_app_alerts").fetchone() == (2,)
    with psycopg.connect(runtime) as connection:
        connection.execute("SELECT set_config('ss.mode','research',true)")
        connection.execute("SELECT set_config('ss.user_id','alice',true)")
        assert connection.execute("SELECT count(*) FROM in_app_alerts").fetchone() == (1,)
        connection.execute("SELECT set_config('ss.user_id','stranger',true)")
        assert connection.execute("SELECT count(*) FROM in_app_alerts").fetchone() == (0,)
        with pytest.raises(psycopg.Error, match="append-only"):
            connection.execute("DELETE FROM in_app_alerts")
    with pytest.raises(ValueError, match="mode"):
        store.refresh(replace(SCOPE, mode="paper"), [STOP], NOW)


def test_atomic_exit_offline(database: tuple[str, str]) -> None:  # noqa: F811
    _, runtime = database
    positions = PostgresPositions(runtime)
    state = positions.execute(SCOPE, "open", command("open", OPEN), NOW)
    pid = state["position"]["position_id"]
    positions.execute(SCOPE, "stop", command("exit", {"reason": "STOP"}, pid), NOW)
    positions.execute(SCOPE, "sell", command("fill", {**BUY, "side": "SELL"}, pid), NOW)
    inbox = PostgresAlerts(runtime).refresh(SCOPE, [], NOW)
    assert [a["type"] for a in inbox] == ["STOP"]
    assert positions.list(SCOPE)[0]["position"]["remaining_lots"] == 0


def test_persistent_ready_gate_no_replay(database: tuple[str, str]) -> None:  # noqa: F811
    _, runtime = database
    ready = replace(STOP, kind="ENTRY_READY")
    assert PostgresAlerts(runtime).refresh(SCOPE, [ready], NOW) == []
    assert len(PostgresAlerts(runtime).refresh(SCOPE, [ready], NOW + timedelta(seconds=3))) == 1
    replay = replace(STOP, replay=True)
    inbox = PostgresAlerts(runtime).refresh(SCOPE, [replay], NOW + timedelta(seconds=4))
    assert [a["type"] for a in inbox] == ["ENTRY_READY"]
