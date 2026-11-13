"""PRD 1/2/7: synthetic checks, not licensed vendor qualification."""

from dataclasses import replace
from datetime import timedelta
from typing import Any, Literal

import pytest
from test_feed import NOW, messages, setup

from saham_signal.application.feed import FeedIngestor
from saham_signal.application.feed_quality import FeedSLA, PositionDataDisruption


def send(ingestor: FeedIngestor, index: int, seconds: float, **changes: Any) -> None:
    at = NOW + timedelta(seconds=seconds)
    message = replace(
        messages()[index],
        profile=ingestor.profile,
        event_time=at,
        event_id=f"event-{index}-{seconds}",
        **changes,
    )
    ingestor.ingest(message, received_at=at, available_at=at, processed_at=at)


def ready(
    *,
    delivery: Literal["live", "delayed"] = "live",
    origin: Literal["market", "simulation"] = "market",
) -> FeedIngestor:
    ingestor, _, _ = setup()
    # Test-only market identity; this is not evidence of vendor approval.
    profile = replace(
        ingestor.profile, delivery=delivery, origin=origin, approval_ref="synthetic-test-only"
    )
    ingestor.profile = ingestor.quality_monitor.profile = profile
    send(ingestor, 4, 0)
    send(ingestor, 0, 0)
    return ingestor


def test_quiet_stock_with_healthy_heartbeats_keeps_old_trade_age() -> None:
    ingestor = ready()
    send(ingestor, 2, 0)
    for seconds in range(5, 101, 5):
        send(ingestor, 4, seconds)
        assessment = ingestor.assess_quality("SIM", NOW + timedelta(seconds=seconds))
        assert assessment.status == "live"
        assert assessment.entry_allowed
        assert assessment.trade_age == timedelta(seconds=seconds)
        assert assessment.last_trade_at == NOW


def test_timeout_latches_until_fresh_heartbeat_and_new_snapshot() -> None:
    ingestor = ready()
    warnings: list[PositionDataDisruption] = []
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=10)).entry_allowed
    at = NOW + timedelta(seconds=10, microseconds=1)
    assessment = ingestor.assess_quality("SIM", at, active_positions=["p1"], emit=warnings.append)
    assert assessment.status == "degraded"
    assert "HEARTBEAT_TIMEOUT" in assessment.reasons
    assert not assessment.entry_allowed and not assessment.price_exit_allowed
    assert not ingestor.books["SIM"].synchronized
    ingestor.assess_quality("SIM", at, active_positions=["p1", "p2"], emit=warnings.append)
    assert [warning.position_id for warning in warnings] == ["p1", "p2"]
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=31)).status == "stale"
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=61)).status == "disconnected"
    send(ingestor, 4, 62)
    assert not ingestor.assess_quality("SIM", NOW + timedelta(seconds=62)).entry_allowed
    send(ingestor, 0, 63, sequence=2)
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=63)).entry_allowed
    ingestor.assess_quality(
        "SIM", NOW + timedelta(seconds=73), active_positions=["p1"], emit=warnings.append
    )
    assert len(warnings) == 3
    assert warnings[-1].episode > warnings[0].episode


@pytest.mark.parametrize("delivery,origin", [("delayed", "market"), ("live", "simulation")])
def test_delayed_or_simulated_feed_never_allows_realtime_entry(
    delivery: Literal["live", "delayed"], origin: Literal["market", "simulation"]
) -> None:
    ingestor = ready(delivery=delivery, origin=origin)
    assessment = ingestor.assess_quality("SIM", NOW)
    assert not assessment.entry_allowed and not assessment.price_exit_allowed
    assert ("DELAYED_FEED" if delivery == "delayed" else "SIMULATION") in assessment.reasons


def test_gap_reconnect_and_out_of_order_do_not_restore_entry() -> None:
    ingestor = ready()
    send(ingestor, 1, 1, sequence=3)
    assert "SEQUENCE_GAP" in ingestor.assess_quality("SIM", NOW + timedelta(seconds=1)).reasons
    send(ingestor, 4, 2)
    send(ingestor, 0, 3, sequence=2)
    assert not ingestor.assess_quality("SIM", NOW + timedelta(seconds=3)).entry_allowed
    send(ingestor, 0, 4, sequence=3)
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=4)).entry_allowed
    ingestor.reconnect()
    assert not ingestor.assess_quality("SIM", NOW + timedelta(seconds=4)).entry_allowed
    send(ingestor, 0, 5, connection=2)
    send(ingestor, 4, 6, connection=2)
    assert not ingestor.assess_quality("SIM", NOW + timedelta(seconds=6)).entry_allowed
    send(ingestor, 0, 7, connection=2, sequence=2)
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=7)).entry_allowed
    assert ingestor.books["SIM"].bids == {"1000.00": 5}


def test_disconnect_warns_without_generating_exit_and_retry_failed_sink() -> None:
    ingestor = ready()
    send(ingestor, 4, 1, payload={"status": "disconnected"})
    at = NOW + timedelta(seconds=1)

    def fail(_: PositionDataDisruption) -> None:
        raise RuntimeError("sink unavailable")

    with pytest.raises(RuntimeError, match="sink"):
        ingestor.assess_quality("SIM", at, active_positions=["open-position"], emit=fail)
    warnings: list[PositionDataDisruption] = []
    assessment = ingestor.assess_quality(
        "SIM", at, active_positions=["open-position"], emit=warnings.append
    )
    assert assessment.status == "disconnected"
    assert not assessment.price_exit_allowed
    assert warnings[0].position_id == "open-position"
    assert not hasattr(warnings[0], "price")


