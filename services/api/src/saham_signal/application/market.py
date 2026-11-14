"""Research-only read model. No vendor/model output can enter this fixture service."""

import json
from collections import OrderedDict
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from importlib.resources import files
from threading import RLock
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from saham_signal.domain.mode import Mode


def stamp(at: datetime) -> str:
    return at.isoformat().replace("+00:00", "Z")


@lru_cache(maxsize=16)
def validator(name: str) -> Draft202012Validator:
    # Same packaged schema used by persistence; never serialize arbitrary upstream maps.
    schema = json.loads(files("saham_signal").joinpath("storage_contract.json").read_text())
    return Draft202012Validator(
        {"$ref": f"#/$defs/{name}", "$defs": schema["$defs"]}, format_checker=FormatChecker()
    )


def validate(name: str, payload: Any) -> None:
    validator(name).validate(payload)


@dataclass(frozen=True)
class MarketScope:
    account: str
    mode: Mode
    nominal_idr: str
    horizon_minutes: int
    configuration_version: str = "fixture-config-1"


class MarketUnavailable(Exception):
    pass


class MarketNotFound(Exception):
    pass


class FixtureMarket:
    """One synthetic scenario, anchored once at startup; time never refreshes its inputs.

    SS-016 has no promoted artifact (G1 no-go). Production reads remain unavailable,
    including paper/live; this class deliberately has no model/provider injection path.
    """

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(UTC))
        self.lock = RLock()
        self.started = self.clock()
        self.fixture = json.loads(
            files("saham_signal").joinpath("fixtures/market-simulation.json").read_text()
        )
        self.cache: OrderedDict[tuple[MarketScope, str, str | None, str], dict[str, Any]] = (
            OrderedDict()
        )

    def read(
        self, scope: MarketScope, resource: str, symbol: str | None = None, interval: str = "1m"
    ) -> dict[str, Any]:
        with self.lock:
            return self._read(scope, resource, symbol, interval)

    def _read(
        self, scope: MarketScope, resource: str, symbol: str | None = None, interval: str = "1m"
    ) -> dict[str, Any]:
        if scope.mode != "research":
            raise MarketUnavailable
        if symbol is not None and symbol != "TEST":
            raise MarketNotFound
        key = (scope, resource, symbol, interval)
        expires = self.started + timedelta(minutes=scope.horizon_minutes)
        expired = self.clock() >= expires
        # A time-dependent phase is part of cache validity, not a new expiry for old data.
        if key in self.cache:
            item = self.cache.pop(key)
            if item["expired"] == expired:
                self.cache[key] = item
                return deepcopy(item["response"])

        signal = deepcopy(self.fixture["CandidatesResponse"]["data"][0])
        signal.update(
            generated_at=stamp(self.started),
            data_as_of=stamp(self.started),
            entry_from=stamp(self.started),
            valid_until=stamp(expires),
            entry_until=stamp(expires),
            exit_deadline=stamp(expires),
            horizon_minutes=scope.horizon_minutes,
            configuration_version=scope.configuration_version,
        )
        signal["assumptions"]["nominal_idr"] = scope.nominal_idr
        original = deepcopy(signal)
        if expired:
            signal.update(
                state="EXPIRED", version=2, invalidation="TIME_EXPIRED", generated_at=stamp(expires)
            )
        names = {
            "candidates": "CandidatesResponse",
            "detail": "StockDetailResponse",
            "depth": "DepthResponse",
            "chart": "ChartResponse",
            "history": "SignalHistoryResponse",
        }
        name = names[resource]
        response = deepcopy(self.fixture[name])
        response["as_of"] = stamp(expires if expired else self.started)
        if resource == "candidates":
            response["data"] = [] if expired else [signal]
        elif resource == "history":
            response["data"] = [original, signal] if expired else [original]
        elif resource == "detail":
            detail = response["data"]
            detail["signal"] = signal
            # No sizing estimate is available for arbitrary nominal/horizon settings.
            detail["liquidity"] = None
            detail["depth"]["depth_as_of"] = stamp(self.started)
        elif resource == "depth":
            response["data"]["depth_as_of"] = stamp(self.started)
        elif resource == "chart":
            response["data"]["interval"] = interval
            # Only the 1m scenario exists. Do not relabel a 1m bar as 5m or 15m.
            if interval != "1m":
                response["data"]["candles"] = []
            else:
                response["data"]["candles"][0]["at"] = stamp(
                    self.started.replace(second=0, microsecond=0) - timedelta(minutes=1)
                )
        validate(name, response)
        self.cache[key] = {"expired": expired, "response": response}
        while len(self.cache) > 128:
            self.cache.popitem(last=False)
        return deepcopy(response)
