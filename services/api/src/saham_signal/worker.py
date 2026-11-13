"""Worker composition root, shipped in the same backend wheel as the API."""

import argparse
import asyncio
import json
import signal
import sys
from datetime import UTC, datetime
from types import FrameType

from pydantic import Field

from saham_signal.application.worker import run_worker
from saham_signal.config import Settings
from saham_signal.domain.mode import Mode


class WorkerSettings(Settings):
    # Keep worker knobs out of the shared HTTP configuration surface.
    worker_heartbeat_seconds: float = Field(default=30, ge=0.05, le=3600, allow_inf_nan=False)
    worker_max_attempts: int = Field(default=3, ge=1, le=10)
    worker_retry_seconds: float = Field(default=1, ge=0.05, le=60, allow_inf_nan=False)
    worker_shutdown_seconds: float = Field(default=10, ge=0.05, le=60, allow_inf_nan=False)


def emit(event: str, mode: Mode, attempt: int) -> None:
    # Allowlisted fields only; never log exception messages, settings, or work payloads.
    print(
        json.dumps(
            {"event": event, "mode": mode, "attempt": attempt, "at": datetime.now(UTC).isoformat()}
        ),
        flush=True,
    )


async def serve(settings: WorkerSettings, *, stop_after: float | None = None) -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def request_stop(signum: int, frame: FrameType | None) -> None:
        loop.call_soon_threadsafe(stop.set)

    previous = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    timer = loop.call_later(stop_after, stop.set) if stop_after is not None else None
    try:
        await run_worker(
            stop,
            mode=settings.app_mode,
            emit=emit,
            heartbeat_seconds=settings.worker_heartbeat_seconds,
            max_attempts=settings.worker_max_attempts,
            retry_seconds=settings.worker_retry_seconds,
            shutdown_seconds=settings.worker_shutdown_seconds,
        )
    finally:
        if timer is not None:
            timer.cancel()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Saham Signal worker (idle bootstrap)")
    parser.add_argument("--env-file", default=None)
    parser.add_argument(
        "--stop-after", type=float, default=None, help="Smoke run duration in seconds"
    )
    args = parser.parse_args()
    if args.stop_after is not None and not 0 < args.stop_after <= 3600:
        parser.error("--stop-after must be between 0 (exclusive) and 3600 seconds")
    try:
        # Pydantic's generated model signature omits BaseSettings' runtime keyword.
        settings = WorkerSettings(_env_file=args.env_file)  # type: ignore[call-arg]
    except Exception:
        print("Invalid worker configuration; check worker README and environment", file=sys.stderr)
        return 2
    try:
        asyncio.run(serve(settings, stop_after=args.stop_after))
    except Exception:
        emit("fatal_failure", settings.app_mode, 0)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
