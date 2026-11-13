"""Transactional append-only PostgreSQL repository. No HTTP routes are exposed."""

import json
from collections.abc import Sequence
from datetime import datetime
from importlib.resources import files
from typing import Any

import psycopg
from jsonschema import Draft202012Validator, FormatChecker
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from saham_signal.domain.mode import Mode
from saham_signal.domain.persistence import Kind, Record, digest

SCHEMA = json.loads(files("saham_signal").joinpath("storage_contract.json").read_text("utf-8"))


class PersistenceConflict(ValueError):
    """A key was reused with different content, or a version is not consecutive."""


class Journal:
    def __init__(self, dsn: str, mode: Mode, user_id: str) -> None:
        self.dsn = dsn
        self.mode = mode
        self.user_id = user_id

    def _scope(self, connection: psycopg.Connection[dict[str, Any]]) -> None:
        connection.execute("SELECT set_config('ss.mode', %s, true)", (self.mode,))
        connection.execute("SELECT set_config('ss.user_id', %s, true)", (self.user_id,))
        row = connection.execute("SELECT current_database() AS name").fetchone()
        if row is None or row["name"] != f"saham_signal_{self.mode}":
            raise ValueError("Database does not match repository mode")

    def append(self, records: Sequence[Record]) -> list[int]:
        """Commit a whole effect (e.g. fill + position version) or none of it.

        Writers for one account/mode serialize, giving committed replay cursors.
        Repeating an identical key returns the original cursor without effects.
        """
        documents = []
        for record in records:
            Draft202012Validator(
                {"$ref": f"#/$defs/{record.kind}", "$defs": SCHEMA["$defs"]},
                format_checker=FormatChecker(),
            ).validate(record.payload)
            documents.append(record.document(self.mode, self.user_id))
        cursors: list[int] = []
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            self._scope(connection)
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"journal:{self.mode}:{self.user_id}",),
            )
            for document in documents:
                fingerprint = digest(document)
                previous = connection.execute(
                    "SELECT cursor, content_digest FROM journal "
                    "WHERE mode = %s AND user_id = %s AND idempotency_key = %s",
                    (self.mode, self.user_id, document["idempotency_key"]),
                ).fetchone()
                if previous is not None:
                    if previous["content_digest"] != fingerprint:
                        raise PersistenceConflict("Idempotency key reused with different content")
                    cursors.append(previous["cursor"])
                    continue
                latest = connection.execute(
                    "SELECT coalesce(max(version), 0) AS version FROM journal "
                    "WHERE mode = %s AND user_id = %s AND kind = %s AND entity_id = %s",
                    (self.mode, self.user_id, document["kind"], document["entity_id"]),
                ).fetchone()
                assert latest is not None
                if document["version"] != latest["version"] + 1:
                    raise PersistenceConflict("Append must use the next entity version")
                document.update(mode=self.mode, user_id=self.user_id, content_digest=fingerprint)
                document["payload"] = Jsonb(document["payload"])
                row = connection.execute(
                    "INSERT INTO journal (mode, user_id, kind, entity_id, version, "
                    "idempotency_key, "
                    "event_time, provider_time, received_at, available_at, processed_at, sequence, "
                    "source, data_origin, actor, reason, payload, contract_version, "
                    "content_digest) "
                    "VALUES (%(mode)s, %(user_id)s, %(kind)s, %(entity_id)s, %(version)s, "
                    "%(idempotency_key)s, %(event_time)s, %(provider_time)s, %(received_at)s, "
                    "%(available_at)s, %(processed_at)s, %(sequence)s, %(source)s, "
                    "%(data_origin)s, %(actor)s, %(reason)s, %(payload)s, %(contract_version)s, "
                    "%(content_digest)s) RETURNING cursor",
                    document,
                ).fetchone()
                assert row is not None
                cursors.append(row["cursor"])
        return cursors

    def replay(self, as_of: datetime) -> list[dict[str, Any]]:
        """Fixed-cutoff replay in availability/sequence order, including late arrivals."""
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must carry a timezone")
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            self._scope(connection)
            return list(
                connection.execute(
                    "SELECT * FROM journal WHERE mode = %s AND user_id = %s "
                    "AND available_at <= %s ORDER BY available_at, sequence, cursor",
                    (self.mode, self.user_id, as_of),
                )
            )

    def snapshot(self, kind: Kind, entity_id: str, as_of: datetime) -> dict[str, Any] | None:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must carry a timezone")
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            self._scope(connection)
            row = connection.execute(
                "SELECT payload FROM journal WHERE mode = %s AND user_id = %s "
                "AND kind = %s AND entity_id = %s AND available_at <= %s "
                "ORDER BY version DESC LIMIT 1",
                (self.mode, self.user_id, kind, entity_id, as_of),
            ).fetchone()
            return row["payload"] if row else None
