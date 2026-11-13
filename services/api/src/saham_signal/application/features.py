"""Shared point-in-time reducer for normalized MarketEvents, never a trading gate."""

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Context, Decimal, localcontext
from typing import Any

from saham_signal.application.feed import FeedProfile
from saham_signal.application.feed_quality import FeedAssessment
from saham_signal.domain.instruments import aware
from saham_signal.domain.mode import Mode

WIB = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class FeaturePolicy:
    reference: str = "SS-013/simulation-v1"
    window: timedelta = timedelta(minutes=5)
    minimum_coverage: Decimal = Decimal("0.8")
    depth_levels: int = 5
    book_max_age: timedelta = timedelta(seconds=10)

    def __post_init__(self) -> None:
        if not self.reference or not timedelta(0) < self.window < timedelta(days=1):
            raise ValueError("Require a policy reference and intraday window")
        if not self.minimum_coverage.is_finite() or not 0 < self.minimum_coverage <= 1:
            raise ValueError("Coverage must be in (0, 1]")
        if type(self.depth_levels) is not int or not 1 <= self.depth_levels <= 50:
            raise ValueError("Unsupported depth")
        if self.book_max_age <= timedelta(0):
            raise ValueError("Book age must be positive")


@dataclass(frozen=True)
class FeatureSnapshot:
    symbol: str
    as_of: datetime
    window_start: datetime
    policy: FeaturePolicy
    source: str
    mode: Mode
    data_origin: str
    delivery: str
    return_fraction: Decimal | None
    volatility_fraction: Decimal | None
    volume_lots: int
    relative_volume: Decimal | None
    baseline_sessions: tuple[date, ...]
    buy_lots: int
    sell_lots: int
    unknown_lots: int
    classification_coverage: Decimal | None
    buy_pressure: Decimal | None
    sell_pressure: Decimal | None
    pressure_method: str
    pressure_hidden_reason: str | None
    spread_idr: Decimal | None
    bid_depth_lots: int | None
    ask_depth_lots: int | None
    available_levels: int
    limited_depth: bool
    book_imbalance: Decimal | None
    depth_as_of: datetime | None
    book_hidden_reason: str | None


