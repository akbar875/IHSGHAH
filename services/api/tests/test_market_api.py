from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from preference_store import MemoryPreferences
from pydantic import SecretStr, ValidationError
from starlette.websockets import WebSocketDisconnect

from saham_signal.application.market import FixtureMarket, MarketScope, MarketUnavailable, validate
from saham_signal.config import Settings
from saham_signal.transport.http import create_app

TOKEN = "local-fixture-session-only-1234567890"
ORIGIN = {"Origin": "http://localhost:3000"}


class Clock:
    now = datetime(2026, 11, 13, 3, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, FixtureMarket, Clock]]:
    clock = Clock()
    market = FixtureMarket(clock)
    config = Settings(market_fixture_enabled=True, market_fixture_token=SecretStr(TOKEN))
    with TestClient(
        create_app(config, market=market, preferences=MemoryPreferences()),
        raise_server_exceptions=False,
    ) as client:
        client.cookies.set("saham_session", TOKEN)
        yield client, market, clock


@pytest.mark.parametrize(
    ("path", "schema"),
    [
        ("/candidates", "CandidatesResponse"),
        ("/stocks/TEST", "StockDetailResponse"),
        ("/stocks/TEST/depth", "DepthResponse"),
        ("/stocks/TEST/chart?interval=1m", "ChartResponse"),
        ("/stocks/TEST/signals", "SignalHistoryResponse"),
    ],
)
def test_reads_match_canonical_contract(
    setup: tuple[TestClient, FixtureMarket, Clock], path: str, schema: str
) -> None:
    client, _, _ = setup
    response = client.get("/api/v1" + path)
    assert response.status_code == 200, response.text
    validate(schema, response.json())
    assert response.json()["mode"] == "research"
    assert response.json()["data_origin"] == "simulation"
    assert response.json()["quality"]["status"] == "unavailable"
    assert response.headers["cache-control"] == "private, no-store"
    assert "Cookie" in response.headers["vary"].split(", ")


def test_missing_predictions_and_intervals_are_not_invented(
    setup: tuple[TestClient, FixtureMarket, Clock],
) -> None:
    client, _, _ = setup
    detail = client.get("/api/v1/stocks/TEST").json()["data"]
    assert detail["liquidity"] is None
    assert detail["signal"]["target_probability"]["value"] is None
    assert detail["signal"]["return_quantiles"] is None
    assert detail["pressure"][0]["buy_ratio"] is None
    for interval in ["1m", "5m", "15m"]:
        response = client.get(f"/api/v1/stocks/TEST/chart?interval={interval}")
        validate("ChartResponse", response.json())
        chart = response.json()["data"]
        assert chart["projection"] == []
        assert chart["model_version"] is None
        if interval != "1m":
            assert chart["candles"] == []


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/stocks/UNKNOWN", 404),
        ("/stocks/UNKNOWN/depth", 404),
        ("/stocks/TEST/chart?interval=1h", 422),
        ("/stocks/TEST/chart", 422),
        ("/candidates?account=other", 422),
        ("/candidates?mode=live", 422),
        ("/candidates?nominal_idr=0.00", 422),
        ("/candidates?nominal_idr=NaN", 422),
        ("/candidates?nominal_idr=-1.00", 422),
        ("/candidates?nominal_idr=2000000", 422),
        ("/candidates?nominal_idr=1.001", 422),
        ("/candidates?nominal_idr=10000000000000000.00", 422),
        ("/candidates?nominal_idr=1.00&nominal_idr=2.00", 422),
        ("/stocks/TEST?nominal_idr=2000000.00", 422),
    ],
)
def test_safe_query_errors(
    setup: tuple[TestClient, FixtureMarket, Clock], path: str, status: int
) -> None:
    response = setup[0].get("/api/v1" + path)
    assert response.status_code == status
    validate("ErrorResponse", response.json())


def test_fixture_requires_opt_in_and_valid_session(
    setup: tuple[TestClient, FixtureMarket, Clock],
) -> None:
    with TestClient(create_app(Settings())) as default:
        assert default.get("/api/v1/candidates").status_code == 503
    client, _, _ = setup
    client.cookies.clear()
    assert client.get("/api/v1/candidates").status_code == 401
    client.cookies.set("saham_session", "forged")
    assert client.get("/api/v1/candidates").status_code == 401
    with pytest.raises(ValidationError):
        Settings(market_fixture_enabled=True)
    with pytest.raises(ValidationError):
        Settings(market_fixture_enabled=True, market_fixture_token=SecretStr("short"))
    with pytest.raises(ValidationError):
        Settings(market_horizon_minutes=42)


def test_candidate_nominal_requests_are_isolated(
    setup: tuple[TestClient, FixtureMarket, Clock],
) -> None:
    client, _, _ = setup
    for nominal in ["1000000.00", "2500000.00", "0.01", "9999999999999999.99", "1000000.00"]:
        response = client.get("/api/v1/candidates", params={"nominal_idr": nominal})
        assert response.status_code == 200
        body = response.json()
        validate("CandidatesResponse", body)
        assert body["data"][0]["assumptions"]["nominal_idr"] == nominal
        assert body["data"][0]["target_probability"]["value"] is None
        assert body["data"][0]["state"] == "WATCH"
    default = client.get("/api/v1/candidates").json()
    assert default["data"][0]["assumptions"]["nominal_idr"] == "1000000.00"


