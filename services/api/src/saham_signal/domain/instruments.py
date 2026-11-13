"""Immutable point-in-time references. No built-in production market data."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

# WIB has no DST. A fixed offset also works on Windows without system tzdata.
JAKARTA = timezone(timedelta(hours=7), "Asia/Jakarta")


class ReferenceUnavailable(ValueError):
    """Missing, ambiguous, or unsupported reference: entry must be withheld."""


def aware(value: datetime) -> None:
    if value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")


def positive_integer(value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError("Positive integer required (IDR/shares)")


@dataclass(frozen=True)
class Version:
    id: str
    effective_from: datetime
    effective_to: datetime
    available_at: datetime
    source_ref: str
    data_origin: Literal["simulation", "licensed"]

    def __post_init__(self) -> None:
        for stamp in (self.effective_from, self.effective_to, self.available_at):
            aware(stamp)
        if self.effective_from >= self.effective_to or not self.id or not self.source_ref:
            raise ValueError("Version needs provenance and a nonempty effective interval")
        if self.data_origin not in ("simulation", "licensed"):
            raise ValueError("Unknown data origin")

    def visible(self, at: datetime, known_at: datetime) -> bool:
        aware(at)
        aware(known_at)
        return self.effective_from <= at < self.effective_to and self.available_at <= known_at


@dataclass(frozen=True)
class TickBand:
    lower_idr: int
    upper_idr: int | None
    step_idr: int

    def __post_init__(self) -> None:
        positive_integer(self.lower_idr)
        positive_integer(self.step_idr)
        if self.upper_idr is not None:
            positive_integer(self.upper_idr)
        if self.upper_idr is not None and self.upper_idr <= self.lower_idr:
            raise ValueError("Empty tick band")


@dataclass(frozen=True)
class InstrumentRule:
    version: Version
    symbol: str
    board: str
    market: str
    lot_shares: int
    ticks: tuple[TickBand, ...]
    limit_rule_id: str
    calendar_id: str

    def __post_init__(self) -> None:
        positive_integer(self.lot_shares)
        if not all((self.symbol, self.board, self.market, self.limit_rule_id, self.calendar_id)):
            raise ValueError("Incomplete instrument rule")
        if not self.ticks or self.ticks[0].lower_idr != 1:
            raise ValueError("Tick bands must cover positive IDR prices")
        for left, right in zip(self.ticks, self.ticks[1:], strict=False):
            if left.upper_idr != right.lower_idr:
                raise ValueError("Tick bands must be ordered and contiguous")
        if self.ticks[-1].upper_idr is not None:
            raise ValueError("Final tick band must be unbounded")

    def tick_size(self, reference_price_idr: int) -> int:
        """Use the day's authoritative reference price, never the proposed order price."""
        positive_integer(reference_price_idr)
        for band in self.ticks:
            if band.upper_idr is None or reference_price_idr < band.upper_idr:
                return band.step_idr
        raise ReferenceUnavailable("unsupported_tick")


@dataclass(frozen=True)
class Session:
    name: str
    opens: time
    closes: time
    mechanism: str = "continuous"

    def __post_init__(self) -> None:
        if self.opens.tzinfo or self.closes.tzinfo or self.opens >= self.closes:
            raise ValueError("Session must be a same-day local half-open interval")
        if not self.name or not self.mechanism:
            raise ValueError("Session metadata required")


@dataclass(frozen=True)
class CalendarDay:
    version: Version
    calendar_id: str
    trading_date: date
    sessions: tuple[Session, ...]  # Empty explicitly means holiday/closed day.

    def __post_init__(self) -> None:
        if not self.calendar_id:
            raise ValueError("Calendar ID required")
        for left, right in zip(self.sessions, self.sessions[1:], strict=False):
            if left.closes > right.opens:
                raise ValueError("Sessions must be ordered and non-overlapping")


@dataclass(frozen=True)
class CorporateAction:
    id: str
    kind: str
    ex_date: date
    source_ref: str

    def __post_init__(self) -> None:
        if not all((self.id, self.kind, self.source_ref)):
            raise ValueError("Corporate action requires identity, type and provenance")


@dataclass(frozen=True)
class TradingState:
    version: Version
    symbol: str
    market: str
    status: Literal["active", "suspended", "delisted", "unknown"]
    corporate_actions: tuple[CorporateAction, ...]
    actions_resolved: bool
    # Active + empty actions is an explicit complete snapshot, not missing events.


@dataclass(frozen=True)
class DailyLimits:
    version: Version
    symbol: str
    market: str
    trading_date: date
    rule_id: str
    reference_price_idr: int
    lower_idr: int
    upper_idr: int

    def __post_init__(self) -> None:
        for value in (self.reference_price_idr, self.lower_idr, self.upper_idr):
            positive_integer(value)
        if self.lower_idr > self.upper_idr or not self.rule_id:
            raise ValueError("Invalid daily price limits")
