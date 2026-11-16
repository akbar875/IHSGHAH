"""Validated, attributed daily research data. No Signal, fill or live-feed projection."""

import csv
import hashlib
import re
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saham_signal.domain.instruments import JAKARTA, aware
from saham_signal.domain.persistence import digest

SOURCE: Final = "https://dataset.aethereal.top/datasets/idx-stock-features"
DOWNLOAD = "https://dataset.aethereal.top/files/idx-stock-features.csv"
LICENSE: Final = "https://creativecommons.org/licenses/by/4.0/"
FIELDS = [
    "date",
    "ticker",
    "close",
    "volume",
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "vol_20d",
    "sma_20",
    "sma_50",
    "sma_200",
    "rsi_14",
    "drawdown",
    "beta_60d",
    "corr_60d",
    "rel_strength_20d",
    "value_idr",
    "avg_value_20d_idr",
    "close_usd",
]
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class DailyRow(Frozen):
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9]{1,7}$")
    date: date
    close_idr: str
    volume: str = Field(pattern=r"^(?:0|[1-9][0-9]{0,18})$")
    return_1d: str | None
    rsi_14: str | None
    technical: dict[str, str | None] | None = None

    @model_validator(mode="after")
    def check(self) -> Self:
        if not 0 < number(self.close_idr) < Decimal("1e16"):
            raise ValueError("Invalid close")
        volume = number(self.volume)
        if not 0 <= volume <= 10**18 or volume != volume.to_integral_value():
            raise ValueError("Invalid volume")
        if self.return_1d is not None and not -1 <= number(self.return_1d) <= Decimal("1e12"):
            raise ValueError("Invalid adjusted return")
        if self.rsi_14 is not None and not 0 <= number(self.rsi_14) <= 100:
            raise ValueError("Invalid RSI")
        if self.date.weekday() >= 5:
            raise ValueError("Unexpected weekend daily row")
        return self


class Snapshot(Frozen):
    format: Literal["SS-FREE-EOD-v1"] = "SS-FREE-EOD-v1"
    mode: Literal["research"] = "research"
    origin: Literal["market"] = "market"
    frequency: Literal["daily"] = "daily"
    provider: Literal["Aethereal"] = "Aethereal"
    source: Literal["https://dataset.aethereal.top/datasets/idx-stock-features"] = SOURCE
    license: Literal["CC BY 4.0"] = "CC BY 4.0"
    license_url: Literal["https://creativecommons.org/licenses/by/4.0/"] = LICENSE
    attribution: str = "Aethereal (2026), IDX Stock Features; filtered daily research snapshot."
    available_at: datetime
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    latest_date: date
    rows: tuple[DailyRow, ...]
    quality: dict[str, int]
    signals_enabled: Literal[False] = False
    sha256: str = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        aware(self.available_at)
        symbols = [r.symbol for r in self.rows]
        if not symbols or len(symbols) > 2000 or symbols != sorted(set(symbols)):
            raise ValueError("Unique sorted universe required")
        if self.latest_date != max(r.date for r in self.rows) or any(
            r.date > self.available_at.astimezone(JAKARTA).date() for r in self.rows
        ):
            raise ValueError("Invalid daily availability")
        if any(type(v) is not int or v < 0 for v in self.quality.values()):
            raise ValueError("Invalid quality count")
        if self.quality.get("rows") != self.quality.get("accepted_rows", 0) + self.quality.get(
            "rejected_rows", 0
        ) or self.quality.get("published_symbols") != len(self.rows):
            raise ValueError("Inconsistent quality denominator")
        body = self.model_dump(mode="json", exclude={"sha256"})
        for row, serialized in zip(self.rows, body["rows"], strict=True):
            if "technical" not in row.model_fields_set:
                serialized.pop("technical", None)
        if self.sha256 and self.sha256 != digest(body):
            raise ValueError("Snapshot checksum mismatch")
        return self

    def sealed(self) -> "Snapshot":
        body = self.model_dump(mode="json", exclude={"sha256"})
        return Snapshot.model_validate({**body, "sha256": digest(body)})


