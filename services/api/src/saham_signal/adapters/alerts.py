"""Transactional inbox with cross-process idempotency and persistent policy gates."""

from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from saham_signal.adapters.persistence import Journal
from saham_signal.application.alerts import PRIORITY, AlertEvent, delivery
from saham_signal.application.market import MarketScope


class PostgresAlerts:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def refresh(
        self, scope: MarketScope, events: list[AlertEvent], at: datetime
    ) -> list[dict[str, Any]]:
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=2) as connection:
            Journal(self.dsn, scope.mode, scope.account)._scope(connection)
            persist_alerts(connection, scope, events, at)
            rows = connection.execute(
                "SELECT payload FROM in_app_alerts WHERE mode=%s AND user_id=%s "
                "ORDER BY priority,cursor DESC LIMIT 1000",
                (scope.mode, scope.account),
            )
            return [row["payload"] for row in rows]


def persist_alerts(
    connection: psycopg.Connection[dict[str, Any]],
    scope: MarketScope,
    events: list[AlertEvent],
    at: datetime,
) -> None:
    """Caller has set database scope; reuse the position transaction for atomic effects."""
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"alerts:{scope.mode}:{scope.account}",),
    )
    for event in events:
        duplicate = connection.execute(
            "SELECT 1 FROM in_app_alerts WHERE mode=%s AND user_id=%s "
            "AND source_key=%s AND channel='in_app'",
            (scope.mode, scope.account, event.key),
        ).fetchone()
        if duplicate and event.active:
            continue
        row = connection.execute(
            "SELECT gate FROM alert_gates WHERE mode=%s AND user_id=%s AND subject=%s",
            (scope.mode, scope.account, event.group),
        ).fetchone()
        gate = dict(row["gate"]) if row else {}
        alert = delivery(scope, event, at, gate)
        connection.execute(
            "INSERT INTO alert_gates(mode,user_id,subject,gate) VALUES (%s,%s,%s,%s) "
            "ON CONFLICT(mode,user_id,subject) DO UPDATE SET gate=EXCLUDED.gate",
            (scope.mode, scope.account, event.group, Jsonb(gate)),
        )
        if alert:
            connection.execute(
                "INSERT INTO in_app_alerts"
                "(mode,user_id,source_key,channel,priority,payload) "
                "VALUES (%s,%s,%s,'in_app',%s,%s) ON CONFLICT DO NOTHING",
                (scope.mode, scope.account, event.key, PRIORITY[event.kind], Jsonb(alert)),
            )