class FeatureEngine:
    """Single-source/mode session. Accept only committed, schema-validated events.

    Keep all revisions: a correction cannot rewrite a snapshot at an older cutoff.
    Replay and streaming use the same reducer; a fresh engine can receive journal
    rows in any order. The caller owns bounded retention/session rotation.
    """

    def __init__(self, profile: FeedProfile, mode: Mode, policy: FeaturePolicy) -> None:
        if mode not in ("research", "paper", "live"):
            raise ValueError("Unknown mode")
        if mode == "live" and profile.origin == "simulation":
            raise ValueError("Simulation cannot enter live")
        self.profile, self.mode, self.policy = profile, mode, policy
        self._events: dict[tuple[str, int], dict[str, Any]] = {}
        self._identities: dict[str, tuple[str, str]] = {}

    def observe(self, event: dict[str, Any], revision: int) -> None:
        """Use Observation.record.version or Journal.replay row['version']."""
        if (
            event["source"] != self.profile.source
            or event["mode"] != self.mode
            or event["data_origin"] != self.profile.origin
            or event["quality"]["feed"] not in (self.profile.delivery, "disconnected")
        ):
            raise ValueError("Mixed source, mode, origin or delivery")
        if type(revision) is not int or revision < 1:
            raise ValueError("Invalid revision")
        key = (event["event_id"], revision)
        identity = (event["symbol"], event["event_type"])
        if key[0] in self._identities and self._identities[key[0]] != identity:
            raise ValueError("Correction changed identity")
        if key in self._events and self._events[key] != event:
            raise ValueError("Conflicting duplicate")
        self._events[key] = deepcopy(event)
        self._identities[key[0]] = identity

    def snapshot(
        self,
        symbol: str,
        cutoff: datetime,
        *,
        baseline_sessions: Iterable[date] = (),
        quality: FeedAssessment | None = None,
    ) -> FeatureSnapshot:
        aware(cutoff)
        # Fix precision independently of the caller's Decimal context.
        with localcontext(Context(prec=28)):
            return self._snapshot(symbol, cutoff, tuple(baseline_sessions), quality)

    def _snapshot(
        self,
        symbol: str,
        cutoff: datetime,
        sessions: tuple[date, ...],
        quality: FeedAssessment | None,
    ) -> FeatureSnapshot:
        latest: dict[str, tuple[int, dict[str, Any]]] = {}
        for (identity, revision), event in self._events.items():
            if event["symbol"] != symbol or datetime.fromisoformat(event["available_at"]) > cutoff:
                continue
            if identity not in latest or revision > latest[identity][0]:
                latest[identity] = revision, event
        # Filter event_time AFTER revision selection: corrections may move a trade.
        events = [
            e for _, e in latest.values() if datetime.fromisoformat(e["event_time"]) <= cutoff
        ]
        events.sort(
            key=lambda e: (
                datetime.fromisoformat(e["event_time"]),
                int(e["sequence"]),
                e["event_id"],
            )
        )
        trades = [e for e in events if e["event_type"] == "trade"]
        start = cutoff - self.policy.window
        current = [e for e in trades if start < datetime.fromisoformat(e["event_time"]) <= cutoff]
        prices = [Decimal(e["payload"]["price_idr"]) for e in current]
        returns = [b / a - 1 for a, b in zip(prices, prices[1:], strict=False)]
        result_return = prices[-1] / prices[0] - 1 if len(prices) >= 2 else None
        volatility = None
        if len(returns) >= 2:
            mean = sum(returns, Decimal(0)) / len(returns)
            volatility = (sum(((r - mean) ** 2 for r in returns), Decimal(0)) / len(returns)).sqrt()
        volumes = {
            side: sum(e["payload"]["lots"] for e in current if e["payload"]["aggressor"] == side)
            for side in ("buyer", "seller", "unknown")
        }
        total = sum(volumes.values())
        classified = volumes["buyer"] + volumes["seller"]
        coverage = Decimal(classified) / total if total else None
        hidden = (
            "NO_VOLUME"
            if not total
            else (
                "INSUFFICIENT_COVERAGE"
                if coverage is None or coverage < self.policy.minimum_coverage
                else None
            )
        )
        buy = Decimal(volumes["buyer"]) / classified if hidden is None else None
        local = cutoff.astimezone(WIB)
        if len(set(sessions)) != len(sessions) or any(s >= local.date() for s in sessions):
            raise ValueError("Baseline sessions must be unique past WIB dates")
        baseline: list[int] = []
        for session in sessions:
            end = datetime.combine(session, local.timetz())
            rows = [
                e
                for e in trades
                if end - self.policy.window < datetime.fromisoformat(e["event_time"]) <= end
            ]
            if not rows:  # Absence is not evidence of zero volume or a trading day.
                break
            baseline.append(sum(e["payload"]["lots"] for e in rows))
        relative = None
        if sessions and len(baseline) == len(sessions) and sum(baseline) > 0:
            relative = Decimal(total) * len(baseline) / sum(baseline)
        books = [e for e in events if e["event_type"] == "book_snapshot"]
        book_reason = "NO_BOOK"
        spread = imbalance = None
        bids = asks = None
        levels = 0
        depth_at = None
        if books:
            book = books[-1]
            depth_at = datetime.fromisoformat(book["event_time"])
            valid_quality = quality is not None and (
                quality.symbol == symbol
                and quality.as_of == cutoff
                and quality.mode == self.mode
                and quality.data_origin == self.profile.origin
                and quality.status in ("live", "delayed")
                and not set(quality.reasons) - {"SIMULATION", "DELAYED_FEED"}
            )
            book_reason = "UNHEALTHY_FEED" if not valid_quality else "STALE_BOOK"
            if valid_quality and cutoff - depth_at <= self.policy.book_max_age:
                data = book["payload"]
                bid_rows = sorted(data["bids"], key=lambda r: Decimal(r["price_idr"]), reverse=True)
                ask_rows = sorted(data["asks"], key=lambda r: Decimal(r["price_idr"]))
                levels = min(len(bid_rows), len(ask_rows), self.policy.depth_levels)
                book_reason = "EMPTY_BOOK"
                if levels:
                    spread = Decimal(ask_rows[0]["price_idr"]) - Decimal(bid_rows[0]["price_idr"])
                    bids = sum(r["lots"] for r in bid_rows[: self.policy.depth_levels])
                    asks = sum(r["lots"] for r in ask_rows[: self.policy.depth_levels])
                    imbalance = Decimal(bids) / (bids + asks) if bids + asks else None
                    book_reason = ""
        return FeatureSnapshot(
            symbol=symbol,
            as_of=cutoff,
            window_start=start,
            policy=self.policy,
            source=self.profile.source,
            mode=self.mode,
            data_origin=self.profile.origin,
            delivery=self.profile.delivery,
            return_fraction=result_return,
            volatility_fraction=volatility,
            volume_lots=total,
            relative_volume=relative,
            baseline_sessions=sessions,
            buy_lots=volumes["buyer"],
            sell_lots=volumes["seller"],
            unknown_lots=volumes["unknown"],
            classification_coverage=coverage,
            buy_pressure=buy,
            sell_pressure=1 - buy if buy is not None else None,
            pressure_method="feed-aggressor-v1",
            pressure_hidden_reason=hidden,
            spread_idr=spread,
            bid_depth_lots=bids,
            ask_depth_lots=asks,
            available_levels=levels,
            limited_depth=levels < self.policy.depth_levels,
            book_imbalance=imbalance,
            depth_as_of=depth_at,
            book_hidden_reason=book_reason or None,
        )
