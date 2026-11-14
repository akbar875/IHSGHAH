"""Deterministic confirmed-fill ledger. Market prices never create or settle a position."""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from saham_signal.application.market import MarketScope, stamp, validate


class PositionConflict(ValueError):
    pass


class PositionMissing(ValueError):
    pass


class PositionStore(Protocol):
    def list(self, scope: MarketScope) -> list[dict[str, Any]]: ...

    def execute(
        self, scope: MarketScope, key: str, command: dict[str, Any], at: datetime
    ) -> dict[str, Any]: ...


def money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def transition(
    scope: MarketScope,
    previous: dict[str, Any] | None,
    command: dict[str, Any],
    at: datetime,
    event_key: str = "",
) -> dict[str, Any]:
    with localcontext() as context:
        context.prec = 80
        return _transition(scope, previous, command, at, event_key)


def _transition(
    scope: MarketScope,
    previous: dict[str, Any] | None,
    command: dict[str, Any],
    at: datetime,
    event_key: str = "",
) -> dict[str, Any]:
    action, data = command["action"], command["data"]
    state = deepcopy(previous)
    if action == "open":
        validate("OpenPositionRequest", data)
        if data["signal_id"] is not None:
            # Unvalidated fixture signals cannot become execution authority.
            raise ValueError("Manual entries must not claim a validated signal")
        state = {
            "position": {
                "position_id": str(
                    uuid5(
                        NAMESPACE_URL,
                        json.dumps([scope.mode, scope.account, event_key, command], sort_keys=True),
                    )
                ),
                "user_id": scope.account,
                "symbol": data["symbol"],
                "fills": [],
                "remaining_lots": 0,
                "average_price_idr": "0.01",
                "fees_idr": "0.00",
                "opened_at": data["fill"]["filled_at"],
                "plan_version": 1,
                "status": "OPEN",
                "overnight_risk": False,
            },
            "plan": None,
            "invested_idr": "0.00",
            "remaining_cost_idr": "0.00",
            "realized_pnl_idr": "0.00",
            "exit_reason": None,
            "basis": "0",
            "realized": "0",
            "average": "0",
        }
        fill = data["fill"]
    else:
        if state is None:
            raise PositionMissing
        if state["position"]["status"] == "CLOSED":
            raise PositionConflict("Position already closed")
        fill = data if action == "fill" else None
    assert state is not None
    position = state["position"]
    if (
        state["plan"]
        and position["remaining_lots"]
        and at >= datetime.fromisoformat(state["plan"]["exit_deadline"])
    ):
        position["status"] = "EXIT_REQUESTED"
        state["exit_reason"] = state["exit_reason"] or "DEADLINE"
    if fill is not None:
        validate("FillRequest", fill)
        when = datetime.fromisoformat(fill["filled_at"])
        if when > at or (
            position["fills"] and when < datetime.fromisoformat(position["fills"][-1]["filled_at"])
        ):
            raise ValueError("Fill time must be chronological and not in the future")
        lots = fill["lots"]
        remaining = position["remaining_lots"]
        price, fees = Decimal(fill["price_idr"]), Decimal(fill["fees_idr"])
        basis, average = Decimal(state["basis"]), Decimal(state["average"])
        if fill["side"] == "BUY":
            if position["status"] == "EXIT_REQUESTED":
                raise PositionConflict("Cannot add while exit is pending")
            average = (average * remaining + price * lots) / (remaining + lots)
            basis += price * lots * 100 + fees
            remaining += lots
            state["invested_idr"] = money(
                Decimal(state["invested_idr"]) + price * lots * 100 + fees
            )
        else:
            if lots > remaining:
                raise PositionConflict("Sell exceeds confirmed remaining lots")
            sold_basis = basis * lots / remaining
            realized = Decimal(state["realized"]) + price * lots * 100 - fees - sold_basis
            state["realized"] = str(realized)
            state["realized_pnl_idr"] = money(realized)
            basis -= sold_basis
            remaining -= lots
        state.update(basis=str(basis), average=str(average), remaining_cost_idr=money(basis))
        position.update(
            remaining_lots=remaining,
            average_price_idr=money(average),
            fees_idr=money(Decimal(position["fees_idr"]) + fees),
        )
        position["fills"].append(
            {
                **fill,
                "fill_id": str(
                    uuid5(NAMESPACE_URL, f"{position['position_id']}:{position['plan_version']}")
                ),
                "position_id": position["position_id"],
                "recorded_at": stamp(at),
                "origin": "manual",
            }
        )
        if remaining == 0:
            position["status"] = "CLOSED"
        elif position["status"] != "EXIT_REQUESTED":
            position["status"] = (
                "PARTIAL" if any(f["side"] == "SELL" for f in position["fills"]) else "OPEN"
            )
    elif action == "plan":
        validate("PositionPlan", data)
        if not Decimal(data["stop_idr"]) < Decimal(state["average"]) < Decimal(data["target_idr"]):
            raise ValueError("Stop < actual average < target required")
        if datetime.fromisoformat(data["exit_deadline"]) <= datetime.fromisoformat(
            position["opened_at"]
        ):
            raise ValueError("Deadline must follow the opening fill")
        state["plan"] = deepcopy(data)
    elif action == "exit":
        validate("ExitRequest", data)
        position["status"] = "EXIT_REQUESTED"
        state["exit_reason"] = data["reason"]
    else:
        raise ValueError("Unknown position command")
    if previous is not None:
        position["plan_version"] += 1
    validate("Position", position)
    monitor(state, at)  # Validate every derived amount before committing the snapshot.
    return state


def monitor(state: dict[str, Any], at: datetime) -> dict[str, Any]:
    with localcontext() as context:
        context.prec = 80
        return _monitor(state, at)


def _monitor(state: dict[str, Any], at: datetime) -> dict[str, Any]:
    result = {k: deepcopy(v) for k, v in state.items() if k not in {"basis", "average", "realized"}}
    position, plan = result["position"], result["plan"]
    local = at.astimezone(timezone(timedelta(hours=7)))
    opened = datetime.fromisoformat(position["opened_at"]).astimezone(timezone(timedelta(hours=7)))
    remaining = position["remaining_lots"]
    position["overnight_risk"] = remaining > 0 and (
        opened.date() < local.date() or (local.hour, local.minute) >= (15, 30)
    )
    # 15:30 WIB is a conservative UI warning, not a validated exchange calendar/cutoff.
    if remaining and plan and at >= datetime.fromisoformat(plan["exit_deadline"]):
        position["status"] = "EXIT_REQUESTED"
        result["exit_reason"] = result["exit_reason"] or "DEADLINE"
    result.update(stop_loss_idr=None, target_net_idr=None)
    if plan:
        shares = remaining * 100
        fee = Decimal(plan["sell_fee_ratio"])
        basis = Decimal(state["basis"])
        result["stop_loss_idr"] = money(
            max(Decimal(0), basis - Decimal(plan["stop_idr"]) * shares * (1 - fee))
        )
        result["target_net_idr"] = money(Decimal(plan["target_idr"]) * shares * (1 - fee) - basis)
    validate("PositionMonitor", result)
    return result
