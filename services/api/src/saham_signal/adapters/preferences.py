"""Durable scoped configuration with serialized, idempotent append-only writes."""

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from saham_signal.adapters.persistence import Journal
from saham_signal.application.market import MarketScope
from saham_signal.application.preferences import PreferenceConflict, validate_preference


class PostgresPreferences:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def get(self, scope: MarketScope, kind: str) -> dict[str, Any] | None:
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            Journal(self.dsn, scope.mode, scope.account)._scope(connection)
            row = connection.execute(
                "SELECT payload FROM personal_preferences WHERE mode=%s AND user_id=%s "
                "AND kind=%s ORDER BY cursor DESC LIMIT 1",
                (scope.mode, scope.account, kind),
            ).fetchone()
            return row["payload"] if row else None

    def put(
        self, scope: MarketScope, kind: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        validate_preference(kind, payload)
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            Journal(self.dsn, scope.mode, scope.account)._scope(connection)
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"preferences:{scope.mode}:{scope.account}",),
            )
            rows = list(
                connection.execute(
                    "SELECT payload, idempotency_key FROM personal_preferences "
                    "WHERE mode=%s AND user_id=%s AND kind=%s ORDER BY cursor DESC",
                    (scope.mode, scope.account, kind),
                )
            )
            for row in rows:
                if row["idempotency_key"] == key:
                    if row["payload"] != payload:
                        raise PreferenceConflict("Idempotency key reused")
                    return dict(row["payload"])
            if kind == "RiskSettings" and any(
                row["payload"]["configuration_version"] == payload["configuration_version"]
                or (
                    row["payload"]["fee_schedule_version"] == payload["fee_schedule_version"]
                    and row["payload"]["fee_schedule"] != payload["fee_schedule"]
                )
                for row in rows
            ):
                raise PreferenceConflict("Configuration and fee versions are immutable")
            connection.execute(
                "INSERT INTO personal_preferences (mode,user_id,kind,idempotency_key,payload) "
                "VALUES (%s,%s,%s,%s,%s)",
                (scope.mode, scope.account, kind, key, Jsonb(payload)),
            )
            return payload
