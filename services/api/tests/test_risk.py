"""SS-015 acceptance scenarios. All prices, references and fees are synthetic."""

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, localcontext
from typing import Any

import pytest
from test_instruments import AT, version
from test_instruments import refs as refs  # noqa: F401

from saham_signal.adapters.instrument_references import MemoryReferences
from saham_signal.application.feed_quality import FeedAssessment
from saham_signal.application.operations import Control
from saham_signal.application.replay import FeeSchedule
from saham_signal.application.risk import (
    Plan,
    PlanCommand,
    PlanSpec,
    Portfolio,
    RiskDecision,
    RiskInputs,
    RiskPolicy,
    audit_document,
    evaluate,
    transition,
)

D = Decimal
FEE = FeeSchedule(version("fees"), D("0.001"), D("0.001"), D("0"), D("0.001"))
SPEC = PlanSpec(
    "plan-1",
    "alice",
    "research",
    "SIM",
    1000,
    950,
    1150,
    AT,
    AT + timedelta(minutes=5),
    AT + timedelta(minutes=10),
    AT + timedelta(minutes=30),
    D("1"),
    "trend-confirmed",
    "support-lost",
)
FEED = FeedAssessment(
    "SIM",
    AT,
    "live",
    ("SIMULATION",),
    AT,
    AT,
    timedelta(0),
    False,
    False,
    "simulation-only",
    "research",
    "simulation",
)
BOOK = Portfolio("alice", "research", AT, D("10000000"), D("1000000"))
INPUTS = RiskInputs(
    AT,
    BOOK,
    FEED,
    AT,
    995,
    1000,
    10000,
    True,
    operations=Control(1, False, "resume", "synthetic-test-only"),
)


def run(refs: MemoryReferences, inputs: RiskInputs = INPUTS, **kwargs: Any) -> RiskDecision:
    return evaluate(kwargs.pop("spec", SPEC), inputs, refs, kwargs.pop("fees", [FEE]), **kwargs)


def command(identity: str = "1", revision: int = 0, **kwargs: Any) -> PlanCommand:
    return PlanCommand(
        identity, revision, kwargs.pop("action", "evaluate"), kwargs.pop("inputs", INPUTS), **kwargs
    )


def test_ready_is_only_a_plan_and_deterministic(refs: MemoryReferences) -> None:
    initial = Plan(SPEC)
    ready = transition(initial, command(), refs, [FEE])
    assert ready.state == "READY" and ready.version == 1
    assert ready.decision is not None and ready.decision.shares > 0
    assert not hasattr(ready, "position") and not hasattr(ready, "fills")
    assert initial == Plan(SPEC)  # immutable input
    assert transition(ready, command(), refs, [FEE]) is ready
    cancel = command("2", 1, action="cancel")
    cancelled = transition(ready, cancel, refs, [FEE])
    assert cancelled.state == "CANCELLED" and cancelled.decision is None
    assert transition(cancelled, command(), refs, [FEE]) is cancelled
    replayed = Plan(SPEC)
    for event in cancelled.commands:
        replayed = transition(replayed, event, refs, [FEE])
    assert replayed == cancelled
    terminal = transition(cancelled, command("3", 2), refs, [FEE])
    assert terminal.state == "CANCELLED"
    with pytest.raises(ValueError, match="idempotency"):
        transition(ready, replace(command(), action="cancel"), refs, [FEE])
    with pytest.raises(ValueError, match="version conflict"):
        transition(ready, command("other"), refs, [FEE])


def test_expiry_cutoff_invalidation_and_monotonicity(refs: MemoryReferences) -> None:
    ready = transition(Plan(SPEC), command(), refs, [FEE])
    expired = transition(
        ready, command("2", 1, inputs=replace(INPUTS, at=SPEC.expires_at)), refs, [FEE]
    )
    assert expired.state == "EXPIRED" and expired.decision is None
    with pytest.raises(ValueError, match="Out-of-order"):
        transition(expired, command("3", 2), refs, [FEE])
    cancelled = transition(
        ready, command("2", 1, inputs=replace(INPUTS, invalidated=True)), refs, [FEE]
    )
    assert cancelled.state == "CANCELLED"
    cutoff = replace(
        INPUTS,
        at=SPEC.entry_cutoff,
        quote_as_of=SPEC.entry_cutoff,
        portfolio=replace(BOOK, as_of=SPEC.entry_cutoff),
        feed=replace(FEED, as_of=SPEC.entry_cutoff),
    )
    assert run(refs, cutoff).reason == "outside_entry_window"
    early = replace(SPEC, entry_from=AT + timedelta(seconds=1))
    assert run(refs, spec=early).reason == "outside_entry_window"


