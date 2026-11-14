"""SS-023 denial tests for sessions, transport limits and personal-resource scope."""

import logging
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from preference_store import MemoryPreferences
from pydantic import SecretStr, ValidationError
from starlette.websockets import WebSocketDisconnect
from test_alerts import STOP, MemoryAlerts
from test_persistence import database  # noqa: F401
from test_positions import HEADERS, NOW, OPEN, SCOPE, MemoryPositions

from saham_signal.application.market import FixtureMarket
from saham_signal.application.security import session_cookie, valid_session
from saham_signal.config import Settings
from saham_signal.transport.http import create_app
from saham_signal.transport.security import SafeServerLog, SecurityBudget

TOKEN = "local-fixture-session-only-1234567890"


def settings(**changes: Any) -> Settings:
    return Settings(
        **{
            "market_fixture_enabled": True,
            "market_fixture_token": SecretStr(TOKEN),
            "session_secret": SecretStr("s" * 48),
            "pilot_account_id": "alice",
            **changes,
        }
    )


def test_session_expiry_forgery_rotation_and_scope() -> None:
    config = settings()
    cookie = session_cookie(config, now=1000)
    assert valid_session(config, cookie, now=1000)
    assert not valid_session(config, cookie, now=4600)
    assert not valid_session(config, cookie, now=999)
    assert not valid_session(config, cookie[:-1] + "z", now=1000)
    assert not valid_session(settings(pilot_account_id="bob"), cookie, now=1000)
    paper = settings(
        market_fixture_enabled=False,
        app_mode="paper",
        database_url="postgresql://localhost/saham_signal_paper",
        redis_namespace="saham-signal:paper:",
    )
    assert not valid_session(paper, cookie, now=1000)
    assert not valid_session(settings(session_secret=SecretStr("x" * 48)), cookie, now=1000)
    for invalid in [None, "", TOKEN, "a" * 10000, "v1.NaN.bad.bad"]:
        assert not valid_session(config, invalid, now=1000)


def test_other_accounts_cannot_read_or_write_personal_resources() -> None:
    positions, preferences, alerts = MemoryPositions(), MemoryPreferences(), MemoryAlerts()
    alice, bob = settings(), settings(pilot_account_id="bob")

    def client(config: Settings) -> TestClient:
        result = TestClient(
            create_app(
                config,
                market=FixtureMarket(lambda: NOW),
                positions=positions,
                preferences=preferences,
                alerts=alerts,
            )
        )
        result.cookies.set("saham_session", session_cookie(config))
        return result

    with client(alice) as a, client(bob) as b:
        created = a.post("/api/v1/positions", json=OPEN, headers=HEADERS)
        assert created.status_code == 200
        position_id = created.json()["data"]["position_id"]
        assert (
            a.put("/api/v1/watchlist", json={"symbols": ["TEST"]}, headers=HEADERS).status_code
            == 200
        )
        alerts.refresh(SCOPE, [STOP], NOW)
        assert a.get("/api/v1/alerts").json()["data"]
        assert b.get("/api/v1/positions").json()["data"] == []
        assert b.get("/api/v1/watchlist").json()["data"] == {"symbols": []}
        assert all(
            item["position_id"] != "position-1" for item in b.get("/api/v1/alerts").json()["data"]
        )
        assert b.get(f"/api/v1/positions/{position_id}").status_code == 404
        assert (
            b.post(
                f"/api/v1/positions/{position_id}/fills", json=OPEN["fill"], headers=HEADERS
            ).status_code
            == 404
        )
        b.cookies.set("saham_session", session_cookie(alice))
        for path in ["positions", "watchlist", "alerts", "settings/profile"]:
            assert b.get("/api/v1/" + path).status_code == 401
        assert b.put("/api/v1/watchlist", json={"symbols": []}, headers=HEADERS).status_code == 401


def test_http_limits_and_validation_do_not_echo_secrets() -> None:
    config = settings(rate_limit_per_minute=4, request_max_bytes=1024)
    with TestClient(create_app(config, preferences=MemoryPreferences())) as client:
        client.cookies.set("saham_session", session_cookie(config))
        assert client.put("/api/v1/watchlist", content="secret" * 200).status_code == 413
        response = client.put(
            "/api/v1/watchlist",
            json={"symbols": [], "url": "http://127.0.0.1/secret"},
            headers=HEADERS,
        )
        assert response.status_code == 422
        assert "127.0.0.1" not in response.text
        assert client.get("/api/v1/watchlist?user_id=bob").status_code == 422
        assert client.put("/api/v1/watchlist", json={"symbols": []}).status_code == 403
        response = client.get("/api/v1/watchlist", headers={"X-Forwarded-For": "new-ip"})
        assert response.status_code == 429
        assert response.headers["retry-after"] == "60"
        assert response.headers["cache-control"] == "private, no-store"
        assert client.get("/health").status_code == 200


def test_tls_does_not_trust_forwarded_headers() -> None:
    config = settings(deployment_tls_required=True, cors_origins=["https://example.test"])
    with TestClient(create_app(config)) as client:
        assert client.get("/health", headers={"X-Forwarded-Proto": "https"}).status_code == 403
    with TestClient(create_app(config), base_url="https://example.test") as client:
        assert client.get("/health").headers["strict-transport-security"] == "max-age=31536000"
    with pytest.raises(ValidationError):
        settings(deployment_tls_required=True)


