"""Fail-closed feed policy. Runtime must poll even when no messages arrive.

This is an input eligibility check, never authorization to trade or an exit engine.
All times are explicit so simulation and runtime use the same policy.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

from saham_signal.domain.instruments import aware
from saham_signal.domain.mode import Mode

if TYPE_CHECKING:
    from saham_signal.application.feed import FeedProfile, Observation


@dataclass(frozen=True)
class FeedSLA:
    """Provisional defaults, not an approved vendor SLA; pin evidence per session."""

    reference: str = "PRD-8/provisional"
    heartbeat_timeout: timedelta = timedelta(seconds=10)
    stale_after: timedelta = timedelta(seconds=30)
    disconnected_after: timedelta = timedelta(seconds=60)
    provider_lag: timedelta = timedelta(seconds=10)
    clock_skew: timedelta = timedelta(seconds=1)

    def __post_init__(self) -> None:
        if not self.reference or not (
            timedelta(0) < self.heartbeat_timeout <= self.stale_after <= self.disconnected_after
        ):
            raise ValueError("SLA requires evidence and ordered positive thresholds")
        if self.provider_lag <= timedelta(0) or self.clock_skew < timedelta(0):
            raise ValueError("Invalid provider lag or clock skew threshold")


@dataclass(frozen=True)
class FeedAssessment:
    symbol: str
    as_of: datetime
    status: Literal["live", "delayed", "degraded", "stale", "disconnected"]
    reasons: tuple[str, ...]
    last_heartbeat_at: datetime | None
    last_trade_at: datetime | None
    trade_age: timedelta | None
    entry_allowed: bool
    price_exit_allowed: bool
    sla_reference: str
    mode: Mode
    data_origin: Literal["simulation", "market"]


@dataclass(frozen=True)
class PositionDataDisruption:
    """Warning only: contains no price, order, fill, or position mutation."""

    source: str
    symbol: str
    position_id: str
    episode: int
    assessment: FeedAssessment


@dataclass
class StreamHealth:
    heartbeat: datetime | None = None
    heartbeat_status: str = "disconnected"
    trade: datetime | None = None
    resync: bool = True
    gap: bool = False
    episode: int = 1
    warned: set[str] = field(default_factory=set)
    invalidate_book: bool = False
    recovery_after: datetime | None = None


class FeedQuality:
    def __init__(self, profile: FeedProfile, sla: FeedSLA, mode: Mode) -> None:
        self.profile, self.sla = profile, sla
        self.mode = mode
        self.streams: dict[str, StreamHealth] = {}
        self.clock: datetime | None = None

    def invalidate(self, symbol: str, *, gap: bool = False) -> None:
        state = self.streams.setdefault(symbol, StreamHealth())
        if not state.resync:
            state.episode += 1
            state.warned.clear()
            state.invalidate_book = True
        state.resync = True
        state.gap |= gap
        if self.clock is not None:
            state.recovery_after = self.clock

    def reconnect(self) -> None:
        for symbol, state in self.streams.items():
            self.invalidate(symbol)
            state.heartbeat = None
            state.heartbeat_status = "disconnected"

    def _age(self, state: StreamHealth, now: datetime) -> timedelta | None:
        return now - state.heartbeat if state.heartbeat is not None else None

    def _healthy(self, state: StreamHealth, now: datetime) -> bool:
        age = self._age(state, now)
        return (
            state.heartbeat_status == "healthy"
            and age is not None
            and -self.sla.clock_skew <= age <= self.sla.heartbeat_timeout
            and age <= self.sla.provider_lag
        )

    def assess(
        self,
        symbol: str,
        now: datetime,
        *,
        active_positions: Iterable[str] = (),
        emit: Callable[[PositionDataDisruption], None] | None = None,
    ) -> FeedAssessment:
        aware(now)
        if self.clock is not None and now < self.clock:
            raise ValueError("Quality clock must be monotonic")
        self.clock = now
        state = self.streams.setdefault(symbol, StreamHealth())
        if not self._healthy(state, now):
            self.invalidate(symbol)
        age = self._age(state, now)
        reasons = []
        if self.profile.origin == "simulation":
            reasons.append("SIMULATION")
        if self.profile.delivery == "delayed":
            reasons.append("DELAYED_FEED")
        if age is None or age > self.sla.heartbeat_timeout:
            reasons.append("HEARTBEAT_TIMEOUT")
        if age is not None and age > self.sla.provider_lag:
            reasons.append("PROVIDER_LAG")
        if age is not None and age < -self.sla.clock_skew:
            reasons.append("CLOCK_SKEW")
        if state.heartbeat_status != "healthy":
            reasons.append("UPSTREAM_UNHEALTHY")
        if state.gap:
            reasons.append("SEQUENCE_GAP")
        if state.resync:
            reasons.append("RESYNC_REQUIRED")
        status: Literal["live", "delayed", "degraded", "stale", "disconnected"]
        if (
            age is None
            or state.heartbeat_status == "disconnected"
            or age > self.sla.disconnected_after
        ):
            status = "disconnected"
        elif state.heartbeat_status == "stale" or age > self.sla.stale_after:
            status = "stale"
        elif state.resync or not self._healthy(state, now):
            status = "degraded"
        else:
            status = self.profile.delivery
        eligible = status == "live" and not reasons
        assessment = FeedAssessment(
            symbol,
            now,
            status,
            tuple(reasons),
            state.heartbeat,
            state.trade,
            max(timedelta(0), now - state.trade) if state.trade is not None else None,
            eligible,
            eligible,
            self.sla.reference,
            self.mode,
            self.profile.origin,
        )
        if not eligible and emit is not None:
            for position_id in active_positions:
                if position_id not in state.warned:
                    emit(
                        PositionDataDisruption(
                            self.profile.source, symbol, position_id, state.episode, assessment
                        )
                    )
                    state.warned.add(position_id)
        return assessment

    def observe(self, observation: Observation) -> None:
        """Called only after a successful commit; duplicates cannot refresh health."""
        message, now = observation.message, observation.processed_at
        self.assess(message.symbol, now)
        state = self.streams[message.symbol]
        if message.kind == "heartbeat":
            # An unhealthy report always fails closed, including equal/older
            # timestamps. Only a strictly newer healthy heartbeat can clear it.
            if message.payload["status"] != "healthy":
                state.heartbeat_status = message.payload["status"]
                state.heartbeat = (
                    max(state.heartbeat, message.event_time)
                    if state.heartbeat is not None
                    else message.event_time
                )
            elif state.heartbeat is None or message.event_time > state.heartbeat:
                state.heartbeat = message.event_time
                state.heartbeat_status = "healthy"
            if not self._healthy(state, now):
                self.invalidate(message.symbol)
        elif message.kind == "trade":
            state.trade = (
                max(state.trade, message.event_time) if state.trade else message.event_time
            )
        elif message.kind == "book_snapshot":
            lag = now - message.event_time
            if (
                self._healthy(state, now)
                and -self.sla.clock_skew <= lag <= self.sla.provider_lag
                and not observation.out_of_order
                and (state.recovery_after is None or message.event_time >= state.recovery_after)
            ):
                if (
                    state.resync
                    and self.profile.delivery == "live"
                    and self.profile.origin == "market"
                ):
                    state.warned.clear()
                state.resync = state.gap = False
        elif message.kind == "book_delta":
            lag = now - message.event_time
            if observation.out_of_order or not -self.sla.clock_skew <= lag <= self.sla.provider_lag:
                self.invalidate(message.symbol)
