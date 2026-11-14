"""In-memory test double only; runtime always uses PostgreSQL."""

from copy import deepcopy
from typing import Any

from saham_signal.application.market import MarketScope
from saham_signal.application.preferences import PreferenceConflict, validate_preference


class MemoryPreferences:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def get(self, scope: MarketScope, kind: str) -> dict[str, Any] | None:
        rows = [v for k, v in self.rows.items() if k[:3] == (scope.mode, scope.account, kind)]
        return deepcopy(rows[-1]) if rows else None

    def put(
        self, scope: MarketScope, kind: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        validate_preference(kind, payload)
        identity = (scope.mode, scope.account, kind, key)
        if identity in self.rows:
            if self.rows[identity] != payload:
                raise PreferenceConflict()
            return deepcopy(self.rows[identity])
        for identity_before, row in self.rows.items():
            if (
                kind == "RiskSettings"
                and identity_before[:3] == identity[:3]
                and (
                    row["configuration_version"] == payload["configuration_version"]
                    or (
                        row["fee_schedule_version"] == payload["fee_schedule_version"]
                        and row["fee_schedule"] != payload["fee_schedule"]
                    )
                )
            ):
                raise PreferenceConflict()
        self.rows[identity] = deepcopy(payload)
        return deepcopy(payload)