def test_sla_validation_monotonic_clock_and_source_lag() -> None:
    with pytest.raises(ValueError, match="SLA"):
        FeedSLA(heartbeat_timeout=timedelta(seconds=90))
    ingestor = ready()
    ingestor.quality_monitor.sla = FeedSLA(provider_lag=timedelta(seconds=2))
    assert not ingestor.assess_quality("SIM", NOW + timedelta(seconds=3)).entry_allowed
    with pytest.raises(ValueError, match="monotonic"):
        ingestor.assess_quality("SIM", NOW)


def test_duplicate_old_heartbeat_and_uncommitted_data_cannot_refresh_health() -> None:
    ingestor = ready()
    heartbeat = replace(messages()[4], profile=ingestor.profile, event_time=NOW, event_id="old")
    ingestor.ingest(heartbeat, received_at=NOW, available_at=NOW, processed_at=NOW)
    at = NOW + timedelta(seconds=11)
    assert (
        ingestor.ingest(heartbeat, received_at=at, available_at=at, processed_at=at) == "duplicate"
    )
    assert not ingestor.assess_quality("SIM", at).entry_allowed

    def fail(_: object) -> None:
        raise RuntimeError("commit failed")

    ingestor.commit = fail
    with pytest.raises(RuntimeError, match="commit"):
        send(ingestor, 4, 12)
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=12)).last_heartbeat_at == NOW


def test_symbols_are_isolated_and_unknown_feed_is_closed() -> None:
    ingestor = ready()
    assessment = ingestor.assess_quality("OTHER", NOW)
    assert assessment.status == "disconnected" and not assessment.entry_allowed
    assert ingestor.assess_quality("SIM", NOW).entry_allowed


def test_stale_or_out_of_order_book_requests_recovery_on_next_poll() -> None:
    ingestor = ready()
    delta = replace(
        messages()[1],
        profile=ingestor.profile,
        sequence=2,
        event_time=NOW - timedelta(seconds=1),
        event_id="late-delta",
    )
    at = NOW + timedelta(seconds=1)
    ingestor.ingest(delta, received_at=at, available_at=at, processed_at=at)
    assessment = ingestor.assess_quality("SIM", at)
    assert not assessment.entry_allowed
    assert not ingestor.books["SIM"].synchronized
    send(ingestor, 0, 2, sequence=3)
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=2)).entry_allowed


def test_position_warning_is_emitted_even_when_snapshot_transport_fails() -> None:
    ingestor = ready()

    def fail_request(_: str, __: int) -> None:
        raise RuntimeError("transport unavailable")

    ingestor.snapshot_request = fail_request
    warnings: list[PositionDataDisruption] = []
    with pytest.raises(RuntimeError, match="transport"):
        ingestor.assess_quality(
            "SIM", NOW + timedelta(seconds=11), active_positions=["p1"], emit=warnings.append
        )
    assert len(warnings) == 1
    assert not ingestor.books["SIM"].synchronized


def test_delayed_warning_is_not_repeated_by_each_snapshot() -> None:
    ingestor = ready(delivery="delayed")
    warnings: list[PositionDataDisruption] = []
    ingestor.assess_quality("SIM", NOW, active_positions=["p1"], emit=warnings.append)
    send(ingestor, 0, 1, sequence=2)
    ingestor.assess_quality(
        "SIM", NOW + timedelta(seconds=1), active_positions=["p1"], emit=warnings.append
    )
    assert len(warnings) == 1


def test_snapshot_from_before_timeout_cannot_recover_even_within_lag_budget() -> None:
    ingestor = ready()
    ingestor.assess_quality("SIM", NOW + timedelta(seconds=11))
    send(ingestor, 4, 12)
    at = NOW + timedelta(seconds=13)
    old_snapshot = replace(
        messages()[0],
        profile=ingestor.profile,
        sequence=2,
        event_id="pre-timeout",
        event_time=NOW + timedelta(seconds=9),
    )
    ingestor.ingest(old_snapshot, received_at=at, available_at=at, processed_at=at)
    assert not ingestor.assess_quality("SIM", at).entry_allowed
    send(ingestor, 0, 14, sequence=3)
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=14)).entry_allowed


def test_disconnect_with_equal_heartbeat_time_needs_new_healthy_heartbeat() -> None:
    ingestor = ready()
    at = NOW + timedelta(seconds=1)
    disconnect = replace(
        messages()[4],
        profile=ingestor.profile,
        event_time=NOW,
        event_id="disconnect-same-time",
        payload={"status": "disconnected"},
    )
    ingestor.ingest(disconnect, received_at=at, available_at=at, processed_at=at)
    send(ingestor, 0, 2, sequence=2)
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=2)).status == "disconnected"
    send(ingestor, 4, 3)
    send(ingestor, 0, 4, sequence=3)
    assert ingestor.assess_quality("SIM", NOW + timedelta(seconds=4)).entry_allowed
