"""Offline paper qualification. This boundary cannot authorize a market/live run.

One flat-start hypothetical plan per run; no shared capital, broker, manual-fill
or notification delivery ports. Persist the receipt before presenting its results.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Any

from saham_signal.application.alerts import AlertEvent, delivery
from saham_signal.application.evaluation import Baseline, document
from saham_signal.application.features import FeatureEngine, FeaturePolicy
from saham_signal.application.feed import FeedIngestor, FeedMessage, FeedProfile, Observation
from saham_signal.application.instruments import ReferenceRepository, lookup
from saham_signal.application.market import MarketScope, stamp, validate
from saham_signal.application.operations import Operations
from saham_signal.application.replay import FeeSchedule, Frame, Order, ReplayPolicy, _json, replay
from saham_signal.application.risk import Plan, PlanCommand, PlanSpec, RiskInputs, audit_document
from saham_signal.application.risk import transition as plan_transition
from saham_signal.domain.instruments import aware
from saham_signal.domain.persistence import digest

EXECUTION_POLICY = ReplayPolicy()
FEATURE_POLICY = FeaturePolicy()


def execution_price(value: str) -> int:
    price = Decimal(value)
    if not price.is_finite() or price <= 0 or price != price.to_integral_value():
        raise ValueError("Execution price requires positive integral IDR")
    return int(price)


@dataclass(frozen=True)
class ObservationProtocol:
    """Freeze before prospective observation; null budgets mean NOT ready.

    Values must be derived from a reviewed validation receipt. This is a protocol
    manifest, not an approval mechanism: neither a hash nor supplied gate strings
    grants execution authority. Synthetic qualification never counts toward G2.
    """

    frozen_at: datetime
    starts_at: datetime
    validation_ref: str | None = None
    maximum_brier: Decimal | None = None
    maximum_fill_rate_error: Decimal | None = None
    maximum_drawdown_idr: Decimal | None = None
    minimum_sessions: int = 60
    minimum_trades: int = 300

    def __post_init__(self) -> None:
        aware(self.frozen_at)
        aware(self.starts_at)
        if self.frozen_at >= self.starts_at:
            raise ValueError("Freeze before observation starts")
        if (
            type(self.minimum_sessions) is not int
            or type(self.minimum_trades) is not int
            or self.minimum_sessions < 60
            or self.minimum_trades < 300
        ):
            raise ValueError("G2 requires at least 60 sessions AND 300 eligible trades")
        for value in (self.maximum_brier, self.maximum_fill_rate_error, self.maximum_drawdown_idr):
            if value is not None and (
                not isinstance(value, Decimal) or not value.is_finite() or value <= 0
            ):
                raise ValueError("Positive finite Decimal tolerance required")
        if any(v is not None and v > 1 for v in (self.maximum_brier, self.maximum_fill_rate_error)):
            raise ValueError("Fraction tolerance must not exceed one")

    def document(self) -> dict[str, Any]:
        body = _json(asdict(self))
        complete = bool(
            self.validation_ref
            and self.validation_ref.strip()
            and all(
                v is not None
                for v in (
                    self.maximum_brier,
                    self.maximum_fill_rate_error,
                    self.maximum_drawdown_idr,
                )
            )
        )
        return {"manifest": body, "sha256": digest(body), "budgets_complete": complete}


def readiness(protocol: ObservationProtocol, acceptance: dict[int, str]) -> dict[str, Any]:
    missing = [i for i in range(1, 13) if acceptance.get(i) != "passed"]
    reasons = ["G0_PENDING_LICENSED_DATA", "G1_NO_GO", "PROSPECTIVE_ADAPTER_UNAVAILABLE"]
    if not protocol.document()["budgets_complete"]:
        reasons.append("VALIDATION_TOLERANCES_MISSING")
    if missing or set(acceptance) != set(range(1, 13)):
        reasons.append("CRITICAL_ACCEPTANCE_INCOMPLETE")
    return {
        "paper_live_enabled": False,
        "g0": "pending",
        "g1": "no-go",
        "g2": "not-started",
        "reasons": reasons,
        "missing_scenarios": missing,
        "observed_sessions": 0,
        "eligible_prospective_trades": 0,
    }


def qualify(
    *,
    profile: FeedProfile,
    messages: Sequence[tuple[FeedMessage, datetime]],
    spec: PlanSpec,
    inputs: RiskInputs,
    baseline: Baseline,
    references: ReferenceRepository,
    fees: Sequence[FeeSchedule],
    operations: Operations,
    protocol: ObservationProtocol,
    execution_policy: ReplayPolicy = EXECUTION_POLICY,
    feature_policy: FeaturePolicy = FEATURE_POLICY,
) -> dict[str, Any]:
    """Feed -> point-in-time features -> baseline -> risk -> replay -> paper view.

    Explicit received/available time is shared in this offline harness. Future
    frames affect execution only. The plan uses only messages available at its
    decision time. Caller risk quote/capacity/trigger/feed/control are replaced
    by values derived here. Output is an internal report, never a v1 Signal.
    """
    if (
        profile.origin != "simulation"
        or profile.delivery != "live"
        or spec.mode != "paper"
        or inputs.portfolio.mode != "paper"
        or inputs.portfolio.account != spec.account
        or operations.mode != "paper"
        or inputs.portfolio.occupied_slots
        or inputs.portfolio.committed_risk_idr
    ):
        raise ValueError("Flat-start isolated paper simulation required")
    if inputs.at != spec.entry_from:
        raise ValueError("Decision must occur at plan entry_from")
    times = [at for _, at in messages]
    for at in times:
        aware(at)
    if times != sorted(times) or any(m.symbol != spec.symbol for m, _ in messages):
        raise ValueError("Ordered single-symbol input required")
    engine = FeatureEngine(profile, "paper", feature_policy)
    frames: list[Frame] = []
    candle_range: tuple[int, int] | None = None

    def commit(observation: Observation) -> None:
        if observation.record is not None:
            engine.observe(observation.payload, observation.record.version)

    feed = FeedIngestor(
        profile,
        "paper",
        lot_shares=lambda symbol, at, known: (
            lookup(references, symbol, "regular", at, known).rule.lot_shares
        ),
        validate=validate,
        commit=commit,
        snapshot_request=lambda *_: None,
        operations=operations,
    )

    def ingest(message: FeedMessage, at: datetime) -> None:
        nonlocal candle_range
        result = feed.ingest(message, received_at=at, available_at=at, processed_at=at)
        if (
            result == "committed"
            and message.kind == "candle"
            and datetime.fromisoformat(message.payload["at"]) >= inputs.at
        ):
            candle_range = (
                execution_price(message.payload["low_idr"]),
                execution_price(message.payload["high_idr"]),
            )
        if result != "committed" or message.kind not in ("book_snapshot", "book_delta"):
            return
        book = feed.books[spec.symbol]
        health = feed.assess_quality(spec.symbol, at)
        lot = lookup(references, spec.symbol, "regular", at, at).rule.lot_shares
        frames.append(
            Frame(
                f"{message.event_id}:{message.revision}",
                spec.symbol,
                message.event_time,
                at,
                tuple(
                    sorted(
                        ((execution_price(p), n * lot) for p, n in book.bids.items()), reverse=True
                    )
                ),
                tuple(sorted((execution_price(p), n * lot) for p, n in book.asks.items())),
                book.synchronized and health.status == "live" and health.reasons == ("SIMULATION",),
                candle_range[0] if candle_range else None,
                candle_range[1] if candle_range else None,
            )
        )

    for message, at in messages:
        if at <= inputs.at:
            ingest(message, at)
    assessment = feed.assess_quality(spec.symbol, inputs.at)
    features = engine.snapshot(spec.symbol, inputs.at, quality=assessment)
    score = baseline.score(features)
    current = frames[-1] if frames else None
    usable = current is not None and current.synchronized and current.bids and current.asks
    derived = replace(
        inputs,
        feed=assessment,
        operations=operations.control(),
        trigger_met=score is not None and bool(usable),
        quote_as_of=current.event_time if current else inputs.at,
        bid_idr=current.bids[0][0] if usable and current else 1,
        ask_idr=current.asks[0][0] if usable and current else 2,
        liquidity_shares=sum(n for p, n in current.asks if p <= spec.entry_idr)
        if usable and current
        else 0,
    )
    plan = plan_transition(
        Plan(spec), PlanCommand("paper-decision", 0, "evaluate", derived), references, fees
    )
    for message, at in messages:
        if at > inputs.at:
            ingest(message, at)
    # Recheck controls before producing execution output. No market publication.
    allowed = plan.state == "READY" and not operations.entry_blocked()
    orders: list[Order] = []
    if allowed and plan.decision:
        lower = lookup(references, spec.symbol, "regular", inputs.at, inputs.at).limits.lower_idr
        orders = [
            Order(
                "entry",
                spec.symbol,
                "buy",
                plan.decision.shares,
                spec.entry_idr,
                spec.entry_from,
                spec.expires_at,
            ),
            Order(
                "exit",
                spec.symbol,
                "sell",
                plan.decision.shares,
                lower,
                spec.entry_from,
                spec.exit_deadline,
                spec.stop_idr,
                spec.target_idr,
            ),
        ]
    result = replay(
        references,
        fees,
        orders,
        frames,
        policy=execution_policy,
        mode="paper",
        data_limits=("SS-026 offline flat-start simulation; no prospective G2 credit",),
    )
    scope = MarketScope(spec.account, "paper", str(inputs.portfolio.capital_idr), 30)
    # Exercise policy in the paper namespace; do not send to an inbox or live channel.
    gate: dict[str, Any] = {}
    event = AlertEvent(
        "paper:" + spec.id,
        "ENTRY_READY",
        inputs.at,
        signal_id=spec.id,
        active=allowed,
        origin="simulation",
        mode="paper",
    )
    alert = delivery(scope, event, inputs.at, gate)
    body = {
        "format": "SS-026-qualification-v1",
        "mode": "paper",
        "account": spec.account,
        "origin": "simulation",
        "as_of": stamp(max([inputs.at, *times])),
        "input_hash": digest(_json([asdict(m) | {"available_at": at} for m, at in messages])),
        "baseline": _json(asdict(baseline)),
        "baseline_score": score,
        "features": document(asdict(features)),
        "plan": audit_document(plan),
        "execution": result,
        "paper_fills": result["fills"],
        "paper_positions": result["positions"],
        "actual_fills": [],
        "actual_fill_source": "excluded:manual_position_events",
        "alert_preview": alert,
        "live_alerts_enabled": False,
        "protocol": protocol.document(),
        "readiness": readiness(protocol, {}),
    }
    return {**body, "sha256": digest(body)}
