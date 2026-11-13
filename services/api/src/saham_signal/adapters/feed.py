"""Shared-schema validation and an explicitly simulated JSON replay adapter.

No HTTP requests, credentials, vendor guesses, or automatic source fallback.
"""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from saham_signal.adapters.persistence import SCHEMA, Journal
from saham_signal.application.feed import FeedMessage, FeedProfile, Observation

SIMULATION_PROFILE = FeedProfile(
    source="simulation-feed-v1",
    schema_ref="simulation-feed/1",
    origin="simulation",
    delivery="delayed",
    volume_unit="shares",
)


def validate_observation(schema: str, payload: dict[str, Any]) -> None:
    Draft202012Validator(
        {"$ref": f"#/$defs/{schema}", "$defs": SCHEMA["$defs"]},
        format_checker=FormatChecker(),
    ).validate(payload)


class MarketJournalSink:
    """Persist v1 events through SS-010; candles explicitly require another sink.

    A restarted session must recover persisted upstream identities/revisions before
    ingesting corrections. Conflicting durable keys raise; never retry them as new
    events. No exactly-once claim across restart is made by this session scaffold.
    """

    def __init__(self, journal: Journal) -> None:
        if journal.user_id:
            raise ValueError("Feed journal requires market scope")
        self.journal = journal

    def __call__(self, observation: Observation) -> None:
        if observation.record is None:
            raise ValueError("Candle persistence envelope is not supported by contract v1")
        if observation.payload["mode"] != self.journal.mode:
            raise ValueError("Journal mode differs from feed mode")
        self.journal.append([observation.record])


def simulation_messages(path: Path, *, connection: int = 1) -> Iterator[FeedMessage]:
    """Replay only our own synthetic schema, never reinterpret vendor samples.

    Ingest timing is supplied separately by the replay caller and must reflect
    actual availability; do not replace missing received_at with event_time.
    """
    document = json.loads(path.read_text("utf-8"))
    if set(document) != {"schema", "data_origin", "events"} or (
        document["schema"] != SIMULATION_PROFILE.schema_ref
        or document["data_origin"] != "simulation"
    ):
        raise ValueError("Expected explicitly labeled simulation fixture")
    for event in document["events"]:
        if set(event) != {
            "event_id",
            "symbol",
            "kind",
            "sequence",
            "event_time",
            "provider_time",
            "payload",
            "revision",
        }:
            raise ValueError("Unexpected simulation fields")
        yield FeedMessage(
            profile=SIMULATION_PROFILE,
            connection=connection,
            event_id=event["event_id"],
            symbol=event["symbol"],
            kind=event["kind"],
            sequence=event["sequence"],
            revision=event["revision"],
            event_time=datetime.fromisoformat(event["event_time"]),
            provider_time=datetime.fromisoformat(event["provider_time"])
            if event["provider_time"] is not None
            else None,
            payload=event["payload"],
        )
