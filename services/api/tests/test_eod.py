"""Synthetic malformed-source/auth tests; actual source audit is a separate receipt."""

import csv
import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from saham_signal.adapters import eod as eod_adapter
from saham_signal.adapters.eod import NoRedirect, download_and_import, publish
from saham_signal.application.eod import FIELDS, Snapshot, import_csv, read_snapshot
from saham_signal.application.security import session_cookie
from saham_signal.config import Settings
from saham_signal.transport.http import create_app

NOW = datetime(2026, 11, 16, 3, tzinfo=UTC)


def row(**changes: Any) -> dict[str, Any]:
    return {
        **dict.fromkeys(FIELDS, ""),
        "date": "2026-11-13",
        "ticker": "SIM",
        "close": "1000",
        "volume": "100",
        "ret_1d": "0.01",
        "rsi_14": "50",
        "value_idr": "100000",
        **changes,
    }


def source(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    file = tmp_path / "source.csv"
    with file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return file


def test_import_real_origin_daily_availability_nullable_indicators_and_integrity(
    tmp_path: Path,
) -> None:
    snapshot = import_csv(
        source(tmp_path, [row(), row(ticker="ALT", rsi_14="", volume="0", value_idr="0")]), NOW
    )
    assert snapshot.mode == "research" and snapshot.origin == "market"
    assert snapshot.frequency == "daily" and not snapshot.signals_enabled
    assert snapshot.rows[0].rsi_14 is None and snapshot.rows[0].volume == "0"
    output = tmp_path / "snapshot.json"
    publish(snapshot, output)
    data = read_snapshot(output, NOW)
    assert data["license"] == "CC BY 4.0" and not data["stale"]
    assert all(not r["stale"] for r in data["rows"])
    assert read_snapshot(output, NOW + timedelta(days=8))["stale"]
    with pytest.raises(ValueError, match="future"):
        read_snapshot(output, NOW - timedelta(seconds=1))
    corrupted = json.loads(output.read_text())
    corrupted["rows"][0]["close_idr"] = "9999"
    output.write_text(json.dumps(corrupted))
    with pytest.raises(ValueError, match="checksum"):
        read_snapshot(output, NOW)


@pytest.mark.parametrize(
    "change",
    [
        {"close": "NaN"},
        {"volume": "1.5", "value_idr": "1500"},
        {"rsi_14": "101"},
        {"corr_60d": "-2"},
        {"date": "2026-11-17"},
        {"date": "2026-11-14"},
        {"value_idr": "123"},
        {"close": "0"},
        {"vol_20d": "-1"},
        {"ticker": "=cmd"},
    ],
)
def test_bad_latest_is_quarantined_without_substituting_a_prior_row(
    tmp_path: Path, change: dict[str, str]
) -> None:
    rows = [row(ticker="SAFE"), row(date="2026-11-12"), row(**change)]
    snapshot = import_csv(source(tmp_path, rows), NOW)
    assert [r.symbol for r in snapshot.rows] == (
        ["SAFE", "SIM"] if "ticker" in change else ["SAFE"]
    )
    assert snapshot.quality["rejected_rows"] == 1


def test_duplicate_both_rows_excluded_and_failed_import_preserves_previous(tmp_path: Path) -> None:
    output = tmp_path / "snapshot.json"
    first = import_csv(source(tmp_path, [row(ticker="SAFE")]), NOW)
    publish(first, output)
    duplicate = import_csv(source(tmp_path, [row(), row(), row(ticker="SAFE")]), NOW)
    assert [r.symbol for r in duplicate.rows] == ["SAFE"]
    assert duplicate.quality["accepted_rows"] == 1
    assert duplicate.quality["rejected_rows"] == 2
    invalid = source(tmp_path, [row(close="-1")])
    with pytest.raises(ValueError):
        publish(import_csv(invalid, NOW), output)
    assert Snapshot.model_validate_json(output.read_bytes()) == first


def test_signed_research_api_rejects_query_and_does_not_need_fixture_or_database(
    tmp_path: Path,
) -> None:
    output = tmp_path / "snapshot.json"
    publish(import_csv(source(tmp_path, [row()]), NOW), output)
    config = Settings(
        session_secret=SecretStr("research-only-test-secret-12345678901234567890"),
        pilot_account_id="research-test",
        eod_snapshot_path=output,
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/api/research/eod").status_code == 200
        client.cookies.set("saham_session", session_cookie(config))
        response = client.get("/api/research/eod")
        assert response.status_code == 200 and response.json()["origin"] == "market"
        assert response.headers["cache-control"] == "private, no-store"
        assert client.get("/api/research/eod?path=private.csv").status_code == 422
        output.unlink()
        assert client.get("/api/research/eod").status_code == 503


def test_paper_live_cannot_enable_daily_snapshot() -> None:
    for mode in ("paper", "live"):
        with pytest.raises(ValueError):
            Settings(app_mode=mode, eod_snapshot_path=Path("snapshot.json"))


def test_downloader_refuses_redirects() -> None:
    assert NoRedirect().redirect_request(None, None, 302, "move", {}, "http://localhost") is None


def test_oversized_download_preserves_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "snapshot.json"
    publish(import_csv(source(tmp_path, [row()]), NOW), output)
    previous = output.read_bytes()

    class Response(BytesIO):
        headers = {"Content-Length": str(65 * 1024 * 1024)}

    class Opener:
        def open(self, *args: Any, **kwargs: Any) -> Response:
            return Response(b"too large")

    monkeypatch.setattr(eod_adapter, "build_opener", lambda *args: Opener())
    with pytest.raises(ValueError, match="size limit"):
        download_and_import(output, NOW)
    assert output.read_bytes() == previous
