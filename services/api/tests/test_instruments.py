"""All instrument/calendar/price data here is synthetic simulation, not a market feed."""

from dataclasses import replace
from datetime import date, datetime, time

import pytest

from saham_signal.adapters.instrument_references import MemoryReferences
from saham_signal.application.instruments import EntryEligibility, check_entry, lookup
from saham_signal.domain.instruments import (
    CalendarDay,
    CorporateAction,
    DailyLimits,
    InstrumentRule,
    ReferenceUnavailable,
    Session,
    TickBand,
    TradingState,
    Version,
)

AT = datetime.fromisoformat("2026-11-13T02:30:00+00:00")  # Friday, 09:30 WIB


def stamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def version(name: str) -> Version:
    return Version(
        name,
        stamp("2026-11-12T17:00:00Z"),
        stamp("2026-11-13T17:00:00Z"),
        stamp("2026-11-12T16:00:00Z"),
        "simulation:SS-009",
        "simulation",
    )


@pytest.fixture
def refs() -> MemoryReferences:
    ticks = (
        TickBand(1, 200, 1),
        TickBand(200, 500, 2),
        TickBand(500, 2000, 5),
        TickBand(2000, 5000, 10),
        TickBand(5000, None, 25),
    )
    return MemoryReferences(
        (
            InstrumentRule(
                version("rule-1"), "SIM", "main", "regular", 100, ticks, "limit-1", "IDX"
            ),
        ),
        (
            CalendarDay(
                version("calendar-1"),
                "IDX",
                date(2026, 11, 13),
                (
                    Session("preopen", time(8, 45), time(9), "auction"),
                    Session("I", time(9), time(11, 30)),
                    Session("II", time(14), time(15, 50)),
                ),
            ),
        ),
        (TradingState(version("state-1"), "SIM", "regular", "active", (), True),),
        (
            DailyLimits(
                version("limits-1"),
                "SIM",
                "regular",
                date(2026, 11, 13),
                "limit-1",
                1000,
                850,
                1250,
            ),
        ),
    )


def decision(
    refs: MemoryReferences, at: datetime = AT, price: int = 1000, shares: int = 100
) -> EntryEligibility:
    return check_entry(
        refs, symbol="SIM", at=at, known_at=at, price_idr=price, shares=shares, mode="research"
    )


def test_lookup_timezone_and_provenance(refs: MemoryReferences) -> None:
    assert lookup(refs, "SIM", "regular", AT, AT) == lookup(
        refs, "SIM", "regular", AT.astimezone(stamp("2026-11-13T09:30:00+07:00").tzinfo), AT
    )
    assert decision(refs).allowed
    assert decision(refs).reference_versions == ("rule-1", "calendar-1", "state-1", "limits-1")
    # UTC Nov 12 is already Nov 13 in Jakarta; a UTC-date calendar lookup would fail.
    assert decision(refs, stamp("2026-11-12T18:00:00Z")).reason == "market_closed"
    assert not decision(refs, stamp("2026-11-13T17:00:00Z")).allowed


@pytest.mark.parametrize(
    ("price", "step"),
    [
        (1, 1),
        (199, 1),
        (200, 2),
        (499, 2),
        (500, 5),
        (1999, 5),
        (2000, 10),
        (4999, 10),
        (5000, 25),
        (10000, 25),
    ],
)
def test_tick_band_boundaries(refs: MemoryReferences, price: int, step: int) -> None:
    assert refs.instrument_rules[0].tick_size(price) == step


@pytest.mark.parametrize(
    ("clock", "reason"),
    [
        ("08:44:59", "market_closed"),
        ("08:45:00", "unsupported_session"),
        ("09:00:00", "eligible"),
        ("11:29:59.999999", "eligible"),
        ("11:30:00", "market_closed"),
        ("13:59:59", "market_closed"),
        ("14:00:00", "eligible"),
        ("15:49:59.999999", "eligible"),
        ("15:50:00", "market_closed"),
    ],
)
def test_friday_session_boundaries(refs: MemoryReferences, clock: str, reason: str) -> None:
    assert decision(refs, stamp(f"2026-11-13T{clock}+07:00")).reason == reason


@pytest.mark.parametrize(
    ("price", "shares", "reason"),
    [
        (850, 100, "eligible"),
        (1250, 100, "eligible"),
        (845, 100, "outside_price_limits"),
        (1255, 100, "outside_price_limits"),
        (1001, 100, "invalid_tick"),
        (1000, 99, "invalid_lot"),
        (0, 100, "invalid_order"),
        (1000, -100, "invalid_order"),
        (True, 100, "invalid_order"),
    ],
)
def test_order_boundaries(refs: MemoryReferences, price: int, shares: int, reason: str) -> None:
    assert decision(refs, price=price, shares=shares).reason == reason


def test_tick_uses_daily_reference_not_order_price(refs: MemoryReferences) -> None:
    limits = replace(refs.daily_limits[0], reference_price_idr=199, lower_idr=150, upper_idr=250)
    assert decision(replace(refs, daily_limits=(limits,)), price=201).allowed


def test_missing_ambiguous_and_future_information(refs: MemoryReferences) -> None:
    for field in ("instrument_rules", "calendar_days", "trading_states", "daily_limits"):
        rows = getattr(refs, field)
        assert not decision(replace(refs, **{field: ()})).allowed
        assert not decision(replace(refs, **{field: rows + rows})).allowed
        late = replace(rows[0], version=replace(rows[0].version, available_at=AT.replace(hour=3)))
        assert not decision(replace(refs, **{field: (late,)})).allowed
    with pytest.raises(ReferenceUnavailable, match="future_knowledge"):
        lookup(refs, "SIM", "regular", AT, AT.replace(hour=3))
    with pytest.raises(ValueError, match="Timezone-aware"):
        lookup(refs, "SIM", "regular", AT.replace(tzinfo=None), AT)


