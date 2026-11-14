"""SS-021 acceptance and durable idempotency, including races and account isolation."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_persistence import database  # noqa: F401

from saham_signal.adapters.positions import PostgresPositions
from saham_signal.application.market import FixtureMarket, MarketScope, validate
from saham_signal.application.positions import PositionConflict, monitor, transition
from saham_signal.config import Settings
from saham_signal.transport.http import create_app

NOW = datetime(2026, 11, 14, 3, tzinfo=UTC)
SCOPE = MarketScope("alice", "research", "1000000.00", 30)
TOKEN = "manual-position-test-session-12345"
HEADERS = {"Origin": "http://localhost:3000", "Idempotency-Key": "open-1"}
BUY = {
    "side": "BUY",
    "price_idr": "1000.00",
    "lots": 2,
    "fees_idr": "300.00",
    "filled_at": "2026-11-14T02:00:00Z",
}
OPEN = {"symbol": "TEST", "signal_id": None, "fill": BUY}
PLAN = {
    "stop_idr": "990.00",
    "target_idr": "1100.00",
    "exit_deadline": "2026-11-14T08:00:00Z",
    "sell_fee_ratio": "0.002500",
}


class MemoryPositions:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]] = {}

    def list(self, scope: MarketScope) -> list[dict[str, Any]]:
        latest = {}
        for (mode, account, _), (_, state) in self.rows.items():
            if mode == scope.mode and account == scope.account:
                latest[state["position"]["position_id"]] = deepcopy(state)
        return list(latest.values())

    def execute(
        self, scope: MarketScope, key: str, command: dict[str, Any], at: datetime
    ) -> dict[str, Any]:
        index = scope.mode, scope.account, key
        if index in self.rows:
            old, state = self.rows[index]
            if old != command:
                raise PositionConflict
            return deepcopy(state)
        previous = next(
            (s for s in self.list(scope) if s["position"]["position_id"] == command["position_id"]),
            None,
        )
        state = transition(scope, previous, command, at, key)
        self.rows[index] = deepcopy(command), deepcopy(state)
        return state


def api(store: MemoryPositions, account: str = "alice") -> TestClient:
    result = TestClient(
        create_app(
            Settings(
                market_fixture_enabled=True,
                market_fixture_token=SecretStr(TOKEN),
                pilot_account_id=account,
            ),
            market=FixtureMarket(lambda: NOW),
            positions=store,
        )
    )
    result.cookies.set("saham_session", TOKEN)
    return result


def command(action: str, data: dict[str, Any], pid: str | None = None) -> dict[str, Any]:
    return {"action": action, "data": data, "position_id": pid}


def test_actual_quantity_partial_exit_stop_and_close() -> None:
    state = transition(SCOPE, None, command("open", OPEN), NOW)
    pid = state["position"]["position_id"]
    state = transition(SCOPE, state, command("plan", PLAN, pid), NOW)
    result = monitor(state, NOW)
    assert result["invested_idr"] == "200300.00"  # not the 1m planned nominal
    assert result["stop_loss_idr"] == "2795.00"
    assert result["target_net_idr"] == "19150.00"
    state = transition(SCOPE, state, command("exit", {"reason": "STOP"}, pid), NOW)
    assert state["position"]["remaining_lots"] == 2
    assert state["position"]["status"] == "EXIT_REQUESTED"
    sell = {**BUY, "side": "SELL", "lots": 1, "price_idr": "990.00", "fees_idr": "247.50"}
    state = transition(SCOPE, state, command("fill", sell, pid), NOW)
    result = monitor(state, NOW)
    assert result["position"]["remaining_lots"] == 1
    assert result["remaining_cost_idr"] == "100150.00"
    assert result["realized_pnl_idr"] == "-1397.50"
    assert result["stop_loss_idr"] == "1397.50"
    assert result["position"]["status"] == "EXIT_REQUESTED"
    assert monitor(state, NOW + timedelta(days=1))["position"]["overnight_risk"]
    state = transition(SCOPE, state, command("fill", sell, pid), NOW)
    assert state["position"]["status"] == "CLOSED"
    assert not monitor(state, NOW + timedelta(days=1))["position"]["overnight_risk"]
    assert all(f["origin"] == "manual" for f in state["position"]["fills"])
    assert len({f["fill_id"] for f in state["position"]["fills"]}) == 3
    with pytest.raises(PositionConflict):
        transition(SCOPE, state, command("fill", sell, pid), NOW)


def test_average_partial_and_deadline_without_sell() -> None:
    state = transition(SCOPE, None, command("open", OPEN), NOW)
    state = transition(SCOPE, state, command("fill", {**BUY, "price_idr": "1100.00"}), NOW)
    assert state["position"]["average_price_idr"] == "1050.00"
    state = transition(SCOPE, state, command("fill", {**BUY, "side": "SELL", "lots": 1}), NOW)
    assert state["position"]["status"] == "PARTIAL"
    state = transition(SCOPE, state, command("plan", PLAN), NOW)
    late = NOW + timedelta(days=1)
    assert monitor(state, late)["position"]["status"] == "EXIT_REQUESTED"
    assert monitor(state, late)["position"]["remaining_lots"] == 3
    with pytest.raises(PositionConflict):
        transition(SCOPE, state, command("fill", BUY), late)


def test_api_contract_retry_isolation_and_no_chart_fill() -> None:
    store = MemoryPositions()
    with api(store) as alice, api(store, "bob") as bob:
        alice.get("/api/v1/stocks/TEST/chart?interval=1m")
        assert alice.get("/api/v1/positions").json()["data"] == []
        first = alice.post("/api/v1/positions", json=OPEN, headers=HEADERS)
        assert first.status_code == 200, first.text
        validate("PositionResponse", first.json())
        pid = first.json()["data"]["position_id"]
        base = "/api/v1/positions/" + pid
        assert alice.post("/api/v1/positions", json=OPEN, headers=HEADERS).json() == first.json()
        assert (
            alice.post(
                "/api/v1/positions", json={**OPEN, "symbol": "BBCA"}, headers=HEADERS
            ).status_code
            == 409
        )
        assert len(alice.get("/api/v1/positions").json()["data"]) == 1
        assert bob.get(base).status_code == 404
        assert bob.get("/api/v1/positions").json()["data"] == []
        assert (
            alice.put(
                base + "/plan", json=PLAN, headers={**HEADERS, "Idempotency-Key": "plan"}
            ).status_code
            == 200
        )
        result = alice.get(base + "/monitor")
        validate("PositionMonitorResponse", result.json())
        assert (
            alice.post(
                base + "/exit-request",
                json={"reason": "STOP"},
                headers={**HEADERS, "Idempotency-Key": "stop"},
            ).status_code
            == 200
        )
        assert alice.get(base).json()["data"]["remaining_lots"] == 2
        assert (
            alice.post(
                base + "/fills",
                json={**BUY, "side": "SELL", "lots": 3},
                headers={**HEADERS, "Idempotency-Key": "oversell"},
            ).status_code
            == 409
        )
        assert alice.post("/api/v1/positions", json=OPEN).status_code == 403
        assert (
            alice.post(
                "/api/v1/positions", json=OPEN, headers={"Origin": HEADERS["Origin"]}
            ).status_code
            == 422
        )
        assert alice.get("/api/v1/positions?user_id=bob").status_code == 422
        alice.cookies.clear()
        assert alice.get("/api/v1/positions").status_code == 401


@pytest.mark.parametrize(
    "field,value",
    [
        ("lots", 0),
        ("lots", True),
        ("price_idr", "NaN"),
        ("fees_idr", "-1.00"),
        ("filled_at", "2026-12-01T00:00:00Z"),
        ("origin", "simulation"),
    ],
)
def test_invalid_fill_rejected(field: str, value: Any) -> None:
    with api(MemoryPositions()) as client:
        response = client.post(
            "/api/v1/positions", json={**OPEN, "fill": {**BUY, field: value}}, headers=HEADERS
        )
        assert response.status_code == 422


def test_postgres_restart_races_and_rls(database: tuple[str, str]) -> None:  # noqa: F811
    _, dsn = database
    store = PostgresPositions(dsn)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: store.execute(SCOPE, "same", command("open", OPEN), NOW), range(8))
        )
    assert all(result == results[0] for result in results)
    assert len(PostgresPositions(dsn).list(SCOPE)) == 1
    assert store.list(replace(SCOPE, account="bob")) == []
    with pytest.raises(ValueError, match="Database does not match repository mode"):
        store.list(replace(SCOPE, mode="paper"))
    pid = results[0]["position"]["position_id"]
    sell = {**BUY, "side": "SELL", "lots": 1}

    def exit_one(key: str) -> dict[str, Any]:
        return store.execute(SCOPE, key, command("fill", sell, pid), NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(exit_one, ["sell1", "sell2"]))
    assert store.list(SCOPE)[0]["position"]["status"] == "CLOSED"
    assert len(store.list(SCOPE)[0]["position"]["fills"]) == 3
    with pytest.raises(PositionConflict):
        store.execute(SCOPE, "sell3", command("fill", sell, pid), NOW)
    with psycopg.connect(dsn) as connection:
        connection.execute("SELECT set_config('ss.mode','research',true)")
        connection.execute("SELECT set_config('ss.user_id','bob',true)")
        assert connection.execute("SELECT count(*) FROM manual_position_events").fetchone() == (0,)
    with psycopg.connect(dsn) as connection, pytest.raises(psycopg.Error):
        connection.execute("DELETE FROM manual_position_events")


def test_fractional_cost_basis_is_not_rounded_per_partial_exit() -> None:
    state = transition(
        SCOPE,
        None,
        command(
            "open",
            {
                **OPEN,
                "fill": {**BUY, "lots": 3, "fees_idr": "0.01"},
            },
        ),
        NOW,
    )
    for _ in range(3):
        state = transition(
            SCOPE,
            state,
            command(
                "fill",
                {
                    **BUY,
                    "side": "SELL",
                    "lots": 1,
                    "fees_idr": "0.00",
                },
            ),
            NOW,
        )
    assert state["realized_pnl_idr"] == "-0.01"
    assert state["remaining_cost_idr"] == "0.00"


def test_database_failure_returns_unavailable() -> None:
    class Unavailable(MemoryPositions):
        def list(self, scope: MarketScope) -> list[dict[str, Any]]:
            raise psycopg.OperationalError("offline")

        def execute(
            self, scope: MarketScope, key: str, command: dict[str, Any], at: datetime
        ) -> dict[str, Any]:
            raise psycopg.OperationalError("offline")

    with api(Unavailable()) as client:
        assert client.get("/api/v1/positions").status_code == 503
        assert client.post("/api/v1/positions", json=OPEN, headers=HEADERS).status_code == 503


def test_command_replay_has_stable_entity_ids() -> None:
    cmd = command("open", OPEN)
    assert transition(SCOPE, None, cmd, NOW, "first") == transition(SCOPE, None, cmd, NOW, "first")
    assert (
        transition(SCOPE, None, cmd, NOW, "first")["position"]["position_id"]
        != transition(SCOPE, None, cmd, NOW, "second")["position"]["position_id"]
    )
