"""Scenario math, exclusion and backwards-compatible snapshot integrity."""

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_eod import NOW, row, source

from saham_signal.application.eod import Snapshot, import_csv, read_snapshot
from saham_signal.application.screener import screen
from saham_signal.application.security import session_cookie
from saham_signal.config import Settings
from saham_signal.domain.persistence import digest
from saham_signal.transport.http import create_app


def data(tmp_path: Path) -> dict[str, Any]:
    snapshot = import_csv(
        source(
            tmp_path,
            [
                row(
                    close="1100",
                    value_idr="110000",
                    rsi_14="60",
                    sma_20="1070",
                    sma_50="1000",
                    sma_200="900",
                    ret_20d="0.12",
                    avg_value_20d_idr="2000000000",
                ),
                row(
                    ticker="BEAR",
                    close="900",
                    value_idr="90000",
                    rsi_14="40",
                    sma_20="930",
                    sma_50="1000",
                    sma_200="1100",
                    ret_20d="-0.12",
                    avg_value_20d_idr="2000000000",
                ),
            ],
        ),
        NOW,
    )
    path = tmp_path / "snapshot.json"
    path.write_text(snapshot.model_dump_json())
    return read_snapshot(path, NOW)


def test_bull_bear_targets_are_directional_rounded_and_at_least_2r(tmp_path: Path) -> None:
    result = screen(data(tmp_path))
    bear, bull = result["rows"]
    assert bull["direction"] == "bullish" and bull["symbol"] == "SIM"
    assert bear["direction"] == "bearish"
    assert float(bull["take_profit"]) > 1100 > float(bull["stop_loss"])
    assert float(bear["take_profit"]) < 900 < float(bear["stop_loss"])
    for candidate in result["rows"]:
        assert float(candidate["reward_risk"]) >= 2
        assert 1 <= float(candidate["risk_pct"]) <= 10
        assert float(candidate["take_profit"]) % 5 == 0


@pytest.mark.parametrize(
    "condition",
    ["stale", "lagging", "missing", "illiquid", "neutral", "zero-volume", "wide-stop", "malformed"],
)
def test_unreliable_or_unconfirmed_rows_never_become_candidates(
    tmp_path: Path, condition: str
) -> None:
    snapshot = deepcopy(data(tmp_path))
    snapshot["rows"] = [snapshot["rows"][1]]
    candidate = snapshot["rows"][0]
    if condition == "stale":
        snapshot["stale"] = True
    elif condition == "lagging":
        candidate["date"] = "2026-11-12"
    elif condition == "missing":
        candidate["technical"] = None
    elif condition == "illiquid":
        candidate["technical"]["avg_value_20d_idr"] = "100"
    elif condition == "neutral":
        candidate["rsi_14"] = "80"
    elif condition == "zero-volume":
        candidate["volume"] = "0"
    elif condition == "wide-stop":
        candidate["technical"]["sma_20"] = "100"
    else:
        candidate["technical"]["sma_20"] = "NaN"
    assert screen(snapshot)["rows"] == []


def test_old_sealed_snapshot_still_loads_but_requires_reimport(tmp_path: Path) -> None:
    snapshot = data(tmp_path)
    for key in ("stale", "as_of"):
        snapshot.pop(key)
    for candidate in snapshot["rows"]:
        candidate.pop("stale")
        candidate.pop("technical")
        candidate.pop("history")
        candidate.pop("backtest")
    snapshot.pop("sha256")
    snapshot["sha256"] = digest(snapshot)
    assert Snapshot.model_validate(snapshot)
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(snapshot))
    result = screen(read_snapshot(path, NOW))
    assert result["needs_reimport"] and not result["rows"]


def test_screener_api_auth_query_and_unavailable_source(tmp_path: Path) -> None:
    data(tmp_path)
    path = tmp_path / "snapshot.json"
    config = Settings(
        session_secret=SecretStr("screener-research-test-secret-12345678901234567890"),
        pilot_account_id="research-test",
        eod_snapshot_path=path,
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/api/research/screener").status_code == 401
        client.cookies.set("saham_session", session_cookie(config))
        response = client.get("/api/research/screener")
        assert response.status_code == 200
        assert response.json()["method"] == "ma-rsi-momentum-2r-v1"
        assert response.headers["cache-control"] == "private, no-store"
        assert client.get("/api/research/screener?path=private.csv").status_code == 422
        path.unlink()
        assert client.get("/api/research/screener").status_code == 503


def test_research_session_exchange_validates_token_origin_and_cookie(tmp_path: Path) -> None:
    data(tmp_path)
    config = Settings(
        session_secret=SecretStr("research-session-test-secret-12345678901234567890"),
        pilot_account_id="research-test",
        eod_snapshot_path=tmp_path / "snapshot.json",
    )
    headers = {"Origin": config.cors_origins[0]}
    token = session_cookie(config)
    with TestClient(create_app(config)) as client:
        endpoint = "/api/research/session"
        assert client.post(endpoint, json={"token": token}).status_code == 403
        assert client.post(
            endpoint, json={"token": token}, headers={"Origin": "https://foreign.invalid"}
        ).status_code == 403
        for invalid in ("invalid", token[:-1], session_cookie(config, now=int(time.time()) - 3601)):
            response = client.post(endpoint, json={"token": invalid}, headers=headers)
            assert response.status_code == 401
            assert "set-cookie" not in response.headers
            assert invalid not in response.text
        response = client.post(endpoint, json={"token": token}, headers=headers)
        assert response.status_code == 204 and not response.content
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
        assert "Secure" not in cookie
        assert response.headers["cache-control"] == "private, no-store"
        assert client.get("/api/research/screener").status_code == 200


def test_research_session_does_not_accept_fixture_token() -> None:
    config = Settings(market_fixture_token=SecretStr("test-fixture-token"))
    with TestClient(create_app(config)) as client:
        response = client.post(
            "/api/research/session",
            json={"token": "test-fixture-token"},
            headers={"Origin": config.cors_origins[0]},
        )
        assert response.status_code == 401
        assert "set-cookie" not in response.headers


def test_research_session_uses_secure_cookie_on_tls() -> None:
    config = Settings(
        session_secret=SecretStr("research-tls-test-secret-12345678901234567890"),
        pilot_account_id="research-test",
        deployment_tls_required=True,
        cors_origins=["https://research.example"],
    )
    with TestClient(create_app(config), base_url="https://research.example") as client:
        response = client.post(
            "/api/research/session",
            json={"token": session_cookie(config)},
            headers={"Origin": "https://research.example"},
        )
        assert response.status_code == 204
        assert "Secure" in response.headers["set-cookie"]
        assert "HttpOnly" in response.headers["set-cookie"]
