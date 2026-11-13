"""Versioned long-only plan decisions. READY reserves risk; it never creates a fill.

Pure application boundary: callers serialize portfolio reservations per account/mode
and journal commands plus input snapshots before publishing the resulting plan.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from typing import Any, Literal

from saham_signal.application.feed_quality import FeedAssessment
from saham_signal.application.instruments import ReferenceRepository, check_entry, lookup, select
from saham_signal.application.replay import FeeSchedule
from saham_signal.domain.instruments import JAKARTA, ReferenceUnavailable, aware, positive_integer
from saham_signal.domain.mode import Mode
from saham_signal.domain.persistence import digest

ZERO = Decimal("0")


def money(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("Nonnegative finite Decimal required")


@dataclass(frozen=True)
class RiskPolicy:
    version: str = "SS-015-v1/provisional"
    risk_fraction: Decimal = Decimal("0.005")
    max_risk_fraction: Decimal = Decimal("0.01")
    combined_fraction: Decimal = Decimal("0.02")
    max_positions: int = 3
    min_reward_risk: Decimal = Decimal("1")
    max_spread_fraction: Decimal = Decimal("0.01")
    max_data_age: timedelta = timedelta(seconds=5)

    def __post_init__(self) -> None:
        for value in (
            self.risk_fraction,
            self.max_risk_fraction,
            self.combined_fraction,
            self.min_reward_risk,
            self.max_spread_fraction,
        ):
            money(value)
        if not self.version or not 0 < self.risk_fraction <= self.max_risk_fraction <= 1:
            raise ValueError("Invalid version or per-plan risk limits")
        if not 0 < self.combined_fraction <= 1 or self.min_reward_risk <= 0:
            raise ValueError("Invalid aggregate or reward/risk policy")
        positive_integer(self.max_positions)
        if self.max_data_age <= timedelta(0):
            raise ValueError("Positive freshness limit required")


DEFAULT_POLICY = RiskPolicy()


@dataclass(frozen=True)
class Portfolio:
    """Free cash and risk of all OTHER open positions and pending READY plans.

    Include partial fills at actual remaining shares; never release a failed exit.
    Scope, reservations and actual fills remain the caller's transactional concern.
    """

    account: str
    mode: Mode
    as_of: datetime
    capital_idr: Decimal
    free_cash_idr: Decimal
    committed_risk_idr: Decimal = ZERO
    occupied_slots: int = 0

    def __post_init__(self) -> None:
        aware(self.as_of)
        for value in (self.capital_idr, self.free_cash_idr, self.committed_risk_idr):
            money(value)
        if not self.account or self.mode not in ("research", "paper", "live"):
            raise ValueError("Account/mode required")
        if type(self.occupied_slots) is not int or self.occupied_slots < 0:
            raise ValueError("Invalid occupied slots")


@dataclass(frozen=True)
class PlanSpec:
    id: str
    account: str
    mode: Mode
    symbol: str
    entry_idr: int
    stop_idr: int
    target_idr: int
    entry_from: datetime
    expires_at: datetime
    entry_cutoff: datetime
    exit_deadline: datetime
    # Explicit adverse execution allowance, beyond crossing the quoted spread.
    friction_per_share_idr: Decimal
    trigger: str
    invalidation: str

    def __post_init__(self) -> None:
        for price in (self.entry_idr, self.stop_idr, self.target_idr):
            positive_integer(price)
        for stamp in (self.entry_from, self.expires_at, self.entry_cutoff, self.exit_deadline):
            aware(stamp)
        money(self.friction_per_share_idr)
        if not all((self.id, self.account, self.symbol, self.trigger, self.invalidation)):
            raise ValueError("Plan identity, trigger and invalidation required")
        if self.mode not in ("research", "paper", "live"):
            raise ValueError("Unsupported mode")
        if not self.entry_from < self.expires_at <= self.entry_cutoff < self.exit_deadline:
            raise ValueError("Entry lifetime, cutoff and exit deadline must be ordered")
        if (
            len(
                {
                    t.astimezone(JAKARTA).date()
                    for t in (
                        self.entry_from,
                        self.expires_at,
                        self.entry_cutoff,
                        self.exit_deadline,
                    )
                }
            )
            != 1
        ):
            raise ValueError("Intraday plan must remain on the same WIB date")


@dataclass(frozen=True)
class RiskInputs:
    at: datetime
    portfolio: Portfolio
    feed: FeedAssessment
    quote_as_of: datetime  # Same snapshot supplies bid, ask and executable capacity.
    bid_idr: int
    ask_idr: int
    liquidity_shares: int  # Conservative executable capacity, not raw displayed volume.
    trigger_met: bool
    invalidated: bool = False

    def __post_init__(self) -> None:
        aware(self.at)
        aware(self.quote_as_of)
        positive_integer(self.bid_idr)
        positive_integer(self.ask_idr)
        if self.bid_idr >= self.ask_idr:
            raise ValueError("Book must be uncrossed")
        if type(self.liquidity_shares) is not int or self.liquidity_shares < 0:
            raise ValueError("Invalid liquidity capacity")


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    lots: int = 0
    shares: int = 0
    cash_idr: Decimal = ZERO
    risk_idr: Decimal = ZERO
    reward_idr: Decimal = ZERO
    policy_version: str = ""
    reference_versions: tuple[str, ...] = ()
    fee_version: str = ""


def evaluate(
    spec: PlanSpec,
    inputs: RiskInputs,
    references: ReferenceRepository,
    fees: Sequence[FeeSchedule],
    policy: RiskPolicy = DEFAULT_POLICY,
) -> RiskDecision:
    """Size with integer lots and exact rounded fees; all boundaries are inclusive caps."""

    def reject(reason: str) -> RiskDecision:
        return RiskDecision(False, reason, policy_version=policy.version)

    at, book, feed = inputs.at, inputs.portfolio, inputs.feed
    if (spec.account, spec.mode) != (book.account, book.mode):
        return reject("portfolio_scope")
    if spec.mode == "live":
        return reject("live_gates_pending")
    for stamp in (book.as_of, feed.as_of, inputs.quote_as_of):
        aware(stamp)
        if not timedelta(0) <= at - stamp <= policy.max_data_age:
            return reject("stale_or_future_inputs")
    # Production eligibility comes from SS-012. Simulation is allowed only in research/paper.
    simulation = (
        feed.data_origin == "simulation"
        and feed.status == "live"
        and set(feed.reasons) == {"SIMULATION"}
    )
    market = (
        feed.data_origin == "market"
        and feed.status == "live"
        and not feed.reasons
        and feed.entry_allowed
    )
    if feed.symbol != spec.symbol or feed.mode != spec.mode or not (market or simulation):
        return reject("unhealthy_data")
    if inputs.invalidated:
        return reject("invalidated")
    if not spec.entry_from <= at < min(spec.expires_at, spec.entry_cutoff):
        return reject("outside_entry_window")
    if not inputs.trigger_met:
        return reject("trigger_pending")
    if not spec.stop_idr < spec.entry_idr < spec.target_idr:
        return reject("invalid_bracket")
    if book.occupied_slots >= policy.max_positions:
        return reject("position_cap")
    try:
        snapshot = lookup(references, spec.symbol, "regular", at, at)
        fee = select(fees, at, at)
        if not fee.version.visible(spec.exit_deadline, at):
            return reject("fees_do_not_cover_exit")
        sessions = snapshot.day.sessions
        if not any(
            s.mechanism == "continuous"
            and s.opens < spec.exit_deadline.astimezone(JAKARTA).time() <= s.closes
            for s in sessions
        ):
            return reject("invalid_exit_deadline")
        lot = snapshot.rule.lot_shares
        for price in (spec.entry_idr, spec.stop_idr, spec.target_idr):
            eligibility = check_entry(
                references,
                symbol=spec.symbol,
                at=at,
                known_at=at,
                price_idr=price,
                shares=lot,
                mode=spec.mode,
            )
            if not eligibility.allowed:
                return reject(eligibility.reason)
    except ReferenceUnavailable as exc:
        return reject(str(exc))
    with localcontext() as context:
        context.prec = 60
        spread = Decimal(inputs.ask_idr - inputs.bid_idr)
        if spread / Decimal(inputs.ask_idr) > policy.max_spread_fraction:
            return reject("spread_too_wide")
        if inputs.ask_idr > spec.entry_idr:
            return reject("entry_not_executable")
        budget = min(
            book.capital_idr * policy.risk_fraction,
            book.capital_idr * policy.combined_fraction - book.committed_risk_idr,
        )
        if budget <= 0:
            return reject("aggregate_risk_cap")

        def amounts(lots: int) -> tuple[Decimal, Decimal, Decimal]:
            shares = lots * lot
            gross = Decimal(spec.entry_idr * shares)
            buy_fee = fee.charge("buy", gross)
            friction = (spec.friction_per_share_idr + spread) * shares
            stop_fee = fee.charge("sell", Decimal(spec.stop_idr * shares))
            target_fee = fee.charge("sell", Decimal(spec.target_idr * shares))
            cash = gross + buy_fee
            risk = Decimal((spec.entry_idr - spec.stop_idr) * shares)
            risk += buy_fee + stop_fee + friction
            reward = Decimal((spec.target_idr - spec.entry_idr) * shares)
            reward -= buy_fee + target_fee + friction
            return cash, risk, reward

        # Binary search includes fee minima and rounding instead of approximating per-lot fees.
        low, high = 0, inputs.liquidity_shares // lot
        while low < high:
            middle = (low + high + 1) // 2
            cash, risk, _ = amounts(middle)
            if cash <= book.free_cash_idr and risk <= budget:
                low = middle
            else:
                high = middle - 1
        if low == 0:
            return reject("insufficient_cash_risk_or_liquidity")
        cash, risk, reward = amounts(low)
        if reward <= 0 or reward < risk * policy.min_reward_risk:
            return reject("target_not_viable")
        return RiskDecision(
            True,
            "eligible",
            low,
            low * lot,
            cash,
            risk,
            reward,
            policy.version,
            tuple(v.id for v in snapshot.versions),
            fee.version.id,
        )


@dataclass(frozen=True)
class PlanCommand:
    id: str
    expected_version: int
    action: Literal["evaluate", "cancel", "trail"]
    inputs: RiskInputs
    stop_idr: int | None = None


@dataclass(frozen=True)
class Plan:
    spec: PlanSpec
    version: int = 0
    state: Literal["WATCH", "READY", "EXPIRED", "CANCELLED"] = "WATCH"
    decision: RiskDecision | None = None
    as_of: datetime | None = None
    commands: tuple[PlanCommand, ...] = ()
    policy: RiskPolicy = DEFAULT_POLICY
    initial_spec: PlanSpec | None = None


def transition(
    plan: Plan,
    command: PlanCommand,
    references: ReferenceRepository,
    fees: Sequence[FeeSchedule],
    policy: RiskPolicy | None = None,
) -> Plan:
    """Replay commands in journal order with the same frozen references, fees and policy.

    A repeated ID must contain the exact same payload, even after later commands.
    Rejected eligibility demotes READY to WATCH and releases its proposed reservation.
    No position/fill state can be mutated by this reducer.
    """
    policy = plan.policy if policy is None else policy
    if plan.commands and policy != plan.policy:
        raise ValueError("Plan policy is frozen; create a new plan for a new policy")
    for previous in plan.commands:
        if previous.id == command.id:
            if previous != command:
                raise ValueError("Conflicting idempotency key")
            return plan
    if not command.id or command.expected_version != plan.version:
        raise ValueError("Missing command ID or version conflict")
    if plan.as_of is not None and command.inputs.at < plan.as_of:
        raise ValueError("Out-of-order command")
    spec, at = plan.spec, command.inputs.at
    if command.action not in ("evaluate", "cancel", "trail"):
        raise ValueError("Unsupported command")
    if command.action != "trail" and command.stop_idr is not None:
        raise ValueError("Only trailing can change stop")
    state, decision = plan.state, plan.decision
    if state not in ("EXPIRED", "CANCELLED"):
        if at >= min(spec.expires_at, spec.entry_cutoff):
            state, decision = "EXPIRED", None
        elif command.action == "cancel" or command.inputs.invalidated:
            state, decision = "CANCELLED", None
        else:
            if command.action == "trail":
                if state != "READY" or command.stop_idr is None:
                    raise ValueError("Trailing requires a READY plan and stop")
                positive_integer(command.stop_idr)
                if not spec.stop_idr <= command.stop_idr < spec.entry_idr:
                    raise ValueError("Trailing must never widen risk or cross entry")
                spec = replace(spec, stop_idr=command.stop_idr)
            inputs = command.inputs
            if command.action == "trail" and plan.decision is not None:
                # Raising stop may increase lot capacity: never expand an existing plan's size.
                inputs = replace(
                    inputs,
                    liquidity_shares=min(
                        inputs.liquidity_shares,
                        plan.decision.shares,
                    ),
                )
            decision = evaluate(spec, inputs, references, fees, policy)
            state = "READY" if decision.allowed else "WATCH"
    return Plan(
        spec,
        plan.version + 1,
        state,
        decision,
        at,
        (*plan.commands, command),
        policy,
        plan.initial_spec or plan.spec,
    )


def audit_document(plan: Plan) -> dict[str, Any]:
    """JSON-safe internal research artifact; not a v1 Signal, Fill or Position payload.

    Retain with immutable reference/fee snapshots in the SS-010 research artifact
    store. The application service must commit reservations and journal atomically
    before publishing READY. This function does not perform a database write.
    """

    def encode(value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        if isinstance(value, timedelta):
            return {"microseconds": value // timedelta(microseconds=1)}
        if isinstance(value, dict):
            return {key: encode(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [encode(item) for item in value]
        return value

    document: dict[str, Any] = {
        "engine_version": "SS-015-v1",
        "live_enabled": False,
        "plan": encode(asdict(plan)),
    }
    return {**document, "sha256": digest(document)}
