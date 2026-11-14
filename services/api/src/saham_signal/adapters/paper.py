"""Durable offline paper receipts, isolated from manual fills and live alerts."""

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from saham_signal.adapters.persistence import Journal
from saham_signal.domain.persistence import digest


class PostgresPaper:
    def __init__(self, dsn: str, account: str) -> None:
        if not account or len(account) > 128:
            raise ValueError("Account required")
        self.dsn, self.account = dsn, account

    def append(self, report: dict[str, Any]) -> str:
        body = {k: v for k, v in report.items() if k != "sha256"}
        fingerprint = digest(body)
        if (
            report.get("sha256") != fingerprint
            or report.get("format") != "SS-026-qualification-v1"
            or report.get("mode") != "paper"
            or report.get("account") != self.account
            or report.get("origin") != "simulation"
            or report.get("actual_fills") != []
            or report.get("readiness", {}).get("paper_live_enabled") is not False
            or report.get("live_alerts_enabled") is not False
        ):
            raise ValueError("Invalid offline paper receipt")
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=3) as conn:
            Journal(self.dsn, "paper", self.account)._scope(conn)
            conn.execute(
                "INSERT INTO paper_qualification(mode,user_id,content_digest,snapshot) "
                "VALUES ('paper',%s,%s,%s) ON CONFLICT DO NOTHING",
                (self.account, fingerprint, Jsonb(report)),
            )
        return fingerprint

    def latest(self) -> dict[str, Any] | None:
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=3) as conn:
            Journal(self.dsn, "paper", self.account)._scope(conn)
            row = conn.execute(
                "SELECT snapshot FROM paper_qualification WHERE mode='paper' AND user_id=%s "
                "ORDER BY recorded_at DESC,content_digest DESC LIMIT 1",
                (self.account,),
            ).fetchone()
            return dict(row["snapshot"]) if row else None
