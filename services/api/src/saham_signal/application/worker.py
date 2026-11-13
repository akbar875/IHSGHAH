"""Sequential worker lifecycle; no vendor, storage, or transport dependencies."""

import asyncio
from collections.abc import Awaitable, Callable

from saham_signal.domain.mode import Mode

type Work = Callable[[], Awaitable[None]]
type Emit = Callable[[str, Mode, int], None]


class RetryableWorkError(Exception):
    """Only raise when retry is safe: no effect committed, or durable dedup exists."""


async def wait_for_stop(stop: asyncio.Event, seconds: float) -> bool:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
        return True
    except TimeoutError:
        return False


async def run_worker(
    stop: asyncio.Event,
    *,
    mode: Mode,
    emit: Emit,
    heartbeat_seconds: float,
    max_attempts: int,
    retry_seconds: float,
    shutdown_seconds: float,
    work: Work | None = None,
) -> None:
    """Run at most one work call at a time; drain/cancel it before stopping."""

    async def heartbeat() -> None:
        while not stop.is_set():
            emit("heartbeat", mode, 0)
            if await wait_for_stop(stop, heartbeat_seconds):
                break

    async def execute() -> None:
        if work is None:
            await stop.wait()
            return
        while not stop.is_set():
            for attempt in range(1, max_attempts + 1):
                try:
                    await work()
                    break
                except RetryableWorkError:
                    emit("work_retryable_failure", mode, attempt)
                    if attempt == max_attempts:
                        raise
                    if await wait_for_stop(stop, retry_seconds):
                        return
                except Exception:
                    emit("work_failure", mode, attempt)
                    raise
            # Avoid a busy loop, even if the work completed immediately.
            if await wait_for_stop(stop, heartbeat_seconds):
                return

    emit("started", mode, 0)
    pulse = asyncio.create_task(heartbeat())
    task = asyncio.create_task(execute())
    stopping = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait({task, stopping, pulse}, return_when=asyncio.FIRST_COMPLETED)
        if pulse in done:
            await pulse  # Do not silently lose heartbeat failures.
        if task in done:
            await task
        else:
            emit("stopping", mode, 0)
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=shutdown_seconds)
            except TimeoutError:
                emit("shutdown_timeout", mode, 0)
                task.cancel()
    finally:
        stop.set()
        for pending in (task, pulse, stopping):
            pending.cancel()
        await asyncio.gather(task, pulse, stopping, return_exceptions=True)
        emit("stopped", mode, 0)
