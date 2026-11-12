import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from saham_signal.application.readiness import DependencyProbe, check_dependencies
from saham_signal.config import Settings
from saham_signal.transport.http import create_app

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "packages/contracts/v1/schema.json").read_text())
ERROR = Draft202012Validator(
    {"$ref": "#/$defs/ErrorResponse", "$defs": SCHEMA["$defs"]}, format_checker=FormatChecker()
)


class Probe:
    def __init__(self, fails: bool = False, slow: bool = False) -> None:
        self.fails = fails
        self.slow = slow

    async def check(self) -> None:
        if self.slow:
            await asyncio.sleep(10)
        if self.fails:
            raise RuntimeError("secret-dsn-must-never-leak")


def probes(*, fails: bool = False, slow: bool = False) -> dict[str, DependencyProbe]:
    return {"postgresql": Probe(fails, slow), "redis": Probe()}


def test_health_and_readiness() -> None:
    with TestClient(create_app(Settings(), probes())) as client:
        assert client.get("/health").json() == {"status": "ok", "mode": "research"}
        assert client.get("/ready").json() == {
            "status": "ready",
            "mode": "research",
            "dependencies": {"postgresql": True, "redis": True},
        }


@pytest.mark.parametrize("slow", [False, True])
def test_dependency_failure_and_timeout_do_not_kill_health(slow: bool) -> None:
    app = create_app(Settings(readiness_timeout_seconds=0.1), probes(fails=True, slow=slow))
    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        ERROR.validate(response.json())
        assert response.json()["data"]["code"] == "DATA_UNAVAILABLE"
        assert response.json()["data"]["retryable"] is True
        assert "secret-dsn" not in response.text
        assert response.headers["x-request-id"] == response.json()["data"]["request_id"]
        assert response.headers["retry-after"] == "3"
        assert client.get("/health").status_code == 200


def test_readiness_requires_lifespan_and_both_probes() -> None:
    client = TestClient(create_app(Settings(), probes()))
    assert client.get("/ready").status_code == 503
    with pytest.raises(ValueError):
        create_app(Settings(), {})


def test_error_contract_and_cors() -> None:
    with TestClient(create_app(Settings(), probes())) as client:
        headers = {"Origin": "http://localhost:3000"}
        response = client.get("/missing", headers=headers)
        assert response.status_code == 404
        ERROR.validate(response.json())
        assert response.json()["data"]["code"] == "NOT_FOUND"
        assert response.headers["access-control-allow-origin"] == headers["Origin"]
        assert (
            "access-control-allow-origin"
            not in client.get("/health", headers={"Origin": "https://untrusted.example"}).headers
        )
        preflight = client.options(
            "/health",
            headers={
                **headers,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code == 200
        assert (
            client.options(
                "/health",
                headers={
                    **headers,
                    "Access-Control-Request-Method": "DELETE",
                },
            ).status_code
            == 400
        )
        assert "ErrorResponse" in client.get("/openapi.json").json()["components"]["schemas"]


def test_unexpected_error_is_sanitized_and_has_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken(*args: Any, **kwargs: Any) -> dict[str, bool]:
        raise RuntimeError("super-secret")

    monkeypatch.setattr("saham_signal.transport.http.check_dependencies", broken)
    with TestClient(create_app(Settings(), probes()), raise_server_exceptions=False) as client:
        response = client.get("/ready", headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 500
        ERROR.validate(response.json())
        assert response.json()["data"]["code"] == "INTERNAL_ERROR"
        assert "super-secret" not in response.text
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_validation_and_method_errors_use_contract() -> None:
    wrapped = cast(CORSMiddleware, create_app(Settings(), probes()))
    app = cast(FastAPI, wrapped.app)

    @app.get("/test-validation")
    async def validation_endpoint(lots: int) -> int:
        return lots

    with TestClient(wrapped) as client:
        response = client.get("/test-validation?lots=sensitive-invalid-input")
        assert response.status_code == 422
        ERROR.validate(response.json())
        assert response.json()["data"]["code"] == "INVALID_REQUEST"
        assert "sensitive-invalid-input" not in response.text
        response = client.post("/health")
        assert response.status_code == 405
        assert "GET" in response.headers["allow"]
        ERROR.validate(response.json())


@pytest.mark.parametrize(
    "overrides",
    [
        {"app_mode": "invalid"},
        {"app_mode": "paper"},
        {"redis_namespace": "saham-signal:live:"},
        {"database_url": "postgresql://localhost/saham_signal_live"},
        {"database_url": "postgresql://localhost/saham_signal_research?dbname=saham_signal_live"},
        {"redis_url": "https://localhost"},
        {"cors_origins": ["*"]},
        {"cors_origins": ["https://example.com/path"]},
        {"readiness_timeout_seconds": 0},
    ],
)
def test_invalid_settings(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_settings_environment_and_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "paper")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:private@localhost/saham_signal_paper")
    monkeypatch.setenv("REDIS_NAMESPACE", "saham-signal:paper:")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("PILOT_ACCOUNT_ID", "pilot")
    settings = Settings()
    assert settings.app_mode == "paper"
    assert "private" not in repr(settings)
    assert "s" * 32 not in repr(settings)


def test_invalid_mode_fails_real_startup_without_secrets() -> None:
    import os

    result = subprocess.run(
        [sys.executable, "-m", "saham_signal.transport.http"],
        env={**os.environ, "APP_MODE": "invalid-private-value"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Invalid backend configuration" in result.stderr
    assert "invalid-private-value" not in result.stderr


def test_probes_recover_without_restart() -> None:
    probe = Probe(fails=True)
    dependencies: dict[str, DependencyProbe] = {"postgresql": probe, "redis": Probe()}
    assert asyncio.run(check_dependencies(dependencies, 0.1))["postgresql"] is False
    probe.fails = False
    assert all(asyncio.run(check_dependencies(dependencies, 0.1)).values())