def test_exact_fee_cash_risk_and_liquidity_boundaries(refs: MemoryReferences) -> None:
    # One lot: entry=100000, buy=100, stop fee=190, friction=(1+5)*100.
    # Planned loss=5000+100+190+600=5890, target reward=15000-100-230-600=14070.
    one = replace(INPUTS, liquidity_shares=100)
    result = run(refs, one)
    assert (result.lots, result.cash_idr, result.risk_idr, result.reward_idr) == (
        1,
        D("100100.00"),
        D("5890.00"),
        D("14070.00"),
    )
    assert result.reference_versions == ("rule-1", "calendar-1", "state-1", "limits-1")
    assert result.fee_version == "fees" and result.policy_version == RiskPolicy().version
    for cash, expected in ((D("100100"), 1), (D("100099.99"), 0)):
        assert run(refs, replace(one, portfolio=replace(BOOK, free_cash_idr=cash))).lots == expected
    for capital, expected in ((D("1178000"), 1), (D("1177999"), 0)):
        assert (
            run(refs, replace(one, portfolio=replace(BOOK, capital_idr=capital))).lots == expected
        )
    for capacity, expected in ((99, 0), (100, 1), (199, 1), (200, 2)):
        assert run(refs, replace(INPUTS, liquidity_shares=capacity)).lots == expected
    with localcontext() as context:
        context.prec = 6
        assert run(refs, one) == result
    # Largest allowed size is bounded by cash and remains below the exact plan budget.
    result = run(refs)
    assert result.lots == 8 and result.risk_idr <= D("50000")


def test_aggregate_reservations_and_partial_holdings(refs: MemoryReferences) -> None:
    for used, expected in ((D("194110"), 1), (D("194110.01"), 0), (D("200000"), 0)):
        portfolio = replace(BOOK, committed_risk_idr=used)
        assert run(refs, replace(INPUTS, portfolio=portfolio)).lots == expected
    assert run(refs, replace(INPUTS, portfolio=replace(BOOK, occupied_slots=3))).reason == (
        "position_cap"
    )
    # Outstanding READY plans occupy slots alongside real partial holdings.
    assert run(refs, replace(INPUTS, portfolio=replace(BOOK, occupied_slots=2))).allowed
    assert run(refs, replace(INPUTS, portfolio=replace(BOOK, account="bob"))).reason == (
        "portfolio_scope"
    )


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"entry_idr": 1001}, "invalid_tick"),
        ({"target_idr": 1300}, "outside_price_limits"),
        ({"target_idr": 1000}, "invalid_bracket"),
        ({"target_idr": 1010}, "target_not_viable"),
        ({"stop_idr": 1000}, "invalid_bracket"),
        ({"exit_deadline": AT + timedelta(hours=4)}, "invalid_exit_deadline"),
    ],
)
def test_rejects_invalid_levels_and_deadline(
    refs: MemoryReferences,
    changes: dict[str, Any],
    reason: str,
) -> None:
    assert run(refs, spec=replace(SPEC, **changes)).reason == reason


def test_missing_future_fees_and_references(refs: MemoryReferences) -> None:
    future = replace(FEE, version=replace(FEE.version, available_at=AT + timedelta(seconds=1)))
    for fees in ([], [future], [FEE, FEE]):
        assert not run(refs, fees=fees).allowed
    short_fee = replace(FEE, version=replace(FEE.version, effective_to=SPEC.exit_deadline))
    assert run(refs, fees=[short_fee]).reason == "fees_do_not_cover_exit"
    empty = MemoryReferences((), (), (), ())
    assert not run(empty).allowed
    expensive = replace(FEE, minimum_idr=D("10000"))
    assert not run(refs, replace(INPUTS, liquidity_shares=100), fees=[expensive]).allowed


def test_feed_scope_age_trigger_spread_and_liquidity(refs: MemoryReferences) -> None:
    for feed in (
        replace(FEED, status="stale"),
        replace(FEED, reasons=("SIMULATION", "RESYNC_REQUIRED")),
        replace(FEED, symbol="OTHER"),
        replace(FEED, mode="paper"),
        replace(FEED, status="stale", entry_allowed=True),
    ):
        assert run(refs, replace(INPUTS, feed=feed)).reason == "unhealthy_data"
    for seconds, allowed in ((-1, False), (0, True), (5, True), (6, False)):
        stamp = AT - timedelta(seconds=seconds)
        assert run(refs, replace(INPUTS, feed=replace(FEED, as_of=stamp))).allowed == allowed
        assert run(refs, replace(INPUTS, quote_as_of=stamp)).allowed == allowed
        assert run(refs, replace(INPUTS, portfolio=replace(BOOK, as_of=stamp))).allowed == allowed
    assert (
        run(refs, replace(INPUTS, feed=replace(FEED, as_of=AT + timedelta(seconds=1)))).reason
        == "stale_or_future_inputs"
    )
    assert run(refs, replace(INPUTS, trigger_met=False)).reason == "trigger_pending"
    assert run(refs, replace(INPUTS, bid_idr=950)).reason == "spread_too_wide"
    assert run(refs, replace(INPUTS, bid_idr=1000, ask_idr=1005)).reason == "entry_not_executable"
    assert not run(refs, replace(INPUTS, liquidity_shares=0)).allowed
    live = replace(SPEC, mode="live")
    inputs = replace(INPUTS, portfolio=replace(BOOK, mode="live"))
    assert run(refs, inputs, spec=live).reason == "live_gates_pending"