def test_cache_isolation_copy_bounds_and_expiry() -> None:
    clock = Clock()
    market = FixtureMarket(clock)
    a = MarketScope("a", "research", "1000000.00", 15)
    b = MarketScope("b", "research", "2000000.00", 30, "config-b")
    before = market.read(a, "candidates")
    before["data"].clear()
    assert market.read(a, "candidates")["data"]
    other = market.read(b, "candidates")["data"][0]
    assert other["assumptions"]["nominal_idr"] == "2000000.00"
    assert other["configuration_version"] == "config-b"
    with pytest.raises(MarketUnavailable):
        market.read(MarketScope("a", "live", "1000000.00", 15), "candidates")
    with pytest.raises(MarketUnavailable):
        market.read(MarketScope("a", "paper", "1000000.00", 15), "candidates")
    clock.now += timedelta(minutes=15)
    assert market.read(a, "candidates")["data"] == []
    assert market.read(b, "candidates")["data"]
    history = market.read(a, "history", "TEST")["data"]
    assert [(s["version"], s["state"]) for s in history] == [(1, "WATCH"), (2, "EXPIRED")]
    assert history[1]["generated_at"] == history[0]["valid_until"]
    assert market.read(a, "detail", "TEST")["data"]["signal"] == history[1]
    for n in range(150):
        market.read(MarketScope(f"a{n}", "research", "1000000.00", 15), "candidates")
    assert len(market.cache) == 128


def subscribe(**overrides: Any) -> dict[str, Any]:
    return {
        "kind": "subscribe",
        "contract_version": "1.0.0",
        "subscription_id": "test-sub",
        "topic": "signals",
        "symbol": None,
        "resume_cursor": None,
        **overrides,
    }


def test_stream_snapshot_expiry_delta_and_reconnect(
    setup: tuple[TestClient, FixtureMarket, Clock],
) -> None:
    client, _, clock = setup
    with client.websocket_connect("/api/v1/stream", headers=ORIGIN) as ws:
        ws.send_json(subscribe())
        snapshot = ws.receive_json()
        validate("Snapshot", snapshot)
        assert snapshot["user_id"] == "fixture-pilot"
        assert snapshot["sequence"] == "1"
        clock.now += timedelta(minutes=30)
        delta = ws.receive_json()
        validate("Delta", delta)
        assert delta["previous_sequence"] == "1" and delta["sequence"] == "2"
        assert delta["stream_id"] == snapshot["stream_id"]
        assert delta["operations"] == [{"op": "remove", "entity_id": "signal-sim-1"}]
    with client.websocket_connect("/api/v1/stream", headers=ORIGIN) as ws:
        ws.send_json(subscribe(resume_cursor=delta["cursor"]))
        error = ws.receive_json()
        validate("ErrorResponse", error)
        assert error["data"]["code"] == "RESYNC_REQUIRED"
        ws.send_json(subscribe())
        fresh = ws.receive_json()
        validate("Snapshot", fresh)
        assert fresh["stream_id"] != snapshot["stream_id"]
        assert fresh["sequence"] == "1" and fresh["items"] == []


def test_stream_depth_errors_and_independent_subscriptions(
    setup: tuple[TestClient, FixtureMarket, Clock],
) -> None:
    client, _, _ = setup
    with client.websocket_connect("/api/v1/stream", headers=ORIGIN) as ws:
        for message in [None, {}, subscribe(user_id="other"), subscribe(topic="depth")]:
            ws.send_json(message)
            error = ws.receive_json()
            validate("ErrorResponse", error)
            assert error["data"]["code"] == "INVALID_REQUEST"
        ws.send_text("not-json")
        assert ws.receive_json()["data"]["code"] == "INVALID_REQUEST"
        ws.send_json(subscribe(topic="positions"))
        assert ws.receive_json()["data"]["code"] == "DATA_UNAVAILABLE"
        ws.send_json(subscribe(topic="depth", symbol="UNKNOWN"))
        assert ws.receive_json()["data"]["code"] == "NOT_FOUND"
        for n in range(8):
            ws.send_json(subscribe(topic="depth", symbol="TEST", subscription_id=f"depth-{n}"))
            snapshot = ws.receive_json()
            validate("Snapshot", snapshot)
            assert snapshot["items"][0]["symbol"] == "TEST"
            assert len(snapshot["items"]) == 1
        ws.send_json(subscribe(subscription_id="overflow"))
        assert ws.receive_json()["data"]["code"] == "RATE_LIMITED"


def test_stream_checks_session_origin_and_query_before_upgrade(
    setup: tuple[TestClient, FixtureMarket, Clock],
) -> None:
    client, _, _ = setup
    for headers in [{}, {"Origin": "https://untrusted.example"}]:
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/api/v1/stream", headers=headers),
        ):
            pass
    client.cookies.clear()
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/v1/stream", headers=ORIGIN),
    ):
        pass


def test_internal_fields_are_rejected_and_never_leaked(
    setup: tuple[TestClient, FixtureMarket, Clock],
) -> None:
    client, market, _ = setup
    market.fixture["CandidatesResponse"]["data"][0]["news"] = {"source_ref": "SECRET-INTERNAL"}
    response = client.get("/api/v1/candidates")
    assert response.status_code == 500
    validate("ErrorResponse", response.json())
    assert "SECRET-INTERNAL" not in response.text
    assert "news" not in response.text
    # The shipped public fixture contains only the five allowlisted response types.
    assert set(market.fixture) == {
        "CandidatesResponse",
        "StockDetailResponse",
        "DepthResponse",
        "ChartResponse",
        "SignalHistoryResponse",
    }
