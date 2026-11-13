"""Transport-independent ingest boundary; no vendor connection or live authorization.

Vendor decoders must explicitly map their documented semantics to FeedMessage.
The commit port runs before any in-memory cursor/book advances.
"""

import re
from collections.abc import Callable, Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from saham_signal.application.feed_quality import (
    FeedAssessment,
    FeedQuality,
    FeedSLA,
    PositionDataDisruption,
)
from saham_signal.domain.instruments import aware
from saham_signal.domain.mode import Mode
from saham_signal.domain.persistence import Record, digest

type EventType = Literal["trade", "candle", "book_snapshot", "book_delta", "heartbeat"]


@dataclass(frozen=True)
class FeedProfile:
    """An exact semantics identity, pinned for the lifetime of an ingest session."""

    source: str
    schema_ref: str
    origin: Literal["simulation", "market"]
    delivery: Literal["live", "delayed"]
    volume_unit: Literal["shares", "lots"]
    approval_ref: str | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.source):
            raise ValueError("Invalid source identity")
        if (
            not self.schema_ref
            or len(self.schema_ref) > 256
            or self.origin not in ("simulation", "market")
        ):
            raise ValueError("Missing schema or unknown provenance")
        if self.delivery not in ("live", "delayed") or self.volume_unit not in ("shares", "lots"):
            raise ValueError("Unsupported feed semantics")
        if self.origin == "market" and not self.approval_ref:
            raise ValueError("Market data requires an explicit evidence reference")


@dataclass(frozen=True)
class FeedMessage:
    profile: FeedProfile
    connection: int
    event_id: str
    symbol: str
    kind: EventType
    sequence: int
    event_time: datetime
    provider_time: datetime | None
    payload: dict[str, Any]
    revision: int = 1


@dataclass(frozen=True)
class Observation:
    """Candle uses shared Candle schema; v1 MarketEvent has no candle tag.

    Keep its provenance/timing envelope here, never disguise it as a trade.
    A durable candle envelope requires a separately reviewed contract extension.
    """

    message: FeedMessage
    received_at: datetime
    available_at: datetime
    processed_at: datetime
    schema: Literal["MarketEvent", "Candle"]
    payload: dict[str, Any]
    record: Record | None
    out_of_order: bool


@dataclass
class Book:
    sequence: int = -1
    floor: int = -1
    synchronized: bool = False
    bids: dict[str, int] = field(default_factory=dict)
    asks: dict[str, int] = field(default_factory=dict)


