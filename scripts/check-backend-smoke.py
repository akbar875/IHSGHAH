"""Simulation-only smoke of the installed backend wheel, without vendor or DB services."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from importlib.resources import files
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from websockets.sync.client import connect

from saham_signal.adapters.paper_simulation import run as paper_qualification
from saham_signal.adapters.persistence import SCHEMA
from saham_signal.application.market import FixtureMarket, MarketScope, validate


def main() -> None:
    assert SCHEMA["$defs"]["MarketEvent"]
    assert files("saham_signal.migrations").joinpath("001_journal.sql").is_file()
    assert files("saham_signal.migrations").joinpath("002_preferences.sql").is_file()
    assert files("saham_signal.migrations").joinpath("007_paper_qualification.sql").is_file()
    paper = paper_qualification()
    assert paper["mode"] == "paper" and paper["actual_fills"] == []
    assert len(paper["paper_fills"]) == 2 and not paper["readiness"]["paper_live_enabled"]
    # Verify packaged scenario/schema without bypassing DB checks on HTTP routes.
    fixture = FixtureMarket()
    validate(
        "CandidatesResponse",
        fixture.read(MarketScope("fixture-smoke", "research", "1000000.00", 30), "candidates"),
    )
    # Reserve a non-listening port so neither dependency can accidentally be healthy.
    with socket.socket() as unavailable, socket.socket() as http_port:
        unavailable.bind(("127.0.0.1", 0))
        http_port.bind(("127.0.0.1", 0))
        dependency_port = unavailable.getsockname()[1]
        port = http_port.getsockname()[1]
        http_port.close()
        fixture_token = os.urandom(32).hex()
        env = {
            **os.environ,
            "APP_MODE": "research",
            "DATABASE_URL": (
                f"postgresql://simulation:simulation@127.0.0.1:{dependency_port}"
                "/saham_signal_research"
            ),
            "REDIS_URL": f"redis://:simulation@127.0.0.1:{dependency_port}/0",
            "REDIS_NAMESPACE": "saham-signal:research:",
            "CORS_ORIGINS": '["http://localhost:3000"]',
            "MARKET_FIXTURE_ENABLED": "true",
            "MARKET_FIXTURE_TOKEN": fixture_token,
            "MARKET_NOMINAL_IDR": "1000000.00",
            "MARKET_HORIZON_MINUTES": "30",
            "PILOT_ACCOUNT_ID": "fixture-smoke",
            "READINESS_TIMEOUT_SECONDS": "0.1",
            "WORKER_HEARTBEAT_SECONDS": "0.05",
            "WORKER_MAX_ATTEMPTS": "1",
            "WORKER_RETRY_SECONDS": "0.05",
            "WORKER_SHUTDOWN_SECONDS": "1",
        }
        with tempfile.TemporaryDirectory(prefix="backend-smoke-") as directory:
            # -I plus a temporary cwd prevents an editable source tree hiding wheel defects.
            code = (
                "import asyncio,sys,uvicorn; "
                "asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) "
                "if sys.platform == 'win32' else None; "
                "uvicorn.run('saham_signal.transport.http:create_app',factory=True,"
                f"host='127.0.0.1',port={port},log_level='error')"
            )
            with tempfile.TemporaryFile() as logs:
                process = subprocess.Popen(
                    [sys.executable, "-I", "-c", code],
                    cwd=directory,
                    env=env,
                    stdout=logs,
                    stderr=logs,
                )
                try:
                    opener = build_opener(ProxyHandler({}))
                    deadline = time.monotonic() + 20
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError("Installed API exited before becoming healthy")
                        try:
                            with opener.open(f"http://127.0.0.1:{port}/health", timeout=1) as r:
                                assert r.status == 200
                                assert json.load(r) == {
                                    "status": "ok",
                                    "mode": "research",
                                }
                            break
                        except (URLError, TimeoutError):
                            if time.monotonic() >= deadline:
                                raise RuntimeError("Installed API health timed out") from None
                            time.sleep(0.1)
                    try:
                        opener.open(f"http://127.0.0.1:{port}/ready", timeout=5)
                    except HTTPError as error:
                        with error:
                            payload = json.load(error)
                            assert error.code == 503
                            assert payload["data"]["code"] == "DATA_UNAVAILABLE"
                            assert payload["mode"] == "research"
                            assert payload["data_origin"] == "simulation"
                    else:
                        raise AssertionError("Readiness must fail without DB/cache")
                    request = Request(
                        f"http://127.0.0.1:{port}/api/v1/candidates",
                        headers={"Cookie": f"saham_session={fixture_token}"},
                    )
                    try:
                        opener.open(request, timeout=5)
                    except HTTPError as error:
                        with error:
                            payload = json.load(error)
                            validate("ErrorResponse", payload)
                            assert error.code == 503
                            assert payload["data"]["code"] == "DATA_UNAVAILABLE"
                    else:
                        raise AssertionError("Market must not bypass unavailable personal settings")
                    subscription = {
                        "kind": "subscribe",
                        "contract_version": "1.0.0",
                        "subscription_id": "wheel-smoke",
                        "topic": "signals",
                        "symbol": None,
                        "resume_cursor": None,
                    }
                    with connect(
                        f"ws://127.0.0.1:{port}/api/v1/stream",
                        origin="http://localhost:3000",
                        additional_headers={"Cookie": f"saham_session={fixture_token}"},
                        open_timeout=5,
                        close_timeout=2,
                        proxy=None,
                    ) as ws:
                        ws.send(json.dumps(subscription))
                        unavailable = json.loads(ws.recv(timeout=5))
                        validate("ErrorResponse", unavailable)
                        assert unavailable["data"]["code"] == "DATA_UNAVAILABLE"
                        subscription["resume_cursor"] = "unavailable-wheel-smoke"
                        ws.send(json.dumps(subscription))
                        error = json.loads(ws.recv(timeout=5))
                        validate("ErrorResponse", error)
                        assert error["data"]["code"] == "RESYNC_REQUIRED"
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            worker = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "saham_signal.worker",
                    "--stop-after",
                    "0.3",
                ],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            )
            events = [json.loads(line) for line in worker.stdout.splitlines()]
            assert events[0]["event"] == "started"
            assert events[-1]["event"] == "stopped"
            assert any(event["event"] == "heartbeat" for event in events)
            assert all(event["mode"] == "research" for event in events)
    print("Installed API/worker smoke passed (simulation; no vendor services).")


if __name__ == "__main__":
    main()