def test_unhealthy_data_demotes_ready_and_trailing_never_expands(refs: MemoryReferences) -> None:
    ready = transition(Plan(SPEC), command(), refs, [FEE])
    assert ready.decision is not None
    trail = command("2", 1, action="trail", stop_idr=975)
    raised = transition(ready, trail, refs, [FEE])
    assert raised.spec.stop_idr == 975 and raised.version == 2
    assert raised.decision is not None
    assert raised.decision.shares <= ready.decision.shares
    assert raised.decision.risk_idr < ready.decision.risk_idr
    reduced_depth = replace(trail, inputs=replace(INPUTS, liquidity_shares=100))
    smaller = transition(ready, reduced_depth, refs, [FEE])
    assert smaller.decision is not None and smaller.decision.shares == 100
    for stop in (900, 1000, 1001):
        with pytest.raises(ValueError):
            transition(ready, replace(trail, stop_idr=stop), refs, [FEE])
    assert transition(ready, replace(trail, stop_idr=977), refs, [FEE]).state == "WATCH"
    degraded = replace(INPUTS, feed=replace(FEED, status="disconnected"))
    watch = transition(ready, command("2", 1, inputs=degraded), refs, [FEE])
    assert watch.state == "WATCH" and watch.decision is not None
    assert watch.decision.shares == 0
    with pytest.raises(ValueError, match="READY"):
        transition(Plan(SPEC), command(action="trail", stop_idr=975), refs, [FEE])


def test_policy_is_frozen_and_replayed(refs: MemoryReferences) -> None:
    policy = RiskPolicy(version="paper-approved-example", risk_fraction=D("0.01"))
    ready = transition(Plan(SPEC), command(), refs, [FEE], policy)
    assert ready.policy == policy
    with pytest.raises(ValueError, match="policy is frozen"):
        transition(ready, command("2", 1), refs, [FEE], RiskPolicy())
    replayed = Plan(SPEC, policy=ready.policy)
    for event in ready.commands:
        replayed = transition(replayed, event, refs, [FEE])
    assert replayed == ready


def test_trailing_history_replay_and_audit(refs: MemoryReferences) -> None:
    plan = transition(Plan(SPEC), command(), refs, [FEE])
    plan = transition(plan, command("2", 1, action="trail", stop_idr=960), refs, [FEE])
    plan = transition(plan, command("3", 2, action="trail", stop_idr=975), refs, [FEE])
    assert plan.initial_spec == SPEC
    replayed = Plan(plan.initial_spec, policy=plan.policy)
    for event in plan.commands:
        replayed = transition(replayed, event, refs, [FEE])
    assert replayed == plan
    document = audit_document(plan)
    assert document == json.loads(json.dumps(audit_document(replayed)))
    assert document["live_enabled"] is False
    assert document["plan"]["policy"]["risk_fraction"] == "0.005"
    assert document["plan"]["decision"]["fee_version"] == "fees"
    assert len(document["sha256"]) == 64


@pytest.mark.parametrize(
    "changes",
    [
        {"risk_fraction": D("0.011")},
        {"risk_fraction": D("NaN")},
        {"max_positions": True},
        {"combined_fraction": D("0")},
        {"min_reward_risk": D("0")},
        {"max_data_age": timedelta(0)},
    ],
)
def test_invalid_policy(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        RiskPolicy(**changes)


def test_invalid_money_and_intraday_lifetime() -> None:
    with pytest.raises(ValueError):
        replace(BOOK, free_cash_idr=D("Infinity"))
    with pytest.raises(ValueError):
        replace(SPEC, exit_deadline=AT + timedelta(days=1))
    with pytest.raises(ValueError):
        replace(SPEC, expires_at=SPEC.entry_cutoff + timedelta(seconds=1))
    with pytest.raises(ValueError):
        replace(SPEC, entry_idr=True)
