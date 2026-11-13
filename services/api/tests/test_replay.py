"""SS-014 acceptance and execution regression scenarios, entirely synthetic."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, localcontext
from typing import Any

import pytest
from test_instruments import AT, version
from test_instruments import refs as refs  # noqa: F401

from saham_signal.adapters.instrument_references import MemoryReferences
from saham_signal.application.replay import FeeSchedule, Frame, Order, ReplayPolicy, replay

POLICY = ReplayPolicy(latency_ms=0, slippage_ticks=0, queue_ahead_shares=0)
FEE = FeeSchedule(
    version("fees"), Decimal("0.001"), Decimal("0.001"), Decimal("0.0001"), Decimal("0.001")
)


def order(
    identity: str = "entry",
    side: Any = "buy",
    shares: int = 100,
    limit: int = 1250,
    seconds: int = 0,
) -> Order:
    return Order(
        identity,
        "SIM",
        side,
        shares,
        limit,
        AT + timedelta(seconds=seconds),
        AT + timedelta(minutes=5),
    )


def frame(
    identity: str = "book",
    seconds: int = 1,
    *,
    bids: tuple[tuple[int, int], ...] = ((995, 1000),),
    asks: tuple[tuple[int, int], ...] = ((1000, 1000),),
) -> Frame:
    at = AT + timedelta(seconds=seconds)
    return Frame(identity, "SIM", at, at, bids, asks)


def run(
    refs: MemoryReferences, orders: list[Order], frames: list[Frame], **kwargs: Any
) -> dict[str, Any]:
    return replay(
        refs,
        [FEE],
        orders,
        frames,
        policy=kwargs.pop("policy", POLICY),
        data_limits=("synthetic SS-014 fixture; no licensed feed",),
        **kwargs,
    )


def test_ara_no_sellers_never_fills(refs: MemoryReferences) -> None:
    result = run(refs, [order()], [frame(bids=((1250, 10000),), asks=())])
    assert result["fills"] == []
    assert result["orders"][0]["status"] == "unfilled"


def test_arb_no_buyers_keeps_position_open(refs: MemoryReferences) -> None:
    result = run(
        refs,
        [order(), order("exit", "sell", limit=850, seconds=2)],
        [frame(), frame("arb", 3, bids=(), asks=((850, 10000),))],
    )
    assert result["positions"] == {"SIM": 100}
    assert result["orders"][1]["status"] == "unfilled"
    assert len(result["fills"]) == 1


def test_partial_queue_multi_level_and_no_reuse(refs: MemoryReferences) -> None:
    policy = replace(POLICY, queue_ahead_shares=100)
    book = frame(asks=((1000, 200), (1005, 250)))
    result = run(refs, [order(shares=400)], [book, replace(book, id="repeat")], policy=policy)
    assert [f["shares"] for f in result["fills"]] == [100, 100]
    assert result["orders"][0] == {"id": "entry", "remaining_shares": 200, "status": "partial"}


def test_spread_slippage_limit_latency_deadline(refs: MemoryReferences) -> None:
    policy = replace(POLICY, latency_ms=2000, slippage_ticks=1)
    result = run(refs, [order(limit=1000)], [frame(), frame("later", 3)], policy=policy)
    assert not result["fills"]
    assert result["decisions"][0]["reason"] == "latency_or_pre_order_book"
    result = run(refs, [order()], [frame(), frame("later", 3)], policy=policy)
    assert result["fills"][0]["price_idr"] == 1005
    assert result["fills"][0]["frame_id"] == "later"
    assert not run(refs, [order()], [frame(seconds=300)])["fills"]


def test_fees_date_visibility_decimal_and_cash_flow(refs: MemoryReferences) -> None:
    orders = [order(), order("sell", "sell", limit=850, seconds=2)]
    books = [frame(), frame("exit", 3)]
    with localcontext() as context:
        context.prec = 6
        result = run(refs, orders, books)
    assert [f["fee_idr"] for f in result["fills"]] == ["110.00", "208.95"]
    assert result["net_cash_flow_idr"] == "-818.95"
    assert result["positions"] == {"SIM": 0}
    future = replace(FEE, version=replace(FEE.version, available_at=AT + timedelta(hours=1)))
    for schedules in ([], [future], [FEE, FEE]):
        assert not replay(
            refs, schedules, [order()], [frame()], policy=POLICY, data_limits=("synthetic",)
        )["fills"]
    assert FEE.charge("buy", Decimal("1")) == Decimal("0.01")


def test_intrabar_stop_first_and_trigger_latency(refs: MemoryReferences) -> None:
    exit_order = replace(order("exit", "sell", limit=850, seconds=2), stop_idr=950, target_idr=1100)
    touched = replace(
        frame("both", 3, bids=((900, 100),), asks=((905, 100),)), low_idr=900, high_idr=1150
    )
    result = run(refs, [order(), exit_order], [frame(), touched])
    assert result["fills"][-1]["trigger"] == "stop"
    assert result["fills"][-1]["price_idr"] == 900
    result = run(
        refs,
        [order(), exit_order],
        [
            frame(),
            touched,
            replace(
                touched,
                id="later",
                event_time=AT + timedelta(seconds=4),
                available_at=AT + timedelta(seconds=4),
            ),
        ],
        policy=replace(POLICY, latency_ms=500),
    )
    assert result["fills"][-1]["frame_id"] == "later"


def test_target_requires_executable_bid_and_no_short(refs: MemoryReferences) -> None:
    sell = replace(order("exit", "sell", limit=850, seconds=2), stop_idr=900, target_idr=1100)
    touched = replace(frame("target", 3), low_idr=1000, high_idr=1150)
    result = run(refs, [order(), sell], [frame(), touched])
    assert result["positions"]["SIM"] == 100
    assert not run(refs, [order("short", "sell", limit=850)], [frame()])["fills"]


def test_unhealthy_reference_invalid_lot_and_missing_reference(refs: MemoryReferences) -> None:
    for book in (
        replace(frame(), synchronized=False),
        replace(frame(), available_at=AT + timedelta(seconds=10)),
    ):
        assert not run(refs, [order()], [book])["fills"]
    assert not run(refs, [order(shares=99)], [frame()])["fills"]
    assert not run(replace(refs, instrument_rules=()), [order()], [frame()])["fills"]


def test_deterministic_report_provenance_and_input_isolation(refs: MemoryReferences) -> None:
    orders = [order()]
    books = [frame("b", 2), frame("a", 1)]
    first = run(refs, orders, books, seed=17)
    assert first == run(refs, orders, list(reversed(books)), seed=17)
    assert first["origin"] == "simulation" and first["live_alerts_enabled"] is False
    assert first["assumptions"] and first["limitations"] and first["fee_schedules"]
    assert first["fills"][0]["reference_versions"]
    assert books[0].asks == ((1000, 1000),)
    with pytest.raises(ValueError, match="restricted"):
        run(refs, orders, books, mode="live")
    with pytest.raises(ValueError, match="Duplicate"):
        run(refs, orders * 2, books)
    with pytest.raises(ValueError, match="limitations"):
        replay(refs, [FEE], orders, books, data_limits=())


def test_fee_transition_and_order_competition(refs: MemoryReferences) -> None:
    boundary = AT + timedelta(seconds=2)
    old = replace(FEE, version=replace(FEE.version, effective_to=boundary))
    new = replace(
        FEE,
        version=replace(FEE.version, id="fees-new", effective_from=boundary),
        buy_broker=Decimal("0.002"),
    )
    result = replay(
        refs,
        [old, new],
        [order(shares=200)],
        [frame(asks=((1000, 100),)), frame("more", 3, asks=((1000, 200),))],
        policy=POLICY,
        data_limits=("synthetic",),
    )
    assert [f["fee_version"] for f in result["fills"]] == ["fees", "fees-new"]
    assert [f["fee_idr"] for f in result["fills"]] == ["110.00", "210.00"]
    result = run(refs, [order("b"), order("a")], [frame(asks=((1000, 100),))])
    assert [f["order_id"] for f in result["fills"]] == ["a"]


def test_invalid_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="Crossed"):
        frame(bids=((1000, 100),), asks=((995, 100),))
    with pytest.raises(ValueError, match="unique and sorted"):
        frame(asks=((1005, 100), (1000, 100)))
    with pytest.raises(ValueError, match="nonnegative"):
        ReplayPolicy(slippage_ticks=-1)
    with pytest.raises(ValueError, match="fractions"):
        replace(FEE, buy_broker=Decimal("NaN"))
