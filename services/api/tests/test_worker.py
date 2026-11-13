import asyncio
import json
import os
import signal
import subprocess
import sys

import pytest

from saham_signal.application.worker import RetryableWorkError, run_worker
from saham_signal.worker import WorkerSettings


def test_retry_is_bounded_and_logs_no_exception() -> None:
    events: list[str] = []
    calls = 0

    async def fail() -> None:
        nonlocal calls
        calls += 1
        raise RetryableWorkError("secret credential")

    async def scenario() -> None:
        with pytest.raises(RetryableWorkError):
            await run_worker(
                asyncio.Event(),
                mode="research",
                emit=lambda event, *_: events.append(event),
                heartbeat_seconds=0.01,
                max_attempts=3,
                retry_seconds=0.001,
                shutdown_seconds=0.01,
                work=fail,
            )

    asyncio.run(scenario())
    assert calls == 3
    assert events.count("work_retryable_failure") == 3
    assert events[-1] == "stopped"
    assert "secret" not in str(events)


def test_unknown_failure_is_never_retried() -> None:
    calls = 0

    async def fail() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("commit outcome unknown")

    async def scenario() -> None:
        with pytest.raises(RuntimeError):
            await run_worker(
                asyncio.Event(),
                mode="paper",
                emit=lambda *_: None,
                heartbeat_seconds=0.01,
                max_attempts=3,
                retry_seconds=0.001,
                shutdown_seconds=0.01,
                work=fail,
            )

    asyncio.run(scenario())
    assert calls == 1


@pytest.mark.parametrize("drain", [True, False])
def test_shutdown_drains_or_cancels_one_inflight_work(drain: bool) -> None:
    events: list[str] = []
    effects: list[str] = []

    async def scenario() -> None:
        stop = asyncio.Event()

        async def work() -> None:
            stop.set()
            try:
                await asyncio.sleep(0.001 if drain else 10)
                effects.append("committed")
            finally:
                effects.append("closed")

        await run_worker(
            stop,
            mode="research",
            emit=lambda event, *_: events.append(event),
            heartbeat_seconds=0.01,
            max_attempts=3,
            retry_seconds=0.001,
            shutdown_seconds=0.02,
            work=work,
        )

    asyncio.run(scenario())
    assert effects == (["committed", "closed"] if drain else ["closed"])
    assert ("shutdown_timeout" in events) is not drain
    assert events[-1] == "stopped"


def test_shutdown_interrupts_backoff() -> None:
    calls = 0

    async def scenario() -> None:
        stop = asyncio.Event()

        async def fail() -> None:
            nonlocal calls
            calls += 1
            stop.set()
            raise RetryableWorkError

        await asyncio.wait_for(
            run_worker(
                stop,
                mode="research",
                emit=lambda *_: None,
                heartbeat_seconds=0.01,
                max_attempts=3,
                retry_seconds=60,
                shutdown_seconds=0.1,
                work=fail,
            ),
            timeout=1,
        )

    asyncio.run(scenario())
    assert calls == 1


def test_retry_success_has_one_effect_and_no_overlap() -> None:
    calls = 0
    effects: list[str] = []

    async def scenario() -> None:
        stop = asyncio.Event()

        async def work() -> None:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RetryableWorkError
            effects.append("committed")
            stop.set()

        await run_worker(
            stop,
            mode="research",
            emit=lambda *_: None,
            heartbeat_seconds=0.01,
            max_attempts=3,
            retry_seconds=0.001,
            shutdown_seconds=0.1,
            work=work,
        )

    asyncio.run(scenario())
    assert calls == 3
    assert effects == ["committed"]


def test_real_process_heartbeat_clean_stop_and_secret_safe_failure() -> None:
    env = {**os.environ, "APP_MODE": "research", "WORKER_HEARTBEAT_SECONDS": "0.05"}
    result = subprocess.run(
        [sys.executable, "-m", "saham_signal.worker", "--stop-after", "0.2"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert events[0]["event"] == "started"
    assert events[-1]["event"] == "stopped"
    assert sum(e["event"] == "heartbeat" for e in events) >= 2
    assert all(e["mode"] == "research" for e in events)
    result = subprocess.run(
        [sys.executable, "-m", "saham_signal.worker"],
        env={**env, "APP_MODE": "invalid-secret", "DATABASE_URL": "secret-dsn"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "secret" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX SIGTERM; Windows smoke uses timer")
def test_real_sigterm_shutdown() -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "saham_signal.worker"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert json.loads(process.stdout.readline())["event"] == "started"
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        assert json.loads(stdout.splitlines()[-1])["event"] == "stopped"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


@pytest.mark.parametrize(
    "values",
    [
        {"worker_max_attempts": 0},
        {"worker_max_attempts": 11},
        {"worker_retry_seconds": 0},
        {"worker_heartbeat_seconds": float("nan")},
        {"worker_shutdown_seconds": float("inf")},
        {"app_mode": "paper"},
    ],
)
def test_settings_reject_invalid_configuration(values: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        WorkerSettings(**values)  # type: ignore[arg-type]
