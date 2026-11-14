"""Pilot-sized logical backup, consistent across all application tables.

Requires a trusted operator/BYPASSRLS connection. Files contain private data:
store encrypted outside Git. No DSN, credentials, arbitrary SQL or DDL in files.
Restore supports the exact bundled migration version into an empty migrated
schema only. It never overwrites a running ledger and always pauses entries.
"""

import json
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from saham_signal.adapters.operations import PostgresControl
from saham_signal.domain.mode import Mode
from saham_signal.domain.persistence import digest

TABLES = (
    "journal",
    "retention_policy",
    "personal_preferences",
    "manual_position_events",
    "in_app_alerts",
    "alert_gates",
    "internal_news",
    "operation_events",
    "paper_qualification",
)


def operator(conn: psycopg.Connection[dict[str, Any]], mode: Mode) -> None:
    row = conn.execute(
        "SELECT current_database() AS db, (rolsuper OR rolbypassrls) AS privileged "
        "FROM pg_roles WHERE rolname=current_user"
    ).fetchone()
    if not row or not row["privileged"] or row["db"] != f"saham_signal_{mode}":
        raise ValueError("Backup/restore requires a mode-matched BYPASSRLS operator")


def migrations(conn: psycopg.Connection[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(conn.execute("SELECT name,checksum FROM schema_migrations ORDER BY name"))


def backup(dsn: str, mode: Mode) -> dict[str, Any]:
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=3) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout='60s'")
        operator(conn, mode)
        tables = {}
        for name in TABLES:
            rows = conn.execute(
                sql.SQL("SELECT row_to_json(t) AS row FROM {} t").format(sql.Identifier(name))
            )
            # Stable order makes a restored snapshot independently comparable.
            tables[name] = sorted(
                [r["row"] for r in rows], key=lambda r: json.dumps(r, sort_keys=True)
            )
        document = {
            "format": "SS-025-logical-v1",
            "mode": mode,
            "created_at": datetime.now(UTC).isoformat(),
            "migrations": migrations(conn),
            "tables": tables,
        }
        return {**document, "sha256": digest(document)}


def restore(dsn: str, mode: Mode, document: dict[str, Any], confirmation: str) -> dict[str, int]:
    if confirmation != f"empty:saham_signal_{mode}":
        raise ValueError("Explicit empty target confirmation required")
    body = {k: v for k, v in document.items() if k != "sha256"}
    if (
        document.get("sha256") != digest(body)
        or body.get("format") != "SS-025-logical-v1"
        or body.get("mode") != mode
        or set(body.get("tables", {})) != set(TABLES)
    ):
        raise ValueError("Backup integrity, format or mode mismatch")
    counts = {}
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=3) as conn:
        conn.execute("SET LOCAL lock_timeout='5s'")
        conn.execute("SET LOCAL statement_timeout='60s'")
        operator(conn, mode)
        # No changes to source, no DROP/TRUNCATE, and concurrent writers cannot race emptiness.
        conn.execute(
            sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                sql.SQL(",").join(map(sql.Identifier, sorted(TABLES)))
            )
        )
        if migrations(conn) != body["migrations"]:
            raise ValueError("Restore requires identical migrated schema")
        for name in TABLES:
            if conn.execute(
                sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(name))
            ).fetchone():
                raise ValueError("Restore target is not empty")
        conn.execute("SELECT set_config('ss.mode',%s,true)", (mode,))
        conn.execute("SELECT set_config('ss.news_internal','on',true)")
        for name in TABLES:
            for row in body["tables"][name]:
                if "mode" in row and row["mode"] != mode:
                    raise ValueError("Mixed-mode backup")
                conn.execute("SELECT set_config('ss.user_id',%s,true)", (row.get("user_id", ""),))
                conn.execute(
                    sql.SQL(
                        "INSERT INTO {} OVERRIDING SYSTEM VALUE "
                        "SELECT * FROM jsonb_populate_record(NULL::{},%s)"
                    ).format(sql.Identifier(name), sql.Identifier(name)),
                    (Jsonb(row),),
                )
            counts[name] = len(body["tables"][name])
            # Identity cursors must continue beyond the restored high-water mark.
            if name in {
                "journal",
                "personal_preferences",
                "manual_position_events",
                "in_app_alerts",
                "internal_news",
            }:
                conn.execute(
                    sql.SQL(
                        "SELECT setval(pg_get_serial_sequence(%s,'cursor'), "
                        "coalesce((SELECT max(cursor) FROM {}),1), "
                        "EXISTS(SELECT 1 FROM {}))"
                    ).format(sql.Identifier(name), sql.Identifier(name)),
                    (name,),
                )
        # Restore activation is never inherited from the old release.
        rows = body["tables"]["operation_events"]
        revision = max((r["revision"] for r in rows), default=0)
        conn.execute(
            "INSERT INTO operation_events(mode,revision,blocked,reason,release,evidence,actor) "
            "VALUES (%s,%s,true,'pause','restore',%s,'restore-operator')",
            (mode, revision + 1, document["sha256"]),
        )
    assert PostgresControl(dsn).read(mode).blocked
    return counts
