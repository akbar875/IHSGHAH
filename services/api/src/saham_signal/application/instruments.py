"""Shared reference lookup/entry eligibility for replay, API, and worker callers."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from saham_signal.domain.instruments import (
    JAKARTA,
    CalendarDay,
    DailyLimits,
    InstrumentRule,
    ReferenceUnavailable,
    TradingState,
    Version,
    aware,
)
from saham_signal.domain.mode import Mode


class Versioned(Protocol):
    @property
    def version(self) -> Version: ...


def select[T: Versioned](rows: Sequence[T], at: datetime, known_at: datetime) -> T:
    matches = [row for row in rows if row.version.visible(at, known_at)]
    if len(matches) != 1:
        raise ReferenceUnavailable("missing_or_ambiguous_reference")
    return matches[0]


class ReferenceRepository(Protocol):
    def rules(self, symbol: str, market: str) -> Sequence[InstrumentRule]: ...
    def days(self, calendar_id: str, day: date) -> Sequence[CalendarDay]: ...
    def states(self, symbol: str, market: str) -> Sequence[TradingState]: ...
    def limits(self, symbol: str, market: str, day: date) -> Sequence[DailyLimits]: ...


@dataclass(frozen=True)
class ReferenceSnapshot:
    rule: InstrumentRule
    day: CalendarDay
    state: TradingState
    limits: DailyLimits

    @property
    def versions(self) -> tuple[Version, ...]:
        return (self.rule.version, self.day.version, self.state.version, self.limits.version)


def lookup(
    repository: ReferenceRepository, symbol: str, market: str, at: datetime, known_at: datetime
) -> ReferenceSnapshot:
    aware(at)
    aware(known_at)
    if known_at > at:
        raise ReferenceUnavailable("future_knowledge")
    day = at.astimezone(JAKARTA).date()
    rule = select(repository.rules(symbol, market), at, known_at)
    calendar = select(repository.days(rule.calendar_id, day), at, known_at)
    state = select(repository.states(symbol, market), at, known_at)
    limits = select(repository.limits(symbol, market, day), at, known_at)
    # Check adapter results as well: never trust an incorrectly scoped repository.
    if (
        (rule.symbol, rule.market) != (symbol, market)
        or (state.symbol, state.market) != (symbol, market)
        or (limits.symbol, limits.market) != (symbol, market)
        or calendar.calendar_id != rule.calendar_id
        or calendar.trading_date != day
        or limits.trading_date != day
        or limits.rule_id != rule.limit_rule_id
    ):
        raise ReferenceUnavailable("inconsistent_reference")
    return ReferenceSnapshot(rule, calendar, state, limits)


@dataclass(frozen=True)
class EntryEligibility:
    allowed: bool
    reason: str
    reference_versions: tuple[str, ...] = ()


def check_entry(
    repository: ReferenceRepository,
    *,
    symbol: str,
    at: datetime,
    known_at: datetime,
    price_idr: int,
    shares: int,
    mode: Mode,
    market: str = "regular",
) -> EntryEligibility:
    """Reference checks only; allowed does not authorize live trading or pass G0/risk gates."""
    if mode not in ("research", "paper", "live"):
        return EntryEligibility(False, "unsupported_mode")
    if type(price_idr) is not int or type(shares) is not int or min(price_idr, shares) <= 0:
        return EntryEligibility(False, "invalid_order")
    try:
        snapshot = lookup(repository, symbol, market, at, known_at)
    except ReferenceUnavailable as exc:
        return EntryEligibility(False, str(exc))
    rule, day, state, limits = snapshot.rule, snapshot.day, snapshot.state, snapshot.limits
    versions = tuple(version.id for version in snapshot.versions)

    def result(reason: str) -> EntryEligibility:
        return EntryEligibility(reason == "eligible", reason, versions)

    if mode == "live" and any(v.data_origin != "licensed" for v in snapshot.versions):
        return result("simulation_not_live")
    if market != "regular" or rule.board not in ("main", "development", "new_economy"):
        return result("unsupported_board_or_market")
    if state.status != "active":
        return result("instrument_not_active")
    if any(
        action.kind not in ("split", "reverse_split", "cash_dividend", "rights", "bonus")
        for action in state.corporate_actions
    ):
        return result("unsupported_corporate_action")
    if not state.actions_resolved:
        return result("unresolved_corporate_action")
    local_time = at.astimezone(JAKARTA).time()
    session = next((s for s in day.sessions if s.opens <= local_time < s.closes), None)
    if session is None:
        return result("market_closed")
    if session.mechanism != "continuous":
        return result("unsupported_session")
    if shares % rule.lot_shares:
        return result("invalid_lot")
    tick = rule.tick_size(limits.reference_price_idr)
    if price_idr % tick:
        return result("invalid_tick")
    if not limits.lower_idr <= price_idr <= limits.upper_idr:
        return result("outside_price_limits")
    return result("eligible")