def test_rule_and_limit_change_at_exact_effective_boundary(refs: MemoryReferences) -> None:
    boundary = AT.replace(hour=3)
    old = replace(refs.instrument_rules[0], version=replace(version("old"), effective_to=boundary))
    new = replace(
        old,
        version=replace(version("new"), effective_from=boundary),
        lot_shares=200,
        limit_rule_id="limit-2",
    )
    old_limit = replace(refs.daily_limits[0], version=replace(version("l1"), effective_to=boundary))
    new_limit = replace(
        old_limit,
        version=replace(version("l2"), effective_from=boundary),
        rule_id="limit-2",
        upper_idr=1100,
    )
    changed = replace(refs, instrument_rules=(old, new), daily_limits=(old_limit, new_limit))
    assert decision(changed).allowed
    assert decision(changed, boundary).reason == "invalid_lot"
    assert decision(changed, boundary, shares=200, price=1200).reason == "outside_price_limits"
    assert decision(changed, boundary, shares=200).reference_versions[0] == "new"


def test_suspension_resume_and_actions(refs: MemoryReferences) -> None:
    start, end = AT.replace(hour=3, minute=0), AT.replace(hour=4, minute=0)
    active = refs.trading_states[0]
    states = (
        replace(active, version=replace(version("before"), effective_to=start)),
        replace(
            active,
            version=replace(version("suspended"), effective_from=start, effective_to=end),
            status="suspended",
        ),
        replace(active, version=replace(version("resumed"), effective_from=end)),
    )
    changed = replace(refs, trading_states=states)
    assert decision(changed).allowed
    assert decision(changed, start).reason == "instrument_not_active"
    assert decision(changed, end).allowed
    action = replace(
        active,
        corporate_actions=(
            CorporateAction("split-1", "split", date(2026, 11, 13), "simulation:1"),
        ),
        actions_resolved=False,
    )
    assert decision(replace(refs, trading_states=(action,))).reason == "unresolved_corporate_action"
    assert decision(replace(refs, trading_states=(replace(action, actions_resolved=True),))).allowed


def test_board_market_calendar_and_simulation_rejections(refs: MemoryReferences) -> None:
    for board in ("acceleration", "special_monitoring", "unknown"):
        rules = (replace(refs.instrument_rules[0], board=board),)
        assert (
            decision(replace(refs, instrument_rules=rules)).reason == "unsupported_board_or_market"
        )
    holiday = replace(refs.calendar_days[0], sessions=())
    assert decision(replace(refs, calendar_days=(holiday,))).reason == "market_closed"
    assert not decision(MemoryReferences()).allowed
    assert (
        check_entry(
            refs, symbol="SIM", at=AT, known_at=AT, price_idr=1000, shares=100, mode="live"
        ).reason
        == "simulation_not_live"
    )
    assert (
        check_entry(
            refs,
            symbol="SIM",
            at=AT,
            known_at=AT,
            price_idr=1000,
            shares=100,
            mode="research",
            market="negotiated",
        ).allowed
        is False
    )
    bad = replace(refs.daily_limits[0], rule_id="other-version")
    assert decision(replace(refs, daily_limits=(bad,))).reason == "inconsistent_reference"


def test_calendar_revision_changes_session_boundary(refs: MemoryReferences) -> None:
    boundary = AT.replace(hour=3, minute=0)
    day = refs.calendar_days[0]
    old = replace(day, version=replace(version("c1"), effective_to=boundary))
    new = replace(
        day,
        version=replace(version("c2"), effective_from=boundary),
        sessions=(Session("shortened", time(9), time(10)),),
    )
    changed = replace(refs, calendar_days=(old, new))
    assert decision(changed).allowed
    assert decision(changed, boundary).reason == "market_closed"
    assert decision(changed, boundary).reference_versions[1] == "c2"


def test_unsupported_actions_and_inactive_statuses(refs: MemoryReferences) -> None:
    state = refs.trading_states[0]
    for status in ("suspended", "delisted", "unknown"):
        changed = replace(refs, trading_states=(replace(state, status=status),))
        assert decision(changed).reason == "instrument_not_active"
    action = CorporateAction("unknown-1", "unknown", date(2026, 11, 13), "simulation:1")
    changed = replace(refs, trading_states=(replace(state, corporate_actions=(action,)),))
    assert decision(changed).reason == "unsupported_corporate_action"


def test_malformed_reference_rejected_at_construction(refs: MemoryReferences) -> None:
    with pytest.raises(ValueError):
        replace(version("bad"), effective_to=version("bad").effective_from)
    with pytest.raises(ValueError):
        replace(refs.instrument_rules[0], ticks=(TickBand(1, 200, 1), TickBand(500, None, 5)))
    with pytest.raises(ValueError):
        replace(refs.instrument_rules[0], lot_shares=0)
    with pytest.raises(ValueError):
        replace(refs.daily_limits[0], lower_idr=2000)
    with pytest.raises(ValueError):
        Session("overnight", time(23), time(1))
    with pytest.raises(ValueError):
        replace(
            refs.calendar_days[0],
            sessions=(Session("A", time(9), time(11)), Session("B", time(10), time(12))),
        )
