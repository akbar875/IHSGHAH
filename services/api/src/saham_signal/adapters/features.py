"""Validated feature boundary shared by a committed feed sink and journal replay."""

from typing import Any

from saham_signal.adapters.feed import validate_observation
from saham_signal.application.features import FeatureEngine
from saham_signal.application.feed import Observation


class FeatureConsumer:
    def __init__(self, engine: FeatureEngine) -> None:
        self.engine = engine

    def committed(self, observation: Observation) -> None:
        """Call after durable commit, never instead of MarketJournalSink.

        A failed consumer can be rebuilt from the durable journal. Candles are not
        used: trade-based volume avoids counting a trade and its candle twice.
        """
        if observation.record is not None:
            self.event(observation.payload, observation.record.version)

    def journal_row(self, row: dict[str, Any]) -> None:
        if row["kind"] != "MarketEvent":
            return
        if row["user_id"] or row["mode"] != self.engine.mode:
            raise ValueError("Expected market journal in the engine mode")
        self.event(row["payload"], row["version"])

    def event(self, payload: dict[str, Any], revision: int) -> None:
        validate_observation("MarketEvent", payload)
        self.engine.observe(payload, revision)
