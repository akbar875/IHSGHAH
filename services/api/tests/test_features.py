"""SS-013 acceptance using synthetic normalized data, not vendor certification."""

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_UP, Decimal, Inexact, localcontext
from typing import Any

import pytest

from saham_signal.adapters.features import FeatureConsumer
from saham_signal.adapters.feed import SIMULATION_PROFILE, validate_observation
from saham_signal.application.features import FeatureEngine, FeaturePolicy
from saham_signal.application.feed import FeedIngestor, FeedMessage, Observation, stamp
from saham_signal.application.feed_quality import FeedQuality, FeedSLA

NOW = datetime(2026, 11, 13, 3, 5, tzinfo=UTC)


def setup() -> tuple[FeatureEngine, FeatureConsumer, list[Observation], FeedIngestor]:
    engine = FeatureEngine(SIMULATION_PROFILE, "research", FeaturePolicy())
    consumer = FeatureConsumer(engine)
    saved: list[Observation] = []

    def commit(observation: Observation) -> None:
        saved.append(observation)
        consumer.committed(observation)

    feed = FeedIngestor(
        SIMULATION_PROFILE,
        "research",
        lot_shares=lambda *_: 100,
        validate=validate_observation,
        commit=commit,
        snapshot_request=lambda *_: None,
    )
    return engine, consumer, saved, feed


def add(
    feed: FeedIngestor,
    identity: str,
    seconds: int,
    *,
    lots: int = 1,
    aggressor: str = "buyer",
    price: str = "1000.00",
    revision: int = 1,
    available: datetime = NOW,
    kind: Any = "trade",
    payload: dict[str, Any] | None = None,
) -> None:
    message = FeedMessage(
        SIMULATION_PROFILE,
        1,
        identity,
        "SIM",
        kind,
        seconds + 1000000,
        NOW + timedelta(seconds=seconds),
        None,
        payload
        if payload is not None
        else {
            "price_idr": price,
            "quantity": lots * 100,
            "aggressor": aggressor,
        },
        revision,
    )
    feed.ingest(message, received_at=available, available_at=available, processed_at=available)


def test_numeric_features_and_pressure_are_distinct_from_book() -> None:
    engine, _, saved, feed = setup()
    add(feed, "a", -20, lots=6)
    add(feed, "b", -10, lots=2, aggressor="seller", price="1100.00")
    add(feed, "c", -5, lots=2, aggressor="unknown", price="990.00")
    add(feed, "heartbeat", 0, kind="heartbeat", payload={"status": "healthy"})
    add(
        feed,
        "book",
        0,
        kind="book_snapshot",
        payload={
            "bids": [{"price_idr": "980.00", "quantity": 100}],
            "asks": [{"price_idr": "990.00", "quantity": 900}],
        },
    )
    quality = feed.assess_quality("SIM", NOW)
    result = engine.snapshot("SIM", NOW, quality=quality)
    assert result.return_fraction == Decimal("-0.01")
    assert result.volatility_fraction == Decimal("0.1")
    assert result.volume_lots == 10
    assert result.classification_coverage == Decimal("0.8")
    assert result.buy_pressure == Decimal("0.75")
    assert result.sell_pressure == Decimal("0.25")
    assert result.unknown_lots == 2
    assert result.book_imbalance == Decimal("0.1")
    assert result.spread_idr == Decimal("10")
    assert (result.bid_depth_lots, result.ask_depth_lots) == (1, 9)
    assert result.available_levels == 1 and result.limited_depth
    assert result.pressure_method == "feed-aggressor-v1"
    assert not any("investor" in key for key in asdict(result))
    assert saved[-1].payload["data_origin"] == "simulation"
    replay, replay_consumer, _, _ = setup()
    for observation in reversed(saved):
        replay_consumer.committed(observation)
    assert replay.snapshot("SIM", NOW, quality=quality) == result


def test_every_cutoff_replay_stream_parity_late_events_corrections_duplicates() -> None:
    stream, _, saved, feed = setup()
    add(feed, "old", -40, available=NOW - timedelta(seconds=30))
    add(feed, "late", -50, lots=3, available=NOW)
    add(feed, "old", -40, lots=10, revision=2, available=NOW + timedelta(seconds=5))
    add(feed, "future", 20, lots=100, available=NOW + timedelta(seconds=6))
    for cutoff in (
        NOW - timedelta(seconds=31),
        NOW - timedelta(seconds=1),
        NOW,
        NOW + timedelta(seconds=5),
        NOW + timedelta(seconds=30),
    ):
        replay, consumer, _, _ = setup()
        for observation in reversed(saved):
            if observation.available_at <= cutoff:
                consumer.journal_row(
                    {
                        "kind": "MarketEvent",
                        "user_id": "",
                        "mode": "research",
                        "payload": observation.payload,
                        "version": observation.message.revision,
                    }
                )
                consumer.committed(observation)  # retry is idempotent
        assert replay.snapshot("SIM", cutoff) == stream.snapshot("SIM", cutoff)
    assert stream.snapshot("SIM", NOW - timedelta(seconds=1)).volume_lots == 1
    assert stream.snapshot("SIM", NOW).volume_lots == 4
    assert stream.snapshot("SIM", NOW + timedelta(seconds=6)).volume_lots == 13
    assert stream.snapshot("OTHER", NOW).volume_lots == 0