def number(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError("Invalid numeric value") from None
    if not result.is_finite() or abs(result) > Decimal("1e30"):
        raise ValueError("Nonfinite or excessive numeric value")
    return result


def import_csv(path: Path, available_at: datetime) -> Snapshot:
    with localcontext() as context:
        context.prec = 60
        return _import_csv(path, available_at)


def _import_csv(path: Path, available_at: datetime) -> Snapshot:
    aware(available_at)
    if not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("Source outside size limit")
    fingerprint = hashlib.sha256()
    with path.open("rb") as raw:
        for block in iter(lambda: raw.read(65536), b""):
            fingerprint.update(block)
    counts: Counter[str] = Counter(
        {"rows": 0, "accepted_rows": 0, "rejected_rows": 0, "zero_volume_rows": 0}
    )
    latest: dict[str, DailyRow] = {}
    previous: dict[str, date] = {}
    rejected_latest: dict[str, date] = {}
    unknown_date: set[str] = set()
    seen: set[tuple[str, date]] = set()
    accepted: set[tuple[str, date]] = set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != FIELDS:
            raise ValueError("Unexpected provider schema")
        for raw_row in reader:
            counts["rows"] += 1
            symbol = raw_row.get("ticker", "")
            day: date | None = None
            stage = "identity"
            try:
                if None in raw_row or set(raw_row) != set(FIELDS):
                    raise ValueError("Malformed fields")
                day = date.fromisoformat(raw_row["date"])
                if day.isoformat() != raw_row["date"] or not re.fullmatch(
                    r"[A-Z][A-Z0-9]{1,7}", symbol
                ):
                    raise ValueError("Invalid identity")
                key = symbol, day
                if key in seen:
                    if key in accepted:
                        accepted.remove(key)
                        counts["accepted_rows"] -= 1
                        counts["rejected_rows"] += 1
                        counts["duplicate_previous"] += 1
                    counts["duplicate_rows"] += 1
                    raise ValueError("Duplicate identity")
                seen.add(key)
                if symbol in previous and day < previous[symbol]:
                    counts["out_of_order_rows"] += 1
                    raise ValueError("Out-of-order daily row")
                previous[symbol] = day
                stage = "numeric"
                values = {
                    k: number(v) if v else None
                    for k, v in raw_row.items()
                    if k not in {"date", "ticker"}
                }
                if values["close"] is None or values["volume"] is None:
                    raise ValueError("Missing close/volume")
                for field in ("sma_20", "sma_50", "sma_200", "close_usd"):
                    value = values[field]
                    if value is not None and (value < 0 or (value == 0 and field != "close_usd")):
                        raise ValueError("Nonpositive price/average")
                for field in ("vol_20d", "value_idr", "avg_value_20d_idr"):
                    value = values[field]
                    if value is not None and value < 0:
                        raise ValueError("Negative magnitude")
                if values["corr_60d"] is not None and not -1 <= values["corr_60d"] <= 1:
                    raise ValueError("Invalid correlation")
                if values["drawdown"] is not None and not -1 <= values["drawdown"] <= 0:
                    raise ValueError("Invalid drawdown")
                close, volume = values["close"], values["volume"]
                if volume != volume.to_integral_value():
                    raise ValueError("Fractional volume")
                gross = close * volume
                if values["value_idr"] is not None and abs(values["value_idr"] - gross) > max(
                    Decimal(1), gross * Decimal("0.000001")
                ):
                    raise ValueError("Inconsistent traded value")
                row = DailyRow(
                    symbol=symbol,
                    date=day,
                    close_idr=format(close, "f"),
                    volume=format(volume.to_integral_value(), "f"),
                    return_1d=str(values["ret_1d"]) if values["ret_1d"] is not None else None,
                    rsi_14=str(values["rsi_14"]) if values["rsi_14"] is not None else None,
                    technical={
                        k: str(values[k]) if values[k] is not None else None
                        for k in ("sma_20", "sma_50", "sma_200", "ret_20d", "avg_value_20d_idr")
                    },
                )
                if day > available_at.astimezone(JAKARTA).date():
                    raise ValueError("Future daily data")
                accepted.add(key)
                latest[symbol] = row
                counts["accepted_rows"] += 1
                if volume == 0:
                    counts["zero_volume_rows"] += 1
            except (ValueError, TypeError):
                counts["rejected_rows"] += 1
                counts[f"{stage}_rejected"] += 1
                if (
                    isinstance(symbol, str)
                    and re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", symbol)
                    and day is None
                ):
                    unknown_date.add(symbol)
                if day is not None and isinstance(symbol, str) and symbol:
                    rejected_latest[symbol] = max(day, rejected_latest.get(symbol, day))
    published = tuple(
        row
        for symbol, row in sorted(latest.items())
        if symbol not in unknown_date
        and (symbol not in rejected_latest or row.date > rejected_latest[symbol])
    )
    if not published:
        raise ValueError("No eligible symbols after quarantine")
    counts["published_symbols"] = len(published)
    counts["excluded_symbols"] = len(set(latest) | set(rejected_latest)) - len(published)
    return Snapshot(
        available_at=available_at,
        source_sha256=fingerprint.hexdigest(),
        latest_date=max(r.date for r in published),
        rows=published,
        quality=dict(counts),
    ).sealed()


def read_snapshot(path: Path, at: datetime) -> dict[str, Any]:
    aware(at)
    if not 0 < path.stat().st_size <= MAX_SNAPSHOT_BYTES:
        raise ValueError("Snapshot outside size limit")
    snapshot = Snapshot.model_validate_json(path.read_bytes())
    if not snapshot.sha256 or snapshot.available_at > at:
        raise ValueError("Unsealed or future snapshot")
    result = snapshot.model_dump(mode="json")
    result["stale"] = (at.astimezone(JAKARTA).date() - snapshot.latest_date).days > 7 or (
        at - snapshot.available_at > timedelta(days=7)
    )
    result["as_of"] = at.isoformat()
    for row in result["rows"]:
        row["stale"] = (
            result["stale"]
            or (at.astimezone(JAKARTA).date() - date.fromisoformat(row["date"])).days > 7
        )
    return result
