"""Internal-only news boundary. No network, tools, trading or serving capabilities."""

import hashlib
import re
import unicodedata
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saham_signal.domain.instruments import aware


class InternalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SourceGrant(InternalModel):
    """Operator configuration, never read from an external document/model response."""

    source: str = Field(min_length=1, max_length=128)
    evidence: str = Field(min_length=1, max_length=256)
    valid_from: datetime
    valid_to: datetime
    storage: bool = False
    analysis: bool = False
    llm_processing: bool = False
    origin: Literal["simulation", "licensed"]
    credibility: Literal["official", "verified", "unverified"]

    @model_validator(mode="after")
    def dates(self) -> "SourceGrant":
        aware(self.valid_from)
        aware(self.valid_to)
        if self.valid_from >= self.valid_to:
            raise ValueError("Invalid grant interval")
        return self

    def authorize(self, at: datetime, *, llm: bool = False) -> None:
        aware(at)
        if not (
            self.valid_from <= at < self.valid_to
            and self.storage
            and self.analysis
            and (not llm or self.llm_processing)
        ):
            raise ValueError("Source rights unavailable")


class NewsInput(InternalModel):
    document_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1, le=2147483647)
    published_at: datetime
    text: str = Field(min_length=1, max_length=32000)
    mime: Literal["text/plain"] = "text/plain"

    @model_validator(mode="after")
    def safe_size(self) -> "NewsInput":
        aware(self.published_at)
        if not self.text.strip() or len(self.text.encode("utf-8")) > 64000:
            raise ValueError("Empty or oversized document")
        return self


class Extraction(InternalModel):
    """Only data fields; instructions, URLs, prices and tool calls are not fields."""

    symbols: tuple[str, ...] = Field(max_length=20)
    event: Literal["disclosure", "earnings", "corporate_action", "other"]
    summary: str = Field(max_length=1000)
    method: Literal["deterministic", "llm"]
    version: str = Field(min_length=1, max_length=128)


class NewsRecord(InternalModel):
    source: str
    grant: SourceGrant
    document: NewsInput
    content_hash: str
    received_at: datetime
    available_at: datetime
    extraction: Extraction

    @model_validator(mode="after")
    def valid(self) -> "NewsRecord":
        aware(self.received_at)
        aware(self.available_at)
        self.grant.authorize(self.received_at, llm=self.extraction.method == "llm")
        self.grant.authorize(self.available_at, llm=self.extraction.method == "llm")
        if (
            self.source != self.grant.source
            or self.content_hash != content_hash(self.document.text)
            or self.available_at < max(self.received_at, self.document.published_at)
            or any(not re.fullmatch(r"[A-Z]{4}", s) for s in self.extraction.symbols)
            or len(set(self.extraction.symbols)) != len(self.extraction.symbols)
        ):
            raise ValueError("Invalid news provenance/availability")
        return self


def content_hash(text: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class NewsReader(Protocol):
    def as_of(self, at: datetime) -> Sequence[NewsRecord]: ...


class NewsStore(NewsReader, Protocol):
    def append(self, record: NewsRecord) -> NewsRecord: ...


class NewsIngestor:
    """Run in a separate operator job; never attach to the market/feed consumer.

    Bytes are delivered by an authorized adapter, not fetched from text/URLs.
    No generic model callback is invoked. Optional model output must come from an
    isolated, budgeted extractor and passes the strict data-only schema here.
    """

    def __init__(
        self,
        store: NewsStore,
        grants: Sequence[SourceGrant],
        symbols: frozenset[str],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.store = store
        self.grants = {g.source: g for g in grants}
        if len(self.grants) != len(grants) or any(
            not re.fullmatch(r"[A-Z]{4}", s) for s in symbols
        ):
            raise ValueError("Invalid source registry or issuer universe")
        self.symbols = symbols
        self.clock = clock

    def ingest(
        self, source: str, document: NewsInput, extraction: Extraction | None = None
    ) -> NewsRecord:
        received = self.clock()
        # Revalidate even objects assembled with model_construct by internal callers.
        document = NewsInput.model_validate(document.model_dump())
        grant = self.grants.get(source)
        if grant is None:
            raise ValueError("Unknown source")
        grant.authorize(received)
        mentions = tuple(
            sorted(self.symbols.intersection(re.findall(r"\b[A-Z]{4}\b", document.text)))
        )
        if extraction is None:
            extraction = Extraction(
                symbols=mentions,
                event="other",
                summary="",  # No raw text copied to a public surface or log.
                method="deterministic",
                version="explicit-ticker-v1",
            )
        else:
            extraction = Extraction.model_validate(extraction.model_dump())
            # A model cannot invent an issuer or confer official credibility.
            if not set(extraction.symbols).issubset(mentions):
                raise ValueError("Unsupported issuer mapping")
        available = max(received, document.published_at, self.clock())
        grant.authorize(available, llm=extraction.method == "llm")
        return self.store.append(
            NewsRecord(
                source=source,
                grant=grant,
                document=document,
                content_hash=content_hash(document.text),
                received_at=received,
                available_at=available,
                extraction=extraction,
            )
        )


def point_in_time(records: Sequence[NewsRecord], at: datetime) -> tuple[NewsRecord, ...]:
    """Latest *available* revision, then exact normalized cross-source dedup.

    Near duplicates are deliberately not merged without an evaluated policy.
    Later corrections and later verified syndication cannot rewrite past features.
    """
    aware(at)
    latest: dict[tuple[str, str], NewsRecord] = {}
    for record in records:
        if record.available_at > at:
            continue
        key = record.source, record.document.document_id
        if key not in latest or record.document.revision > latest[key].document.revision:
            latest[key] = record
    unique: dict[str, NewsRecord] = {}
    priority = {"official": 0, "verified": 1, "unverified": 2}
    for record in sorted(
        latest.values(),
        key=lambda r: (priority[r.grant.credibility], r.available_at, r.source),
    ):
        unique.setdefault(record.content_hash, record)
    return tuple(sorted(unique.values(), key=lambda r: (r.available_at, r.source)))


def event_count(
    store: NewsReader, symbol: str, at: datetime, *, window: timedelta = timedelta(days=1)
) -> int:
    """Internal feature only; unverified, unknown issuers and future news abstain."""
    if window <= timedelta(0):
        raise ValueError("Positive news window required")
    records = store.as_of(at)
    first: dict[str, datetime] = {}
    for record in records:
        if record.available_at <= at:
            first[record.content_hash] = min(
                first.get(record.content_hash, record.available_at), record.available_at
            )
    return sum(
        symbol in r.extraction.symbols
        and r.grant.credibility != "unverified"
        and at - window < first[r.content_hash] <= at
        for r in point_in_time(records, at)
    )
