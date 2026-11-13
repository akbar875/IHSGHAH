"""Validated persistence envelope around unchanged v1 contract snapshots."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from saham_signal.domain.mode import Mode

Kind = Literal["MarketEvent", "Signal", "Fill", "Position", "Experiment"]


@dataclass(frozen=True)
class Record:
    kind: Kind
    entity_id: str
    version: int
    idempotency_key: str
    event_time: datetime
    received_at: datetime
    available_at: datetime
    processed_at: datetime
    sequence: str
    source: str
    data_origin: Literal["simulation", "market"]
    actor: str
    reason: str
    payload: dict[str, Any]
    provider_time: datetime | None = None
    contract_version: str = "1.0.0"

    def document(self, mode: Mode, user_id: str) -> dict[str, Any]:
        """Validate at write time, also protecting mutable payloads after construction."""
        if self.kind not in ("MarketEvent", "Signal", "Fill", "Position", "Experiment"):
            raise ValueError("Unknown record kind")
        if mode not in ("research", "paper", "live"):
            raise ValueError("Unknown mode")
        if (self.kind == "MarketEvent") != (user_id == "") or len(user_id) > 128:
            raise ValueError("Personal records require an account; market scope uses empty account")
        if self.kind == "Experiment" and mode != "research":
            raise ValueError("Experiments belong to research")
        if self.data_origin not in ("simulation", "market") or (
            mode == "live" and self.data_origin == "simulation"
        ):
            raise ValueError("Invalid data origin for mode")
        if self.contract_version != "1.0.0" or not re.fullmatch(
            r"0|[1-9][0-9]{0,19}", self.sequence
        ):
            raise ValueError("Invalid contract version or sequence")
        for value, maximum in (
            (self.entity_id, 128),
            (self.idempotency_key, 256),
            (self.source, 128),
            (self.actor, 128),
            (self.reason, 2000),
        ):
            if not value or len(value) > maximum:
                raise ValueError("Missing or oversized persistence metadata")
        if type(self.version) is not int or not 1 <= self.version <= 2147483647:
            raise ValueError("Version must be a positive integer")
        document = asdict(self)
        for name in ("event_time", "received_at", "available_at", "processed_at", "provider_time"):
            value = getattr(self, name)
            if value is not None:
                if value.tzinfo is None or value.utcoffset() is None:
                    raise ValueError("Timestamps must carry a timezone")
                document[name] = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if not self.received_at <= self.available_at <= self.processed_at:
            raise ValueError("Invalid availability/processing order")
        id_field = {
            "MarketEvent": "event_id",
            "Signal": "signal_id",
            "Fill": "fill_id",
            "Position": "position_id",
            "Experiment": "experiment_id",
        }[self.kind]
        if self.payload[id_field] != self.entity_id:
            raise ValueError("Snapshot identity differs from envelope")
        for name, expected in (
            ("mode", mode),
            ("user_id", user_id),
            ("version", self.version),
            ("data_origin", self.data_origin),
            ("contract_version", self.contract_version),
        ):
            if name in self.payload and self.payload[name] != expected:
                raise ValueError("Snapshot scope/version differs from envelope")
        if self.kind == "MarketEvent":
            for name in (
                "event_time",
                "provider_time",
                "received_at",
                "available_at",
                "processed_at",
                "sequence",
                "source",
            ):
                actual = self.payload[name]
                expected = document[name]
                if name.endswith("_time") or name.endswith("_at"):
                    actual = datetime.fromisoformat(actual) if actual is not None else None
                    expected = getattr(self, name)
                if actual != expected:
                    raise ValueError("Market timestamp/sequence differs from envelope")
        known_times = {
            "Signal": ("generated_at", "data_as_of"),
            "Fill": ("filled_at", "recorded_at"),
            "Position": ("opened_at",),
            "Experiment": ("as_of",),
            "MarketEvent": (),
        }[self.kind]
        if any(
            datetime.fromisoformat(self.payload[name]) > self.available_at for name in known_times
        ):
            raise ValueError("Snapshot contains information newer than available_at")
        return document


def digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
