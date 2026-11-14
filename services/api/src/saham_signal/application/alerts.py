"""In-app policy. No order/fill side effects and no replay-to-live delivery path."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Literal, Protocol

from saham_signal.application.feed_quality import PositionDataDisruption
from saham_signal.application.market import MarketScope, stamp, validate
from saham_signal.domain.mode import Mode

AlertType = Literal[
    "ENTRY_READY", "INVALIDATED", "TP", "STOP", "TIME_EXIT", "PLAN_CHANGED", "DATA_DISCONNECTED"
]
PRIORITY = {
    "STOP": 0,
    "DATA_DISCONNECTED": 0,
    "TIME_EXIT": 1,
    "TP": 1,
    "INVALIDATED": 2,
    "PLAN_CHANGED": 3,
    "ENTRY_READY": 4,
}


@dataclass(frozen=True)
class AlertEvent:
    key: str
    kind: AlertType
    occurred_at: datetime
    signal_id: str | None = None
    position_id: str | None = None
    active: bool = True
    origin: Literal["simulation", "market"] = "simulation"
    replay: bool = False
    mode: Mode = "research"

    @property
    def group(self) -> str:
        return f"{self.kind}:{self.position_id or self.signal_id}"


class AlertStore(Protocol):
    def refresh(
        self, scope: MarketScope, events: list[AlertEvent], at: datetime
    ) -> list[dict[str, Any]]: ...


def delivery(
    scope: MarketScope, event: AlertEvent, at: datetime, gate: dict[str, Any]
) -> dict[str, Any] | None:
    """Gate is durable per subject/type. Risk bypasses entry hysteresis/cooldown.

    READY must remain observed for 3s. An inactive observation resets stability;
    a new READY episode within 30s of delivery waits for cooldown. These provisional
    defaults suppress flicker, not a claim of validated model/market latency.
    """
    if at.tzinfo is None or event.occurred_at.tzinfo is None or event.occurred_at > at:
        raise ValueError("Alert timestamps must be aware and not in the future")
    if event.mode != scope.mode or event.replay:
        return None
    if scope.mode == "live" and event.origin != "market":
        return None
    if event.origin == "market" and scope.mode == "research":
        return None
    if not event.active:
        gate.pop("since", None)
        return None
    if event.kind == "ENTRY_READY":
        since = datetime.fromisoformat(gate.setdefault("since", stamp(at)))
        last = datetime.fromisoformat(gate["last"]) if "last" in gate else None
        if at - since < timedelta(seconds=3) or (last and at - last < timedelta(seconds=30)):
            return None
    if event.kind == "PLAN_CHANGED" and "last" in gate:
        if at - datetime.fromisoformat(gate["last"]) < timedelta(seconds=30):
            return None
    identity = sha256(f"{scope.mode}:{scope.account}:{event.key}:in_app".encode()).hexdigest()
    alert = {
        "event_id": identity,
        "user_id": scope.account,
        "signal_id": event.signal_id,
        "position_id": event.position_id,
        "type": event.kind,
        "created_at": stamp(event.occurred_at),
        "delivered_at": None,
        "status": "pending",
        "channel": "in_app",
        "dedup_key": identity,
    }
    validate("Alert", alert)
    gate["last"] = stamp(at)
    return alert


def feed_event(disruption: PositionDataDisruption, *, replay: bool = False) -> AlertEvent:
    """SS-012 recovery episodes have stable identities across retry/reconnect."""
    return AlertEvent(
        key=f"feed:{disruption.source}:{disruption.symbol}:{disruption.position_id}:"
        f"{disruption.episode}",
        kind="DATA_DISCONNECTED",
        occurred_at=disruption.assessment.as_of,
        position_id=disruption.position_id,
        origin=disruption.assessment.data_origin,
        mode=disruption.assessment.mode,
        replay=replay,
    )


def source_events(
    history: list[dict[str, Any]],
    quality: dict[str, Any],
    positions: list[dict[str, Any]],
    at: datetime,
) -> list[AlertEvent]:
    """Research projection; never infer price hits or entry from fixture prices."""
    events: list[AlertEvent] = []
    for signal in history:
        sid, version = signal["signal_id"], signal["version"]
        ready = signal["state"] == "READY" and quality["status"] == "healthy"
        ready &= at < datetime.fromisoformat(signal["entry_until"])
        events.append(
            AlertEvent(
                f"signal:{sid}:{version}:entry", "ENTRY_READY", at, signal_id=sid, active=ready
            )
        )
        if signal["state"] in {"CANCELLED", "EXPIRED"}:
            events.append(
                AlertEvent(
                    f"signal:{sid}:{version}:invalid",
                    "INVALIDATED",
                    datetime.fromisoformat(signal["generated_at"]),
                    signal_id=sid,
                )
            )
    # Only the latest signal determines readiness; historical READY cannot re-arm it.
    latest = {s["signal_id"]: s for s in sorted(history, key=lambda s: s["version"])}
    events = [
        e
        for e in events
        if e.kind != "ENTRY_READY"
        or e.key == f"signal:{e.signal_id}:{latest[e.signal_id]['version']}:entry"
    ]
    for state in positions:
        p = state["position"]
        if not p["remaining_lots"]:
            continue
        pid = p["position_id"]
        exit_types: dict[str, AlertType] = {"STOP": "STOP", "TARGET": "TP", "DEADLINE": "TIME_EXIT"}
        kind = exit_types.get(state["exit_reason"])
        if kind:
            # Partial fills/plan versions do not create another alert for the same exit.
            events.append(AlertEvent(f"position:{pid}:exit:{kind}", kind, at, position_id=pid))
        if state["plan"]:
            version = sha256(json.dumps(state["plan"], sort_keys=True).encode()).hexdigest()
            events.append(
                AlertEvent(f"position:{pid}:plan:{version}", "PLAN_CHANGED", at, position_id=pid)
            )
        if quality["status"] != "healthy":
            events.append(
                AlertEvent(
                    f"position:{pid}:fixture-feed-unavailable",
                    "DATA_DISCONNECTED",
                    at,
                    position_id=pid,
                )
            )
    if quality["status"] != "healthy":
        for sid in latest:
            events.append(
                AlertEvent(
                    f"signal:{sid}:fixture-feed-unavailable", "DATA_DISCONNECTED", at, signal_id=sid
                )
            )
    return sorted(events, key=lambda event: PRIORITY[event.kind])
