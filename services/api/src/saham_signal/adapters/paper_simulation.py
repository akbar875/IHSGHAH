"""Invented qualification input; deliberately has no vendor or credential port."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import Any

from saham_signal.adapters.evaluation_simulation import fixture
from saham_signal.application.evaluation import Baseline
from saham_signal.application.feed import FeedMessage, FeedProfile
from saham_signal.application.market import stamp
from saham_signal.application.operations import Action, Control, Operations
from saham_signal.application.paper import ObservationProtocol, qualify
from saham_signal.domain.mode import Mode


class SimulationControl:
    def write(
        self, mode: Mode, expected: int, action: Action, release: str, evidence: str, actor: str
    ) -> Control:
        raise ValueError("Offline simulation control is read-only")

    def read(self, mode: Mode) -> Control:
        if mode != "paper":
            raise ValueError("Paper simulation only")
        return Control(1, False, "resume", "SS-026-offline-only")


def scenario() -> dict[str, Any]:
    _, cases, references, fees = fixture()
    case = cases[0]
    spec = replace(case.spec, mode="paper", entry_idr=1010)
    inputs = replace(case.inputs, portfolio=replace(case.inputs.portfolio, mode="paper"))
    at = inputs.at
    profile = FeedProfile("simulation:SS-026", "SS-026-v1", "simulation", "live", "shares")
    events: list[tuple[FeedMessage, Any]] = []

    def add(kind: Any, seconds: int, payload: dict[str, Any]) -> None:
        when = at + timedelta(seconds=seconds)
        message = FeedMessage(
            profile,
            1,
            f"event-{len(events)}",
            spec.symbol,
            kind,
            len(events) + 1,
            when,
            None,
            payload,
        )
        events.append((message, when))

    for seconds, price in [(-20, "995.00"), (-10, "1000.00"), (-1, "1005.00")]:
        add("trade", seconds, {"price_idr": price, "quantity": 100, "aggressor": "buyer"})
    add("heartbeat", 0, {"status": "healthy"})
    book = {
        "bids": [{"price_idr": "1000.00", "quantity": 10000}],
        "asks": [{"price_idr": "1005.00", "quantity": 10000}],
    }
    add("book_snapshot", 0, book)
    add("book_snapshot", 1, book)
    add("heartbeat", 59, {"status": "healthy"})
    add(
        "candle",
        60,
        {
            "at": stamp(at),
            "open_idr": "1000.00",
            "low_idr": "1000.00",
            "high_idr": "1160.00",
            "close_idr": "1150.00",
            "quantity": 1000,
        },
    )
    target = {
        "bids": [{"price_idr": "1155.00", "quantity": 10000}],
        "asks": [{"price_idr": "1160.00", "quantity": 10000}],
    }
    add("book_snapshot", 60, target)
    add("book_snapshot", 61, target)
    return {
        "profile": profile,
        "messages": events,
        "spec": spec,
        "inputs": inputs,
        "baseline": Baseline("paper-smoke", "trend", Decimal(0), Decimal("0.1"), False, False),
        "references": references,
        "fees": fees,
        "operations": Operations(SimulationControl(), "paper"),
        "protocol": ObservationProtocol(at - timedelta(days=1), at + timedelta(days=1)),
    }


def run() -> dict[str, Any]:
    return qualify(**scenario())
