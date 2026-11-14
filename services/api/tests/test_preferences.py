"""SS-020 acceptance: contract validation, persistence, isolation and recalculation."""

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from preference_store import MemoryPreferences
from pydantic import SecretStr
from test_persistence import database  # noqa: F401 -- shared disposable PostgreSQL fixture

from saham_signal.adapters.preferences import PostgresPreferences
from saham_signal.application.market import FixtureMarket, MarketScope, validate
from saham_signal.application.preferences import PreferenceConflict
from saham_signal.config import Settings
from saham_signal.transport.http import create_app

TOKEN = "preferences-test-session-1234567890"
ORIGIN = {"Origin": "http://localhost:3000", "Idempotency-Key": "first"}
NOW = datetime(2026, 11, 14, 3, tzinfo=UTC)


def settings(version: str = "config-1") -> dict[str, Any]:
    return {
        "configuration_version": version,
        "nominal_idr": "1000000.00",
        "capital_idr": "10000000.00",
        "risk_per_position_ratio": "0.005000",
        "max_combined_risk_ratio": "0.020000",
        "max_positions": 3,
        "fee_schedule_version": "fee-assumption-1",
        "fee_schedule": {
            "version": "fee-assumption-1",
            "buy_ratio": "0.001500",
            "sell_ratio": "0.002500",
            "effective_from": "2026-11-01T00:00:00Z",
            "effective_to": "2026-12-01T00:00:00Z",
            "source": "User test input, not broker verification",
            "verification": "user_assumption",
        },
    }


def client(store: MemoryPreferences, account: str = "alice") -> TestClient:
    config = Settings(
        market_fixture_enabled=True, market_fixture_token=SecretStr(TOKEN), pilot_account_id=account
    )
    result = TestClient(create_app(config, market=FixtureMarket(lambda: NOW), preferences=store))
    result.cookies.set("saham_session", TOKEN)
    return result