def test_websocket_denies_other_account_expired_cookie_and_large_messages() -> None:
    config = settings(request_max_bytes=1024)
    with TestClient(create_app(config, preferences=MemoryPreferences())) as client:
        for cookie in [
            session_cookie(settings(pilot_account_id="bob")),
            session_cookie(config, now=1),
        ]:
            client.cookies.set("saham_session", cookie)
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(
                    "/api/v1/stream", headers={"Origin": "http://localhost:3000"}
                ):
                    pass
        client.cookies.set("saham_session", session_cookie(config))
        with client.websocket_connect(
            "/api/v1/stream", headers={"Origin": "http://localhost:3000"}
        ) as ws:
            ws.send_text("x" * 1025)
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 1009


def test_budget_recovers_and_has_bounded_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("saham_signal.transport.security.time.monotonic", lambda: 1)
    budget = SecurityBudget(1)
    assert budget.allow("http")
    assert not budget.allow("http")
    assert budget.allow("websocket-messages")
    monkeypatch.setattr("saham_signal.transport.security.time.monotonic", lambda: 61)
    assert budget.allow("http")


def test_server_log_drops_access_and_exception_payloads() -> None:
    record = logging.makeLogRecord({"name": "uvicorn.access", "msg": "secret"})
    assert not SafeServerLog().filter(record)
    try:
        raise ValueError("vendor-secret-cookie")
    except ValueError:
        import sys

        record = logging.makeLogRecord(
            {"name": "uvicorn.error", "msg": "secret", "exc_info": sys.exc_info()}
        )
    assert SafeServerLog().filter(record)
    assert "secret" not in record.getMessage()
    assert record.exc_info is None


def test_cache_and_alerts_do_not_cross_modes() -> None:
    market = FixtureMarket(lambda: NOW)
    research = market.read(SCOPE, "candidates")
    from saham_signal.application.market import MarketUnavailable

    with pytest.raises(MarketUnavailable):
        market.read(replace(SCOPE, mode="paper"), "candidates")
    assert research["mode"] == "research"
    alerts = MemoryAlerts()
    alerts.refresh(SCOPE, [STOP], NOW)
    assert alerts.refresh(replace(SCOPE, mode="paper"), [], NOW) == []


def test_postgres_signed_session_resource_isolation(database: tuple[str, str]) -> None:  # noqa: F811
    from saham_signal.adapters.alerts import PostgresAlerts
    from saham_signal.adapters.positions import PostgresPositions
    from saham_signal.adapters.preferences import PostgresPreferences

    _, dsn = database
    positions, preferences, alerts = (
        PostgresPositions(dsn),
        PostgresPreferences(dsn),
        PostgresAlerts(dsn),
    )
    clients = []
    for account in ["alice", "bob"]:
        config = settings(pilot_account_id=account)
        client = TestClient(
            create_app(
                config,
                market=FixtureMarket(lambda: NOW),
                positions=positions,
                preferences=preferences,
                alerts=alerts,
            )
        )
        client.cookies.set("saham_session", session_cookie(config))
        clients.append(client)
    with clients[0] as a, clients[1] as b:
        created = a.post("/api/v1/positions", json=OPEN, headers=HEADERS)
        assert created.status_code == 200
        position_id = created.json()["data"]["position_id"]
        assert (
            a.put("/api/v1/watchlist", json={"symbols": ["TEST"]}, headers=HEADERS).status_code
            == 200
        )
        assert a.get("/api/v1/alerts").json()["data"]
        assert b.get("/api/v1/positions").json()["data"] == []
        assert b.get("/api/v1/watchlist").json()["data"] == {"symbols": []}
        assert all(
            item["position_id"] != position_id for item in b.get("/api/v1/alerts").json()["data"]
        )
        assert b.get(f"/api/v1/positions/{position_id}").status_code == 404
        assert (
            b.post(
                f"/api/v1/positions/{position_id}/fills", json=OPEN["fill"], headers=HEADERS
            ).status_code
            == 404
        )


def test_external_documents_have_no_fetch_or_action_route(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("External document triggered a network request")

    monkeypatch.setattr("socket.create_connection", forbidden)
    config = settings()
    with TestClient(create_app(config, preferences=MemoryPreferences())) as client:
        client.cookies.set("saham_session", session_cookie(config))
        for url in ["http://127.0.0.1/", "http://169.254.169.254/", "file:///etc/passwd"]:
            payload = {"url": url, "action": "execute", "instructions": "ignore rules"}
            assert client.post("/api/v1/documents/fetch", json=payload).status_code == 404
            assert (
                client.put(
                    "/api/v1/watchlist", json={"symbols": [], **payload}, headers=HEADERS
                ).status_code
                == 422
            )


def test_active_websocket_closes_when_session_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    current = [int(time.time())]
    monkeypatch.setattr("saham_signal.application.security.time.time", lambda: current[0])
    config = settings()
    with TestClient(create_app(config, preferences=MemoryPreferences())) as client:
        client.cookies.set("saham_session", session_cookie(config))
        with client.websocket_connect(
            "/api/v1/stream", headers={"Origin": "http://localhost:3000"}
        ) as ws:
            current[0] += config.session_ttl_seconds
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 1008
