"""Explicit in-memory reference adapter; intentionally empty by default."""

from dataclasses import dataclass
from datetime import date

from saham_signal.domain.instruments import CalendarDay, DailyLimits, InstrumentRule, TradingState


@dataclass(frozen=True)
class MemoryReferences:
    instrument_rules: tuple[InstrumentRule, ...] = ()
    calendar_days: tuple[CalendarDay, ...] = ()
    trading_states: tuple[TradingState, ...] = ()
    daily_limits: tuple[DailyLimits, ...] = ()

    def rules(self, symbol: str, market: str) -> tuple[InstrumentRule, ...]:
        return tuple(r for r in self.instrument_rules if (r.symbol, r.market) == (symbol, market))

    def days(self, calendar_id: str, day: date) -> tuple[CalendarDay, ...]:
        return tuple(
            r for r in self.calendar_days if (r.calendar_id, r.trading_date) == (calendar_id, day)
        )

    def states(self, symbol: str, market: str) -> tuple[TradingState, ...]:
        return tuple(r for r in self.trading_states if (r.symbol, r.market) == (symbol, market))

    def limits(self, symbol: str, market: str, day: date) -> tuple[DailyLimits, ...]:
        return tuple(
            r
            for r in self.daily_limits
            if (r.symbol, r.market, r.trading_date) == (symbol, market, day)
        )