def test_account_isolation_and_session_ownership() -> None:
    store = MemoryPreferences()
    with client(store) as alice, client(store, "bob") as bob:
        assert alice.get("/api/v1/settings/profile").status_code == 404
        response = alice.put(
            "/api/v1/watchlist", json={"symbols": ["TEST", "BBCA"]}, headers=ORIGIN
        )
        assert response.status_code == 200
        validate("WatchlistResponse", response.json())
        assert bob.get("/api/v1/watchlist").json()["data"]["symbols"] == []
        assert alice.get("/api/v1/watchlist").json()["data"]["symbols"] == ["TEST", "BBCA"]
        assert alice.get("/api/v1/watchlist?account=bob").status_code == 422
        assert (
            alice.put(
                "/api/v1/watchlist", json={"symbols": [], "user_id": "bob"}, headers=ORIGIN
            ).status_code
            == 422
        )
        assert alice.put("/api/v1/watchlist", json={"symbols": []}).status_code == 403
        assert (
            alice.put(
                "/api/v1/watchlist",
                json={"symbols": []},
                headers={**ORIGIN, "Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        assert (
            alice.put(
                "/api/v1/watchlist", json={"symbols": []}, headers={"Origin": ORIGIN["Origin"]}
            ).status_code
            == 422
        )
        bob.cookies.clear()
        assert bob.get("/api/v1/watchlist").status_code == 401


@pytest.mark.parametrize(
    "field,value",
    [
        ("nominal_idr", "0.00"),
        ("nominal_idr", "-1.00"),
        ("nominal_idr", "NaN"),
        ("nominal_idr", 1000),
        ("nominal_idr", "10000001.00"),
        ("capital_idr", "0.00"),
        ("risk_per_position_ratio", "0.000000"),
        ("risk_per_position_ratio", "0.010001"),
        ("max_combined_risk_ratio", "0.004000"),
        ("max_combined_risk_ratio", "0.020001"),
        ("max_positions", 0),
        ("max_positions", 4),
        ("max_positions", True),
        ("fee_schedule_version", "unknown"),
        ("fee_schedule", None),
    ],
)
def test_invalid_settings_rejected(field: str, value: Any) -> None:
    data = settings()
    data[field] = value
    with client(MemoryPreferences()) as api:
        response = api.put("/api/v1/settings/profile", json=data, headers=ORIGIN)
        assert response.status_code == 422, response.text
        validate("ErrorResponse", response.json())


@pytest.mark.parametrize(
    "field,value",
    [
        ("buy_ratio", "-0.001000"),
        ("sell_ratio", "1.000001"),
        ("buy_ratio", "0.001"),
        ("effective_to", "2026-11-01T00:00:00Z"),
        ("effective_from", "invalid"),
        ("source", " "),
        ("verification", "verified"),
    ],
)
def test_invalid_fee_assumptions_rejected(field: str, value: Any) -> None:
    data = settings()
    data["fee_schedule"][field] = value
    with client(MemoryPreferences()) as api:
        assert api.put("/api/v1/settings/profile", json=data, headers=ORIGIN).status_code == 422


@pytest.mark.parametrize("symbols", [["test"], ["TEST", "TEST"], ["A"] * 201, ["../TEST"]])
def test_invalid_watchlist_rejected(symbols: list[str]) -> None:
    with client(MemoryPreferences()) as api:
        assert (
            api.put("/api/v1/watchlist", json={"symbols": symbols}, headers=ORIGIN).status_code
            == 422
        )


def test_recalculation_cache_isolation_idempotency_and_fee_expiry() -> None:
    store = MemoryPreferences()
    with client(store) as api, client(store, "bob") as bob:
        before = api.get("/api/v1/candidates").json()
        response = api.put("/api/v1/settings/profile", json=settings(), headers=ORIGIN)
        assert response.status_code == 200, response.text
        validate("RiskProfileResponse", response.json())
        first = api.get("/api/v1/settings/eligibility").json()
        validate("SettingsEligibilityResponse", first)
        assert first["data"]["budget_lots_ceiling"] == 9
        assert first["data"]["eligible_lots"] == 0
        changed = settings("config-2")
        changed["nominal_idr"] = "200000.00"
        assert (
            api.put(
                "/api/v1/settings/profile",
                json=changed,
                headers={**ORIGIN, "Idempotency-Key": "second"},
            ).status_code
            == 200
        )
        assert api.get("/api/v1/settings/eligibility").json()["data"]["budget_lots_ceiling"] == 1
        result = api.get("/api/v1/candidates").json()
        assert result["data"][0]["configuration_version"] == "config-2"
        assert result["data"][0]["assumptions"]["nominal_idr"] == "200000.00"
        assert result["data"][0]["assumptions"]["fee_schedule_version"] == "fee-assumption-1"
        assert result["data"][0]["state"] == "WATCH"
        assert bob.get("/api/v1/candidates").json() == before
        # A delayed retry returns its original snapshot without reverting newer state.
        assert (
            api.put("/api/v1/settings/profile", json=settings(), headers=ORIGIN).status_code == 200
        )
        assert api.get("/api/v1/settings/profile").json()["data"] == changed
        assert api.put("/api/v1/settings/profile", json=changed, headers=ORIGIN).status_code == 409
        expired = settings("config-3")
        expired["fee_schedule_version"] = expired["fee_schedule"]["version"] = "expired-fees"
        expired["fee_schedule"]["effective_to"] = "2026-11-02T00:00:00Z"
        assert (
            api.put(
                "/api/v1/settings/profile",
                json=expired,
                headers={**ORIGIN, "Idempotency-Key": "third"},
            ).status_code
            == 200
        )
        evaluation = api.get("/api/v1/settings/eligibility").json()["data"]
        assert evaluation["budget_lots_ceiling"] == 0
        assert evaluation["reason"] == "FEE_SCHEDULE_EXPIRED"


def test_postgres_restart_scope_versions_and_append_only(database: tuple[str, str]) -> None:  # noqa: F811
    _, dsn = database
    store = PostgresPreferences(dsn)
    scope = MarketScope("alice", "research", "1000000.00", 30)
    store.put(scope, "Watchlist", "wl-1", {"symbols": ["TEST"]})
    store.put(scope, "RiskSettings", "risk-1", settings())
    fresh = PostgresPreferences(dsn)
    assert fresh.get(scope, "Watchlist") == {"symbols": ["TEST"]}
    assert fresh.get(replace(scope, account="bob"), "Watchlist") is None
    assert fresh.get(scope, "RiskSettings") == settings()
    assert fresh.put(scope, "RiskSettings", "risk-1", settings()) == settings()
    changed = settings("config-2")
    changed["fee_schedule"]["buy_ratio"] = "0.002000"
    with pytest.raises(PreferenceConflict):
        fresh.put(scope, "RiskSettings", "risk-2", changed)
    with pytest.raises(PreferenceConflict):
        fresh.put(scope, "Watchlist", "wl-1", {"symbols": []})
    with psycopg.connect(dsn) as connection:
        connection.execute("SELECT set_config('ss.mode','research',true)")
        connection.execute("SELECT set_config('ss.user_id','bob',true)")
        assert connection.execute("SELECT count(*) FROM personal_preferences").fetchone() == (0,)
    with psycopg.connect(dsn) as connection, pytest.raises(psycopg.Error):
        connection.execute("DELETE FROM personal_preferences")


def test_fee_budget_reacts_to_risk_fee_and_time() -> None:
    from saham_signal.application.preferences import eligibility

    data = settings()
    first = eligibility(data, NOW)
    risk = deepcopy(data)
    risk["risk_per_position_ratio"] = "0.000100"
    assert eligibility(risk, NOW)["budget_lots_ceiling"] == 0
    fee = deepcopy(data)
    fee["fee_schedule"]["buy_ratio"] = "0.100000"
    assert eligibility(fee, NOW)["budget_lots_ceiling"] < first["budget_lots_ceiling"]
    assert eligibility(data, NOW + timedelta(days=40))["budget_lots_ceiling"] == 0


def test_legacy_risk_contract_stays_unchanged_and_reuses_known_fees() -> None:
    with client(MemoryPreferences()) as api:
        assert (
            api.put("/api/v1/settings/profile", json=settings(), headers=ORIGIN).status_code == 200
        )
        legacy = api.get("/api/v1/settings/risk").json()
        validate("RiskSettingsResponse", legacy)
        assert "fee_schedule" not in legacy["data"]
        payload = legacy["data"]
        payload["configuration_version"] = "legacy-config-2"
        payload["nominal_idr"] = "200000.00"
        response = api.put(
            "/api/v1/settings/risk",
            json=payload,
            headers={**ORIGIN, "Idempotency-Key": "legacy-save"},
        )
        assert response.status_code == 200
        validate("RiskSettingsResponse", response.json())
        assert "fee_schedule" not in response.json()["data"]
        profile = api.get("/api/v1/settings/profile").json()["data"]
        assert profile["fee_schedule"] == settings()["fee_schedule"]
        assert profile["nominal_idr"] == "200000.00"


def test_database_failure_does_not_serve_cached_personal_state() -> None:
    class Unavailable(MemoryPreferences):
        def get(self, scope: MarketScope, kind: str) -> dict[str, Any] | None:
            raise psycopg.OperationalError("unavailable")

    with client(Unavailable()) as api:
        for path in ["/watchlist", "/settings/profile", "/settings/eligibility", "/candidates"]:
            response = api.get("/api/v1" + path)
            assert response.status_code == 503
            validate("ErrorResponse", response.json())
