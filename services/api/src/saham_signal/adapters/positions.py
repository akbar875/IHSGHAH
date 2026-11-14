"""Append-only manual ledger, serialized per account/mode across all API processes."""

from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from saham_signal.adapters.alerts import persist_alerts
from saham_signal.adapters.persistence import Journal
from saham_signal.application.alerts import source_events
from saham_signal.application.market import MarketScope
from saham_signal.application.positions import PositionConflict, monitor, transition


class PostgresPositions:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def list(self, scope: MarketScope) -> list[dict[str, Any]]:
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=2) as connection:
            Journal(self.dsn, scope.mode, scope.account)._scope(connection)
            rows = connection.execute(
                "SELECT DISTINCT ON (position_id) snapshot FROM manual_position_events "
                "WHERE mode=%s AND user_id=%s ORDER BY position_id,cursor DESC",
                (scope.mode, scope.account),
            )
            return [row["snapshot"] for row in rows]

    def execute(
        self, scope: MarketScope, key: str, command: dict[str, Any], at: datetime
    ) -> dict[str, Any]:
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=2) as connection:
            Journal(self.dsn, scope.mode, scope.account)._scope(connection)
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"manual-positions:{scope.mode}:{scope.account}",),
            )
            duplicate = connection.execute(
                "SELECT command,snapshot FROM manual_position_events "
                "WHERE mode=%s AND user_id=%s AND idempotency_key=%s",
                (scope.mode, scope.account, key),
            ).fetchone()
            if duplicate:
                if duplicate["command"] != command:
                    raise PositionConflict("Idempotency key reused")
                return dict(duplicate["snapshot"])
            row = connection.execute(
                "SELECT snapshot FROM manual_position_events "
                "WHERE mode=%s AND user_id=%s AND position_id=%s ORDER BY cursor DESC LIMIT 1",
                (scope.mode, scope.account, command["position_id"]),
            ).fetchone()
            snapshot = transition(scope, row["snapshot"] if row else None, command, at, key)
            connection.execute(
                "INSERT INTO manual_position_events "
                "(mode,user_id,position_id,idempotency_key,command,snapshot) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    scope.mode,
                    scope.account,
                    snapshot["position"]["position_id"],
                    key,
                    Jsonb(command),
                    Jsonb(snapshot),
                ),
            )
            # Commit the manual change and its alert together, even with no browser open.
            persist_alerts(
                connection,
                scope,
                source_events([], {"status": "healthy"}, [monitor(snapshot, at)], at),
                at,
            )
            return snapshot