@pytest.mark.parametrize(
    "known,unknown,reason",
    [(1, 9, "INSUFFICIENT_COVERAGE"), (0, 5, "INSUFFICIENT_COVERAGE"), (0, 0, "NO_VOLUME")],
)
def test_pressure_hidden_for_unknown_and_empty(known: int, unknown: int, reason: str) -> None:
    engine, _, _, feed = setup()
    if known:
        add(feed, "known", -2, lots=known)
    if unknown:
        add(feed, "ambiguous", -1, lots=unknown, aggressor="unknown")
    result = engine.snapshot("SIM", NOW)
    assert result.buy_pressure is None and result.sell_pressure is None
    assert result.pressure_hidden_reason == reason


def test_relative_volume_same_wib_window_only_known_prior_sessions() -> None:
    engine, consumer, saved, feed = setup()
    add(feed, "history", -86401, lots=5)
    add(feed, "now", -1, lots=10)
    yesterday = (NOW - timedelta(days=1)).date()
    assert engine.snapshot("SIM", NOW, baseline_sessions=[yesterday]).relative_volume == 2
    assert engine.snapshot("SIM", NOW).relative_volume is None
    assert (
        engine.snapshot(
            "SIM", NOW, baseline_sessions=[yesterday - timedelta(days=1)]
        ).relative_volume
        is None
    )
    with pytest.raises(ValueError):
        engine.snapshot("SIM", NOW, baseline_sessions=[NOW.date()])
    correction = deepcopy(saved[0].payload)
    correction["available_at"] = stamp(NOW + timedelta(seconds=1))
    correction["processed_at"] = correction["available_at"]
    correction["payload"]["lots"] = 10
    consumer.event(correction, 2)
    assert engine.snapshot("SIM", NOW, baseline_sessions=[yesterday]).relative_volume == 2
    assert (
        engine.snapshot(
            "SIM", NOW + timedelta(seconds=1), baseline_sessions=[yesterday]
        ).relative_volume
        == 1
    )


def test_book_requires_current_healthy_assessment_and_fresh_full_snapshot() -> None:
    engine, _, _, feed = setup()
    add(feed, "heartbeat", 0, kind="heartbeat", payload={"status": "healthy"})
    add(
        feed,
        "book",
        0,
        kind="book_snapshot",
        payload={
            "bids": [{"price_idr": "980.00", "quantity": 100}],
            "asks": [{"price_idr": "990.00", "quantity": 900}],
        },
    )
    quality = feed.assess_quality("SIM", NOW)
    assert engine.snapshot("SIM", NOW).book_imbalance is None
    for invalid in (
        replace(quality, status="degraded"),
        replace(quality, symbol="OTHER"),
        replace(quality, as_of=NOW - timedelta(seconds=1)),
    ):
        assert engine.snapshot("SIM", NOW, quality=invalid).bid_depth_lots is None
    later = NOW + timedelta(seconds=11)
    assert (
        engine.snapshot("SIM", later, quality=replace(quality, as_of=later)).book_hidden_reason
        == "STALE_BOOK"
    )
    monitor = FeedQuality(SIMULATION_PROFILE, FeedSLA(), "research")
    assert engine.snapshot("SIM", NOW, quality=monitor.assess("SIM", NOW)).spread_idr is None


def test_isolation_validation_aliasing_and_decimal_context() -> None:
    engine, consumer, saved, feed = setup()
    add(feed, "a", -2, lots=6)
    add(feed, "b", -1, lots=1, aggressor="seller", price="1100.00")
    expected = engine.snapshot("SIM", NOW)
    for key, value in (("source", "other"), ("mode", "paper"), ("data_origin", "market")):
        event = deepcopy(saved[0].payload)
        event[key] = value
        with pytest.raises(ValueError):
            consumer.event(event, 1)
    conflict = deepcopy(saved[0].payload)
    conflict["payload"]["lots"] = 99
    with pytest.raises(ValueError):
        consumer.event(conflict, 1)
    saved[0].payload["payload"]["lots"] = 50
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_UP
        context.traps[Inexact] = True
        assert engine.snapshot("SIM", NOW) == expected
    with pytest.raises(ValueError):
        engine.snapshot("SIM", NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        FeatureEngine(SIMULATION_PROFILE, "live", FeaturePolicy())
    with pytest.raises(ValueError):
        FeaturePolicy(minimum_coverage=Decimal("NaN"))


def test_window_boundaries_and_correction_moving_event_into_future() -> None:
    engine, consumer, saved, feed = setup()
    add(feed, "excluded-start", -300, lots=100)
    add(feed, "included", -299, lots=2)
    add(feed, "included-end", 0, lots=3)
    assert engine.snapshot("SIM", NOW).volume_lots == 5
    correction = deepcopy(saved[1].payload)
    correction["event_time"] = stamp(NOW + timedelta(seconds=1))
    consumer.event(correction, 2)
    assert engine.snapshot("SIM", NOW).volume_lots == 3
