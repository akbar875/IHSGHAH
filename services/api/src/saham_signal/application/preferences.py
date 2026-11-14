"""Personal configuration validation; fee inputs are always unverified assumptions."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from saham_signal.application.market import MarketScope, validate


class PreferenceConflict(ValueError):
    pass


class PreferenceStore(Protocol):
    def get(self, scope: MarketScope, kind: str) -> dict[str, Any] | None: ...

    def put(
        self, scope: MarketScope, kind: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...


def validate_preference(kind: str, payload: dict[str, Any]) -> None:
    validate("RiskProfile" if kind == "RiskSettings" else kind, payload)
    if kind == "Watchlist":
        return
    nominal = Decimal(payload["nominal_idr"])
    capital = Decimal(payload["capital_idr"])
    risk = Decimal(payload["risk_per_position_ratio"])
    combined = Decimal(payload["max_combined_risk_ratio"])
    if not nominal <= capital or not 0 < risk <= Decimal("0.01"):
        raise ValueError("Nominal exceeds capital or risk exceeds pilot cap")
    if not risk <= combined <= Decimal("0.02") or payload["max_positions"] > 3:
        raise ValueError("Invalid aggregate risk or pilot position cap")
    fee = payload.get("fee_schedule")
    if fee is None or fee["version"] != payload["fee_schedule_version"]:
        raise ValueError("Explicit dated fee assumptions required")
    if not fee["source"].strip():
        raise ValueError("Fee source required")
    if datetime.fromisoformat(fee["effective_from"]) >= datetime.fromisoformat(fee["effective_to"]):
        raise ValueError("Invalid fee validity interval")


def fees_current(settings: dict[str, Any], at: datetime) -> bool:
    fee = settings["fee_schedule"]
    return (
        datetime.fromisoformat(fee["effective_from"])
        <= at
        < datetime.fromisoformat(fee["effective_to"])
    )


def eligibility(settings: dict[str, Any], at: datetime) -> dict[str, Any]:
    """Budget ceiling for the TEST fixture, never an executable quantity or fill estimate."""
    capital = Decimal(settings["capital_idr"])
    budget = capital * Decimal(settings["risk_per_position_ratio"])
    aggregate = capital * Decimal(settings["max_combined_risk_ratio"])
    current = fees_current(settings, at)
    fee = settings["fee_schedule"]
    buy = Decimal(fee["buy_ratio"])
    sell = Decimal(fee["sell_ratio"])
    # Synthetic upper entry 1010, stop 990, 100 shares/lot. No liquidity assumption.
    cash_per_lot = Decimal(101000) * (1 + buy)
    loss_per_lot = cash_per_lot - Decimal(99000) * (1 - sell)
    cash_lots = int(min(capital, Decimal(settings["nominal_idr"])) // cash_per_lot)
    risk_lots = int(min(budget, aggregate) // loss_per_lot)
    return {
        "configuration_version": settings["configuration_version"],
        "risk_budget_idr": str(budget.quantize(Decimal("0.01"))),
        "combined_budget_idr": str(aggregate.quantize(Decimal("0.01"))),
        "budget_lots_ceiling": min(cash_lots, risk_lots) if current else 0,
        "eligible_lots": 0,
        "reason": "MODEL_UNVALIDATED" if current else "FEE_SCHEDULE_EXPIRED",
    }