def stamp(value: datetime) -> str:
    aware(value)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def price(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
        raise ValueError("Prices must be exact IDR strings with two decimals")
    if not Decimal("0") < Decimal(value) < Decimal("10000000000000000"):
        raise ValueError("Price outside contract range")
    return format(Decimal(value), ".2f")


class FeedIngestor:
    """Sequential, single-writer session. Call reconnect on every transport reset.

    snapshot_request must arrange a fresh snapshot for the current connection.
    commit must atomically persist an observation or raise without committing.
    validate checks the named shared contract; malformed messages are surfaced,
    never silently dropped. A caller owns raw quarantine and bounded session rotation.
    """

    def __init__(
        self,
        profile: FeedProfile,
        mode: Mode,
        *,
        lot_shares: Callable[[str, datetime, datetime], int],
        validate: Callable[[str, dict[str, Any]], None],
        commit: Callable[[Observation], None],
        snapshot_request: Callable[[str, int], None],
        sla: FeedSLA | None = None,
    ) -> None:
        if mode not in ("research", "paper", "live"):
            raise ValueError("Unknown mode")
        if mode == "live" and profile.origin == "simulation":
            raise ValueError("Simulation cannot enter live mode")
        self.profile, self.mode = profile, mode
        self.lot_shares, self.validate, self.commit = lot_shares, validate, commit
        self.snapshot_request = snapshot_request
        self.quality_monitor = FeedQuality(profile, sla or FeedSLA(), mode)
        self.connection = 1
        self.books: dict[str, Book] = {}
        self.seen: dict[tuple[str, int], str] = {}
        self.revisions: dict[str, int] = {}
        self.identities: dict[str, tuple[str, str]] = {}
        self.event_times: dict[tuple[str, str], datetime] = {}

    def reconnect(self) -> None:
        self.connection += 1
        self.quality_monitor.reconnect()
        for symbol in self.books:
            self.books[symbol] = Book()
        for symbol in self.books:
            self.snapshot_request(symbol, self.connection)

    def _resync(self, symbol: str, sequence: int) -> None:
        self.quality_monitor.invalidate(symbol, gap=sequence >= 0)
        book = self.books.setdefault(symbol, Book())
        book.synchronized = False
        book.floor = max(book.floor, sequence)
        # Retry the request on subsequent messages if a prior request failed.
        self.snapshot_request(symbol, self.connection)

    def assess_quality(
        self,
        symbol: str,
        now: datetime,
        *,
        active_positions: Iterable[str] = (),
        emit: Callable[[PositionDataDisruption], None] | None = None,
    ) -> FeedAssessment:
        """Poll on a timer and immediately before using inputs for entry/exit.

        Caller supplies account-scoped active position IDs and a durable warning
        sink. A warning never closes a position. Entry still needs all other gates.
        """
        self.quality_monitor.assess(symbol, now)
        state = self.quality_monitor.streams[symbol]
        book = self.books.get(symbol)
        request_snapshot = state.invalidate_book and book is not None and book.synchronized
        state.invalidate_book = False
        if request_snapshot and book is not None:
            book.synchronized = False
        assessment = self.quality_monitor.assess(
            symbol, now, active_positions=active_positions, emit=emit
        )
        # Publish warnings even if the disconnected transport cannot request data.
        if request_snapshot:
            self.snapshot_request(symbol, self.connection)
        return assessment

    def _lots(self, quantity: Any, message: FeedMessage, known_at: datetime) -> int:
        if type(quantity) is not int or quantity < 0:
            raise ValueError("Volume must be a nonnegative integer")
        if self.profile.volume_unit == "shares":
            size = self.lot_shares(message.symbol, message.event_time, known_at)
            if type(size) is not int or size <= 0 or quantity % size:
                raise ValueError("Missing lot rule or fractional lot")
            quantity //= size
        if quantity > 2147483647:
            raise ValueError("Volume outside contract range")
        return int(quantity)

    def _levels(self, rows: Any, message: FeedMessage, known_at: datetime) -> dict[str, int]:
        if not isinstance(rows, list) or len(rows) > 50:
            raise ValueError("Expected at most 50 price levels")
        levels: dict[str, int] = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"price_idr", "quantity"}:
                raise ValueError("Invalid price level")
            key = price(row["price_idr"])
            if key in levels:
                raise ValueError("Repeated price level")
            levels[key] = self._lots(row["quantity"], message, known_at)
        return levels

    def _book_payload(self, message: FeedMessage, book: Book) -> dict[str, Any]:
        def side(levels: dict[str, int], reverse: bool) -> list[dict[str, Any]]:
            total = 0
            result = []
            for key in sorted(levels, key=Decimal, reverse=reverse):
                total += levels[key]
                result.append({"price_idr": key, "lots": levels[key], "cumulative_lots": total})
            return result

        if len(book.bids) > 50 or len(book.asks) > 50:
            raise ValueError("Book exceeds supported depth")
        if book.bids and book.asks and max(map(Decimal, book.bids)) >= min(map(Decimal, book.asks)):
            raise ValueError("Crossed/locked continuous-session book")
        return {
            "symbol": message.symbol,
            "snapshot_id": message.event_id,
            "sequence": str(message.sequence),
            "depth_as_of": stamp(message.event_time),
            "bids": side(book.bids, True),
            "asks": side(book.asks, False),
            "available_levels": min(len(book.bids), len(book.asks)),
            "limited": min(len(book.bids), len(book.asks)) < 5,
        }

    def ingest(
        self,
        message: FeedMessage,
        *,
        received_at: datetime,
        available_at: datetime,
        processed_at: datetime,
    ) -> Literal["committed", "duplicate", "resync_required"]:
        # Never retain caller-owned mutable dictionaries in cursors or sink objects.
        message = deepcopy(message)
        if message.profile != self.profile or message.connection != self.connection:
            raise ValueError("Feed semantics changed or stale connection")
        for value in (message.event_time, received_at, available_at, processed_at):
            aware(value)
        if message.provider_time is not None:
            aware(message.provider_time)
        if not received_at <= available_at <= processed_at:
            raise ValueError("Invalid availability order")
        self.assess_quality(message.symbol, processed_at)
        if (
            type(message.sequence) is not int
            or not 0 <= message.sequence < 10**20
            or type(message.revision) is not int
            or not 1 <= message.revision <= 2147483647
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", message.event_id)
            or not re.fullmatch(r"[A-Z][A-Z0-9.]{0,11}", message.symbol)
        ):
            raise ValueError("Invalid event identity, revision or sequence")
        identity = (message.event_id, message.revision)
        fingerprint = digest(
            {
                "symbol": message.symbol,
                "kind": message.kind,
                "sequence": message.sequence,
                "event_time": stamp(message.event_time),
                "provider_time": stamp(message.provider_time) if message.provider_time else None,
                "payload": message.payload,
            }
        )
        if identity in self.seen:
            if self.seen[identity] != fingerprint:
                if message.kind in ("book_snapshot", "book_delta"):
                    self._resync(message.symbol, message.sequence)
                raise ValueError("Conflicting retransmission; quarantine required")
            return "duplicate"
        if message.revision != self.revisions.get(message.event_id, 0) + 1:
            raise ValueError("Correction requires consecutive known revisions")
        if message.event_id in self.identities and self.identities[message.event_id] != (
            message.symbol,
            message.kind,
        ):
            raise ValueError("Correction changed event identity")
        data = message.payload
        next_book: Book | None = None
        event_type: str = message.kind
        if message.kind in ("book_snapshot", "book_delta"):
            current = self.books.setdefault(message.symbol, Book())
            if message.revision != 1:
                self._resync(message.symbol, message.sequence)
                return "resync_required"
            if message.kind == "book_delta" and (
                not current.synchronized or message.sequence != current.sequence + 1
            ):
                self._resync(message.symbol, message.sequence)
                return "resync_required"
            if message.kind == "book_snapshot" and message.sequence < max(
                current.sequence + 1, current.floor
            ):
                self._resync(message.symbol, max(current.sequence, current.floor))
                return "resync_required"
            try:
                if set(data) != {"bids", "asks"}:
                    raise ValueError("Unknown book fields")
                next_book = deepcopy(current) if message.kind == "book_delta" else Book()
                for name in ("bids", "asks"):
                    levels = getattr(next_book, name)
                    for key, lots in self._levels(data[name], message, available_at).items():
                        if lots:
                            levels[key] = lots
                        else:
                            levels.pop(key, None)
                next_book.sequence = message.sequence
                next_book.floor = message.sequence
                next_book.synchronized = True
                payload = self._book_payload(message, next_book)
            except Exception:
                self._resync(message.symbol, message.sequence)
                raise
            event_type = "book_snapshot"
        elif message.kind == "trade":
            if set(data) != {"price_idr", "quantity", "aggressor"}:
                raise ValueError("Unknown trade fields")
            payload = {
                "price_idr": price(data["price_idr"]),
                "lots": self._lots(data["quantity"], message, available_at),
                "aggressor": data["aggressor"],
            }
        elif message.kind == "heartbeat":
            if set(data) != {"status"}:
                raise ValueError("Unknown heartbeat fields")
            payload = {"status": data["status"], "heartbeat_at": stamp(message.event_time)}
            event_type = "feed_status"
            if data["status"] != "healthy" and message.symbol in self.books:
                self._resync(message.symbol, -1)
        elif message.kind == "candle":
            if set(data) != {"at", "open_idr", "high_idr", "low_idr", "close_idr", "quantity"}:
                raise ValueError("Unknown candle fields")
            payload = {
                name: price(data[name]) for name in ("open_idr", "high_idr", "low_idr", "close_idr")
            }
            low, high = Decimal(payload["low_idr"]), Decimal(payload["high_idr"])
            if not low <= min(Decimal(payload["open_idr"]), Decimal(payload["close_idr"])):
                raise ValueError("Invalid candle low")
            if not high >= max(Decimal(payload["open_idr"]), Decimal(payload["close_idr"])):
                raise ValueError("Invalid candle high")
            payload.update(
                at=data["at"], volume_lots=self._lots(data["quantity"], message, available_at)
            )
        else:
            raise ValueError("Unsupported event type")
        channel = (message.symbol, "book" if next_book is not None else message.kind)
        previous_time = self.event_times.get(channel)
        out_of_order = previous_time is not None and message.event_time < previous_time
        record = None
        schema: Literal["MarketEvent", "Candle"] = "Candle"
        if message.kind != "candle":
            schema = "MarketEvent"
            reasons = ["SIMULATION"] if self.profile.origin == "simulation" else []
            if self.profile.delivery == "delayed":
                reasons.append("DELAYED_FEED")
            if (
                next_book is None
                and message.symbol in self.books
                and not self.books[message.symbol].synchronized
            ):
                reasons.append("RESYNC_REQUIRED")
            status = "degraded" if reasons else "healthy"
            if message.kind == "heartbeat" and data["status"] != "healthy":
                status = data["status"]
            entity_id = "feed-" + digest({"source": self.profile.source, "id": message.event_id})
            payload = {
                "contract_version": "1.0.0",
                "as_of": stamp(available_at),
                "mode": self.mode,
                "data_origin": self.profile.origin,
                "quality": {
                    "status": status,
                    "feed": "disconnected" if status == "disconnected" else self.profile.delivery,
                    "last_heartbeat_at": stamp(message.event_time)
                    if message.kind == "heartbeat"
                    else None,
                    "reasons": reasons,
                },
                "event_id": entity_id,
                "symbol": message.symbol,
                "event_type": event_type,
                "event_time": stamp(message.event_time),
                "provider_time": stamp(message.provider_time) if message.provider_time else None,
                "received_at": stamp(received_at),
                "available_at": stamp(available_at),
                "processed_at": stamp(processed_at),
                "sequence": str(message.sequence),
                "source": self.profile.source,
                "payload": payload,
            }
            record = Record(
                kind="MarketEvent",
                entity_id=entity_id,
                version=message.revision,
                idempotency_key=f"{entity_id}:{message.revision}",
                event_time=message.event_time,
                provider_time=message.provider_time,
                received_at=received_at,
                available_at=available_at,
                processed_at=processed_at,
                sequence=str(message.sequence),
                source=self.profile.source,
                data_origin=self.profile.origin,
                actor="feed-ingest",
                reason=f"schema={self.profile.schema_ref}; upstream={fingerprint}",
                payload=payload,
            )
            record.document(self.mode, "")
        try:
            self.validate(schema, payload)
        except Exception:
            if next_book is not None:
                self._resync(message.symbol, message.sequence)
            raise
        observation = Observation(
            message, received_at, available_at, processed_at, schema, payload, record, out_of_order
        )
        self.commit(observation)
        self.seen[identity] = fingerprint
        self.revisions[message.event_id] = message.revision
        self.identities[message.event_id] = (message.symbol, message.kind)
        self.event_times[channel] = (
            max(previous_time, message.event_time) if previous_time else (message.event_time)
        )
        if next_book is not None:
            self.books[message.symbol] = next_book
        self.quality_monitor.observe(observation)
        return "committed"
