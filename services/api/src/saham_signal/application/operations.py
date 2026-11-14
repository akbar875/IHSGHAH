"""Bounded process telemetry and explicit, durable operator release decisions."""

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime
from math import ceil, isfinite
from threading import RLock
from typing import Any, Literal, Protocol

from saham_signal.domain.mode import Mode

Action = Literal["pause", "drift", "rollback", "resume"]


@dataclass(frozen=True)
class Control:
    revision: int = 0
    blocked: bool = True
    reason: str = "uninitialized"
    release: str = "none"


class ControlStore(Protocol):
    def read(self, mode: Mode) -> Control: ...

    def write(
        self, mode: Mode, expected: int, action: Action, release: str, evidence: str, actor: str
    ) -> Control: ...


class Telemetry:
    """Fixed names; never retain URLs, accounts, payloads or unbounded symbol labels.

    Latency is a rolling nearest-rank p95 of the last 2048 observations, not a
    browser-display or vendor SLA. Missing measurements are null, never zero.
    """

    COUNTERS = frozenset(
        {"http_requests", "http_failed", "feed_gap", "alert_failed", "missing_input", "drift"}
    )
    GAUGES = frozenset(
        {"feed_lag_seconds", "active_candidates", "queue_depth", "capacity_fraction", "cost_idr"}
    )

    def __init__(self) -> None:
        self.lock = RLock()
        self.counts: Counter[str] = Counter()
        self.latencies: deque[float] = deque(maxlen=2048)
        self.gauges: dict[str, float] = {}

    def count(self, name: str, amount: int = 1) -> None:
        if name not in self.COUNTERS or type(amount) is not int or amount < 0:
            raise ValueError("Unknown counter or negative amount")
        with self.lock:
            self.counts[name] += amount

    def gauge(self, name: str, value: float) -> None:
        if name not in self.GAUGES or not isfinite(value) or value < 0:
            raise ValueError("Unknown gauge or invalid value")
        with self.lock:
            self.gauges[name] = value

    def latency(self, seconds: float) -> None:
        if not isfinite(seconds) or seconds < 0:
            raise ValueError("Invalid latency")
        with self.lock:
            self.latencies.append(seconds)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            samples = sorted(self.latencies)
            return {
                "scope": "process_since_start",
                "counters": {k: self.counts[k] for k in sorted(self.COUNTERS)},
                "gauges": {k: self.gauges.get(k) for k in sorted(self.GAUGES)},
                "internal_p95_seconds": samples[ceil(len(samples) * 0.95) - 1] if samples else None,
                "latency_samples": len(samples),
            }


def change(previous: Control, action: Action, release: str, evidence: str) -> Control:
    if action not in {"pause", "drift", "rollback", "resume"}:
        raise ValueError("Unsupported operation")
    if not 1 <= len(evidence.strip()) <= 512 or not 1 <= len(release.strip()) <= 128:
        raise ValueError("Release and review/incident evidence required")
    # A drift observation can only pause. Resume/rollback require a separate
    # explicit operator command with a reviewed immutable release identifier.
    return Control(previous.revision + 1, action != "resume", action, release)


class Operations:
    def __init__(self, store: ControlStore, mode: Mode, telemetry: Telemetry | None = None) -> None:
        self.store, self.mode = store, mode
        self.telemetry = telemetry or Telemetry()
        self.local_drift = False

    def control(self) -> Control:
        if self.local_drift:
            return Control(reason="drift_persistence_pending")
        try:
            return self.store.read(self.mode)
        except Exception:
            # Control storage outage never authorizes an entry; position reads continue.
            self.telemetry.count("missing_input")
            return Control(reason="control_unavailable")

    def entry_blocked(self) -> bool:
        return self.local_drift or self.control().blocked

    def observe_drift(self, evidence: str) -> None:
        """Detector hook: persist abstention and request review; never select/train a model.

        A failed write latches this process closed. Restart is safe only after the
        operator has persisted the pause (see runbook); no background auto-resume.
        """
        self.local_drift = True
        self.telemetry.count("drift")
        current = self.store.read(self.mode)
        self.store.write(
            self.mode, current.revision, "drift", current.release, evidence, "detector"
        )
        self.local_drift = False  # durable drift pause now owns recovery

    def feed(self, reasons: tuple[str, ...], lag: float | None) -> None:
        if "SEQUENCE_GAP" in reasons:
            self.telemetry.count("feed_gap")
        if lag is not None:
            self.telemetry.gauge("feed_lag_seconds", max(0, lag))
        if any(r not in {"SIMULATION"} for r in reasons):
            self.telemetry.count("missing_input")

    def status(self, at: datetime) -> dict[str, Any]:
        from dataclasses import asdict

        return {
            "mode": self.mode,
            "as_of": at.isoformat(),
            "control": asdict(self.control()),
            "local_drift_latched": self.local_drift,
            "metrics": self.telemetry.snapshot(),
            "gates_passed": False,
        }
