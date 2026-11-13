"""Explicit migration entrypoint; never run migrations during API/worker startup."""

import hashlib
from importlib.resources import files

import psycopg

from saham_signal.config import load_settings


def migrate(dsn: str) -> None:
    with psycopg.connect(dsn) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(10010)")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name text PRIMARY KEY, checksum text NOT NULL, "
            "applied_at timestamptz NOT NULL DEFAULT now())"
        )
        for resource in sorted(files("saham_signal.migrations").iterdir(), key=lambda r: r.name):
            if not resource.name.endswith(".sql"):
                continue
            sql = resource.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            previous = connection.execute(
                "SELECT checksum FROM schema_migrations WHERE name = %s", (resource.name,)
            ).fetchone()
            if previous:
                if previous[0] != checksum:
                    raise RuntimeError("Applied migration checksum changed")
                continue
            connection.execute(sql)
            connection.execute(
                "INSERT INTO schema_migrations (name, checksum) VALUES (%s, %s)",
                (resource.name, checksum),
            )


if __name__ == "__main__":
    try:
        migrate(load_settings().database_url.get_secret_value())
    except Exception:
        raise SystemExit("Migration failed; check database access and migration history") from None
