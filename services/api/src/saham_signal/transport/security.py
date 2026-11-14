"""Bounded single-pilot request budget and logging that never formats user payloads."""

import logging
import time
from threading import Lock


class SecurityBudget:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.window = -1
        self.counts: dict[str, int] = {}
        self.lock = Lock()

    def allow(self, channel: str) -> bool:
        # Two server-owned channels, independent of attacker-controlled IP/cookies.
        with self.lock:
            window = int(time.monotonic() // 60)
            if window != self.window:
                self.window, self.counts = window, {}
            self.counts[channel] = self.counts.get(channel, 0) + 1
            return self.counts[channel] <= self.limit


class SafeServerLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access":
            return False
        if record.exc_info or record.stack_info:
            # Traceback messages may contain DSNs, vendor keys or request bodies.
            record.msg = "Backend request failed; inspect request ID and health checks"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True


def configure_server_logging() -> None:
    for name in ("uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, SafeServerLog) for item in logger.filters):
            logger.addFilter(SafeServerLog())
