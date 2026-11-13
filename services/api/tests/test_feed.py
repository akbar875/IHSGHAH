"""Synthetic acceptance tests; these are not vendor sample certification."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from saham_signal.adapters.feed import (
    SIMULATION_PROFILE,
    MarketJournalSink,
    simulation_messages,
    validate_observation,
)
from saham_signal.adapters.persistence import Journal
from saham_signal.application.feed import FeedIngestor, FeedMessage, Observation

NOW = datetime(2026, 11, 13, 3, 2, tzinfo=UTC)
FIXTURE = Path(__file__).parent / "fixtures/feed-simulation.json"


def messages() -> list[FeedMessage]:
    return list(simulation_messages(FIXTURE))


def setup() -> tuple[FeedIngestor, list[Observation], list[tuple[str, int]]]:
    saved: list[Observation] = []
    requests: list[tuple[str, int]] = []
    ingestor = FeedIngestor(
        SIMULATION_PROFILE,
        "research",
        lot_shares=lambda *_: 100,
        validate=validate_observation,
        commit=saved.append,
        snapshot_request=lambda symbol, connection: requests.append((symbol, connection)),
    )
    return ingestor, saved, requests


def ingest(ingestor: FeedIngestor, message: FeedMessage) -> str:
    return ingestor.ingest(
        message,
        received_at=NOW,
        available_at=NOW + timedelta(milliseconds=1),
        processed_at=NOW + timedelta(milliseconds=2),
    )


def test_shared_contracts_times_units_and_atomic_book_replacement() -> None:
    ingestor, saved, _ = setup()
    for message in messages():
        assert ingest(ingestor, message) == "committed"
    assert [x.schema for x in saved] == ["MarketEvent"] * 3 + ["Candle", "MarketEvent"]
    book = saved[1].payload["payload"]
    assert book["bids"] == [{"price_idr": "995.00", "lots": 3, "cumulative_lots": 3}]
    assert book["asks"][0]["lots"] == 6
    assert book["limited"]
    assert saved[2].payload["payload"]["lots"] == 2
    assert saved[3].payload["volume_lots"] == 8
    assert saved[3].record is None
    assert saved[3].message.profile.origin == "simulation"
    assert saved[0].payload["event_time"] == "2026-11-13T03:00:00Z"
    assert saved[0].payload["provider_time"] == "2026-11-13T03:00:00.001000Z"
    assert saved[0].payload["received_at"] == "2026-11-13T03:02:00Z"
    assert saved[0].payload["available_at"] == "2026-11-13T03:02:00.001000Z"
    for observation in saved:
        validate_observation(observation.schema, observation.payload)
        if observation.record:
            observation.record.document("research", "")
            assert observation.payload["quality"]["status"] == "degraded"
            assert observation.payload["quality"]["feed"] == "delayed"


def test_replay_is_deterministic_and_payloads_do_not_alias() -> None:
    first, saved, _ = setup()
    second, replayed, _ = setup()
    for message in messages():
        ingest(first, message)
        ingest(second, message)
    assert saved == replayed
    snapshot = messages()[0]
    third, isolated, _ = setup()
    ingest(third, snapshot)
    snapshot.payload["bids"][0]["quantity"] = 12300
    assert isolated[0].payload["payload"]["bids"][0]["lots"] == 5
    assert third.books["SIM"].bids["1000.00"] == 5


def test_gap_stale_snapshot_and_reconnect_require_new_snapshot() -> None:
    ingestor, saved, requests = setup()
    snapshot, delta, *_ = messages()
    assert ingest(ingestor, delta) == "resync_required"
    assert not ingestor.books["SIM"].synchronized
    # Snapshot older than the discarded delta cannot repair missing updates.
    assert ingest(ingestor, snapshot) == "resync_required"
    assert not saved
    assert ingest(ingestor, replace(snapshot, sequence=2)) == "committed"
    assert ingest(ingestor, replace(delta, sequence=4)) == "resync_required"
    assert ingest(ingestor, replace(delta, sequence=5)) == "resync_required"
    assert len(saved) == 1
    assert ingest(ingestor, replace(snapshot, event_id="snap-5", sequence=5)) == "committed"
    assert ingest(ingestor, replace(delta, event_id="delta-6", sequence=6)) == "committed"
    ingestor.reconnect()
    assert requests[-1] == ("SIM", 2)
    assert not ingestor.books["SIM"].synchronized
    with pytest.raises(ValueError, match="stale connection"):
        ingest(ingestor, snapshot)
    assert ingest(ingestor, replace(delta, connection=2)) == "resync_required"
    assert (
        ingest(ingestor, replace(snapshot, event_id="new-snap", connection=2, sequence=2))
        == "committed"
    )


def test_duplicates_conflicts_corrections_and_late_trade_are_explicit() -> None:
    ingestor, saved, _ = setup()
    trade = messages()[2]
    assert ingest(ingestor, trade) == "committed"
    assert ingest(ingestor, trade) == "duplicate"
    correction = replace(trade, revision=2, payload={**trade.payload, "quantity": 300})
    assert ingest(ingestor, correction) == "committed"
    assert saved[-1].record is not None
    assert saved[-1].record.version == 2
    assert saved[0].payload["payload"]["lots"] == 2
    assert saved[-1].payload["payload"]["lots"] == 3
    with pytest.raises(ValueError, match="Conflicting"):
        ingest(ingestor, replace(trade, payload=correction.payload))
    with pytest.raises(ValueError, match="consecutive"):
        ingest(ingestor, replace(trade, revision=4))
    with pytest.raises(ValueError, match="identity"):
        ingest(ingestor, replace(trade, revision=3, symbol="OTHER"))
    assert (
        ingest(
            ingestor,
            replace(trade, event_id="late", event_time=trade.event_time - (timedelta(seconds=1))),
        )
        == "committed"
    )
    assert saved[-1].out_of_order
    assert len(saved) == 3


def test_commit_failure_does_not_advance_state_and_retry_is_safe() -> None:
    ingestor, saved, _ = setup()
    original_commit = ingestor.commit

    def fail(_: Observation) -> None:
        raise RuntimeError("No effects committed")

    ingestor.commit = fail
    with pytest.raises(RuntimeError):
        ingest(ingestor, messages()[0])
    assert not ingestor.seen
    assert not ingestor.books["SIM"].synchronized
    ingestor.commit = original_commit
    assert ingest(ingestor, messages()[0]) == "committed"
    assert len(saved) == 1


def test_reconnect_invalidates_all_books_before_request_can_fail() -> None:
    ingestor, _, _ = setup()
    snapshot = messages()[0]
    ingest(ingestor, snapshot)
    ingest(ingestor, replace(snapshot, event_id="other-snapshot", symbol="OTHER"))

    def fail_request(symbol: str, connection: int) -> None:
        raise RuntimeError("Transport unavailable")

    ingestor.snapshot_request = fail_request
    with pytest.raises(RuntimeError, match="Transport"):
        ingestor.reconnect()
    assert ingestor.connection == 2
    assert all(not book.synchronized for book in ingestor.books.values())


def test_book_schema_failure_invalidates_previously_synchronized_book() -> None:
    ingestor, saved, requests = setup()
    snapshot, delta, *_ = messages()
    ingest(ingestor, snapshot)
    # Each quantity fits, but their cumulative sum exceeds the shared contract.
    oversized = replace(
        delta,
        payload={
            "bids": [
                {"price_idr": "990.00", "quantity": 214748364700},
                {"price_idr": "985.00", "quantity": 100},
            ],
            "asks": [],
        },
    )
    with pytest.raises(ValidationError):
        ingest(ingestor, oversized)
    assert not ingestor.books["SIM"].synchronized
    assert len(saved) == 1
    assert requests[-1] == ("SIM", 1)


@pytest.mark.parametrize(
    "payload",
    [
        {"price_idr": 1000.0, "quantity": 100, "aggressor": "unknown"},
        {"price_idr": "1000.00", "quantity": 150, "aggressor": "unknown"},
        {"price_idr": "1000.00", "quantity": True, "aggressor": "unknown"},
        {"price_idr": "1000.00", "quantity": 0, "aggressor": "unknown"},
        {"price_idr": "1000.00", "quantity": 100, "aggressor": "guessed"},
    ],
)
def test_invalid_trade_is_rejected_before_commit(payload: dict[str, Any]) -> None:
    ingestor, saved, _ = setup()
    with pytest.raises((ValueError, ValidationError)):
        ingest(ingestor, replace(messages()[2], payload=payload))
    assert not saved
    assert not ingestor.seen


def test_invalid_book_and_correction_invalidate_until_resnapshot() -> None:
    ingestor, saved, requests = setup()
    snapshot, delta, *_ = messages()
    ingest(ingestor, snapshot)
    crossed = replace(
        delta, payload={"bids": [{"price_idr": "1020.00", "quantity": 100}], "asks": []}
    )
    with pytest.raises(ValueError, match="Crossed"):
        ingest(ingestor, crossed)
    assert len(saved) == 1
    assert not ingestor.books["SIM"].synchronized
    assert requests[-1] == ("SIM", 1)
    assert ingest(ingestor, replace(snapshot, revision=2)) == "resync_required"
    ingest(ingestor, messages()[2])
    assert "RESYNC_REQUIRED" in saved[-1].payload["quality"]["reasons"]


def test_no_silent_semantics_switch_or_simulation_live() -> None:
    ingestor, saved, _ = setup()
    trade = messages()[2]
    with pytest.raises(ValueError, match="semantics"):
        ingest(ingestor, replace(trade, profile=replace(SIMULATION_PROFILE, volume_unit="lots")))
    with pytest.raises(ValueError, match="evidence"):
        replace(SIMULATION_PROFILE, origin="market")
    with pytest.raises(ValueError, match="Simulation"):
        FeedIngestor(
            SIMULATION_PROFILE,
            "live",
            lot_shares=lambda *_: 100,
            validate=validate_observation,
            commit=saved.append,
            snapshot_request=lambda *_: None,
        )
    assert not saved


def test_disconnect_candle_validation_and_journal_boundary() -> None:
    ingestor, saved, _ = setup()
    snapshot, _, _, candle, heartbeat = messages()
    ingest(ingestor, snapshot)
    ingest(ingestor, replace(heartbeat, payload={"status": "disconnected"}))
    assert not ingestor.books["SIM"].synchronized
    assert saved[-1].payload["quality"]["feed"] == "disconnected"
    with pytest.raises(ValueError, match="low"):
        ingest(ingestor, replace(candle, payload={**candle.payload, "low_idr": "1020.00"}))
    ingest(ingestor, candle)
    with pytest.raises(ValueError, match="Candle persistence"):
        MarketJournalSink(Journal("invalid", "research", ""))(saved[-1])
    with pytest.raises(ValueError, match="market scope"):
        MarketJournalSink(Journal("invalid", "research", "user"))


def test_invalid_ingest_times_and_fixture_provenance(tmp_path: Path) -> None:
    ingestor, saved, _ = setup()
    with pytest.raises(ValueError, match="Timezone"):
        ingest(ingestor, replace(messages()[2], event_time=NOW.replace(tzinfo=None)))
    with pytest.raises(ValueError, match="availability"):
        ingestor.ingest(
            messages()[2],
            received_at=NOW,
            available_at=NOW,
            processed_at=NOW - timedelta(seconds=1),
        )
    path = tmp_path / "unlabeled.json"
    path.write_text('{"schema":"simulation-feed/1","data_origin":"market","events":[]}')
    with pytest.raises(ValueError, match="simulation"):
        list(simulation_messages(path))
    assert not saved
