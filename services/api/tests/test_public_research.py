"""Deployed daily data works without sessions; administrative resources remain private."""

from pathlib import Path

from fastapi.testclient import TestClient

from saham_signal.config import Settings
from saham_signal.transport.http import create_app


def test_bundled_public_market_data_and_linked_detail_without_configuration() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/api/research/eod")
        assert response.status_code == 200
        snapshot = response.json()
        assert len(snapshot["rows"]) >= 100
        bbca = next(row for row in snapshot["rows"] if row["symbol"] == "BBCA")
        assert "history" not in bbca and "backtest" not in bbca
        detail = client.get("/api/research/stocks/BBCA")
        assert detail.status_code == 200
        assert detail.json()["close_idr"] == bbca["close_idr"]
        assert len(detail.json()["history"]) > 20
        assert detail.json()["order_book"] is None
        assert client.get("/api/research/screener").status_code == 200
        assert client.get("/api/ops/status").status_code == 401
        assert client.get("/api/ops/paper").status_code == 401
        assert client.get("/api/v1/watchlist").status_code == 503


def test_deployment_with_missing_local_snapshot_uses_bundled_data() -> None:
    config = Settings(eod_snapshot_path=Path("/nonexistent-operator-local/snapshot.json"))
    with TestClient(create_app(config)) as client:
        assert client.get("/api/research/eod").status_code == 200
