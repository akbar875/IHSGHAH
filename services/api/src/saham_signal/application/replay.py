"""Deterministic, long-only research execution. No broker or notification ports."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_CEILING, Decimal, localcontext
from typing import Any, Literal

from saham_signal.application.instruments import ReferenceRepository, check_entry, lookup
from saham_signal.domain.instruments import Version, aware, positive_integer
from saham_signal.domain.persistence import digest

Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class FeeSchedule:
    version: Version
    buy_broker: Decimal
    sell_broker: Decimal
    levy: Decimal
    sell_tax: Decimal
    minimum_idr: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for rate in (self.buy_broker, self.sell_broker, self.levy, self.sell_tax):
            if not isinstance(rate, Decimal) or not rate.is_finite() or not 0 <= rate < 1:
                raise ValueError("Fee rates must be finite Decimal fractions")
        if not self.minimum_idr.is_finite() or self.minimum_idr < 0:
            raise ValueError("Invalid minimum fee")

    def charge(self, side: Side, gross: Decimal) -> Decimal:
        with localcontext() as context:
            context.prec = 60
            rate = self.buy_broker if side == "buy" else self.sell_broker + self.sell_tax
            return max(self.minimum_idr, gross * (rate + self.levy)).quantize(
                Decimal("0.01"), rounding=ROUND_CEILING
            )


@dataclass(frozen=True)
class ReplayPolicy:
    latency_ms: int = 250
    slippage_ticks: int = 1
    queue_ahead_shares: int = 100
    max_book_age_ms: int = 1000

    def __post_init__(self) -> None:
        if any(type(v) is not int or v < 0 for v in asdict(self).values()):
            raise ValueError("Policy values must be nonnegative integers")


@dataclass(frozen=True)
class Order:
    id: str
    symbol: str
    side: Side
    shares: int
    limit_idr: int
    submitted_at: datetime
    deadline: datetime
    stop_idr: int | None = None
    target_idr: int | None = None

    def __post_init__(self) -> None:
        aware(self.submitted_at)
        aware(self.deadline)
        positive_integer(self.shares)
        positive_integer(self.limit_idr)
        if not self.id or not self.symbol or self.side not in ("buy", "sell"):
            raise ValueError("Invalid order identity/side")
        if self.deadline <= self.submitted_at:
            raise ValueError("Empty order lifetime")
        if (self.stop_idr is None) != (self.target_idr is None):
            raise ValueError("Bracket requires both stop and target")
        if self.stop_idr is not None and self.target_idr is not None:
            if self.side != "sell" or not 0 < self.stop_idr < self.target_idr:
                raise ValueError("Only long-position exit brackets are supported")


@dataclass(frozen=True)
class Frame:
    """A complete, point-in-time book, optionally with a completed candle's range.

    Adapter/journal callers must preserve available_at and synchronized status.
    Candle ranges select an exit trigger only; they never supply executable volume.
    """

    id: str
    symbol: str
    event_time: datetime
    available_at: datetime
    bids: tuple[tuple[int, int], ...]
    asks: tuple[tuple[int, int], ...]
    synchronized: bool = True
    low_idr: int | None = None
    high_idr: int | None = None

    def __post_init__(self) -> None:
        aware(self.event_time)
        aware(self.available_at)
        if not self.id or not self.symbol or self.available_at < self.event_time:
            raise ValueError("Invalid frame identity/timestamps")
        for levels, reverse in ((self.bids, True), (self.asks, False)):
            prices = [p for p, _ in levels]
            if prices != sorted(set(prices), reverse=reverse):
                raise ValueError("Book levels must be unique and sorted best first")
            for price, shares in levels:
                positive_integer(price)
                positive_integer(shares)
        if self.bids and self.asks and self.bids[0][0] >= self.asks[0][0]:
            raise ValueError("Crossed or locked book")
        if (self.low_idr is None) != (self.high_idr is None):
            raise ValueError("Incomplete candle range")
        if self.low_idr is not None and self.high_idr is not None:
            if not 0 < self.low_idr <= self.high_idr:
                raise ValueError("Invalid candle range")


ASSUMPTIONS = (
    "simulation only; no actual fills, live alerts, or broker orders",
    "long-only regular continuous market; point-in-time reference and fee lookup",
    "orders compete by submitted_at then id; frames by available_at then id",
    "marketable limit orders only; resting orders are not filled from price touches",
    "spread paid by crossing opposite book; adverse slippage rounded in ticks",
    "queue reserve removed per level; executed depth never reused at that price in this replay",
    "each fill slice pays rounded-up broker/levy/tax and configured minimum",
    "stop wins when stop and target touch the same candle; trigger latency starts at availability",
    "exit triggers do not close positions; only available bid volume can reduce holdings",
)
LIMITATIONS = (
    "synthetic execution model, not calibrated fill probabilities or vendor certification",
    "no inferred hidden liquidity, replenishment, cancellations, or exact queue position",
    "no OHLC-only fills, auctions, shorting, cash/risk sizing, or corporate-action adjustment",
    "no automatic liquidation or mark-to-market for remaining positions",
    "caller supplies complete synchronized books and candle ranges available only after bar close",
    "G0/G1 pending; licensed vendor evidence and out-of-sample evaluation required separately",
)


DEFAULT_POLICY = ReplayPolicy()


def _json(value: Any) -> Any:
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


def replay(
    references: ReferenceRepository,
    fees: Sequence[FeeSchedule],
    orders: Sequence[Order],
    frames: Sequence[Frame],
    *,
    policy: ReplayPolicy = DEFAULT_POLICY,
    seed: int = 0,
    data_limits: tuple[str, ...],
    mode: Literal["research", "paper"] = "research",
) -> dict[str, Any]:
    """Return a JSON-safe audit report; deterministic (seed recorded, no random draws).

    Start flat. Existing real holdings cannot enter this boundary. Persist the report
    as a research artifact, never as a user-confirmed Fill or Position.
    """
    if mode not in ("research", "paper") or type(seed) is not int:
        raise ValueError("Replay is restricted to research/paper with an integer seed")
    if not data_limits or any(not item.strip() for item in data_limits):
        raise ValueError("Explicit input data limitations required")
    if len({o.id for o in orders}) != len(orders) or len({f.id for f in frames}) != len(frames):
        raise ValueError("Duplicate order/frame identity")
    ordered = sorted(orders, key=lambda o: (o.submitted_at, o.id))
    timeline = sorted(frames, key=lambda f: (f.available_at, f.id))
    report: dict[str, Any] = {
        "model_version": "SS-014-v1",
        "mode": mode,
        "origin": "simulation",
        "live_alerts_enabled": False,
        "seed": seed,
        "policy": asdict(policy),
        "assumptions": list(ASSUMPTIONS),
        "limitations": [*LIMITATIONS, *data_limits],
        "orders": [],
        "fills": [],
        "decisions": [],
        "positions": {},
        "net_cash_flow_idr": "0.00",
    }
    audit: list[dict[str, Any]] = report["decisions"]
    fills: list[dict[str, Any]] = report["fills"]
    remaining = {o.id: o.shares for o in ordered}
    holdings: dict[str, int] = {}
    consumed: dict[tuple[str, Side, int], int] = {}
    triggered: dict[str, tuple[datetime, str]] = {}
    cash = Decimal("0")
    for frame in timeline:
        at = frame.available_at
        for order in ordered:
            if order.symbol != frame.symbol or not remaining[order.id]:
                continue
            if not order.submitted_at <= at < order.deadline:
                continue
            if not frame.synchronized or at - frame.event_time > timedelta(
                milliseconds=policy.max_book_age_ms
            ):
                audit.append(
                    {"order_id": order.id, "frame_id": frame.id, "reason": "unhealthy_book"}
                )
                continue
            reason = "no_opposite_liquidity"
            if order.stop_idr is not None and order.id not in triggered:
                if frame.low_idr is not None and frame.low_idr <= order.stop_idr:
                    triggered[order.id] = (at, "stop")
                elif (
                    frame.high_idr is not None
                    and order.target_idr is not None
                    and frame.high_idr >= order.target_idr
                ):
                    triggered[order.id] = (at, "target")
                else:
                    audit.append(
                        {
                            "order_id": order.id,
                            "frame_id": frame.id,
                            "reason": "bracket_not_triggered",
                        }
                    )
                    continue
            start, trigger = triggered.get(order.id, (order.submitted_at, "limit"))
            ready_at = start + timedelta(milliseconds=policy.latency_ms)
            if at < ready_at or frame.event_time < ready_at:
                reason = "latency_or_pre_order_book"
            else:
                eligibility = check_entry(
                    references,
                    symbol=order.symbol,
                    at=at,
                    known_at=at,
                    price_idr=order.limit_idr,
                    shares=remaining[order.id],
                    mode=mode,
                )
                schedules = [fee for fee in fees if fee.version.visible(at, at)]
                if not eligibility.allowed:
                    reason = eligibility.reason
                elif len(schedules) != 1:
                    reason = "missing_or_ambiguous_fees"
                else:
                    snapshot = lookup(references, order.symbol, "regular", at, at)
                    report.setdefault("references", {})[frame.id] = _json(asdict(snapshot))
                    tick = snapshot.rule.tick_size(snapshot.limits.reference_price_idr)
                    levels = frame.asks if order.side == "buy" else frame.bids
                    for price, volume in levels:
                        execution = price + (1 if order.side == "buy" else -1) * (
                            policy.slippage_ticks * tick
                        )
                        if not snapshot.limits.lower_idr <= execution <= snapshot.limits.upper_idr:
                            reason = "slippage_outside_daily_limits"
                            continue
                        if price % tick or execution % tick:
                            reason = "invalid_book_tick"
                            continue
                        if (
                            (order.side == "buy" and execution > order.limit_idr)
                            or (order.side == "sell" and execution < order.limit_idr)
                            or (
                                trigger == "target"
                                and order.target_idr is not None
                                and execution < order.target_idr
                            )
                        ):
                            reason = "limit_or_slippage_cap"
                            continue
                        key = (order.symbol, order.side, price)
                        capacity = max(0, volume - policy.queue_ahead_shares - consumed.get(key, 0))
                        quantity = min(remaining[order.id], capacity)
                        if order.side == "sell":
                            quantity = min(quantity, holdings.get(order.symbol, 0))
                        quantity = quantity // snapshot.rule.lot_shares * snapshot.rule.lot_shares
                        if not quantity:
                            reason = "queue_or_position_capacity"
                            continue
                        with localcontext() as context:
                            context.prec = 60
                            gross = Decimal(execution) * quantity
                            fee_idr = schedules[0].charge(order.side, gross)
                            cash += -gross - fee_idr if order.side == "buy" else gross - fee_idr
                        holdings[order.symbol] = holdings.get(order.symbol, 0) + (
                            quantity if order.side == "buy" else -quantity
                        )
                        remaining[order.id] -= quantity
                        consumed[key] = consumed.get(key, 0) + quantity
                        fills.append(
                            {
                                "origin": "simulation",
                                "order_id": order.id,
                                "frame_id": frame.id,
                                "symbol": order.symbol,
                                "side": order.side,
                                "shares": quantity,
                                "price_idr": execution,
                                "gross_idr": str(gross),
                                "fee_idr": str(fee_idr),
                                "fee_version": schedules[0].version.id,
                                "reference_versions": list(eligibility.reference_versions),
                                "filled_at": at.isoformat(),
                                "trigger": trigger,
                            }
                        )
                        reason = "filled" if not remaining[order.id] else "partial_fill"
                        if not remaining[order.id]:
                            break
            audit.append({"order_id": order.id, "frame_id": frame.id, "reason": reason})
    report["orders"] = [
        {
            "id": o.id,
            "remaining_shares": remaining[o.id],
            "status": "filled"
            if not remaining[o.id]
            else ("partial" if remaining[o.id] < o.shares else "unfilled"),
        }
        for o in ordered
    ]
    report["positions"] = holdings
    report["fee_schedules"] = _json([asdict(f) for f in fees])
    report["order_inputs"] = _json([asdict(o) for o in ordered])
    with localcontext() as context:
        context.prec = 60
        report["net_cash_flow_idr"] = str(cash.quantize(Decimal("0.01")))
    report["input_hash"] = digest(
        _json(
            {
                "orders": [asdict(o) for o in ordered],
                "frames": [asdict(f) for f in timeline],
                "fees": [asdict(f) for f in fees],
                "policy": asdict(policy),
                "seed": seed,
                "mode": mode,
                "data_limits": data_limits,
                "references": report.get("references", {}),
            }
        )
    )
    report["report_hash"] = digest(report)
    return report
