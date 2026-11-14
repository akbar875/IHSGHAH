"""Dedicated research PostgreSQL news store; no market connection or HTTP route."""

import json
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from saham_signal.adapters.persistence import PersistenceConflict
from saham_signal.application.news import NewsRecord
from saham_signal.domain.instruments import aware


class NewsRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _scope(self, connection: psycopg.Connection[dict[str, Any]]) -> None:
        row = connection.execute("SELECT current_database() AS name").fetchone()
        if row is None or row["name"] != "saham_signal_research":
            raise ValueError("News storage requires research database")
        connection.execute("SELECT set_config('ss.news_internal', 'on', true)")

    def append(self, record: NewsRecord) -> NewsRecord:
        record = NewsRecord.model_validate(record.model_dump())
        doc = record.document
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            self._scope(connection)
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"news:{record.source}:{doc.document_id}",),
            )
            rows = list(
                connection.execute(
                    "SELECT payload FROM internal_news WHERE source = %s AND document_id = %s "
                    "ORDER BY revision DESC",
                    (record.source, doc.document_id),
                )
            )
            for row in rows:
                previous = NewsRecord.model_validate_json(json.dumps(row["payload"]))
                if previous.document.revision == doc.revision:
                    if (
                        previous.document != doc
                        or previous.extraction != record.extraction
                        or previous.grant != record.grant
                    ):
                        raise PersistenceConflict("News revision reused with changed content")
                    return previous
            if rows:
                previous = NewsRecord.model_validate_json(json.dumps(rows[0]["payload"]))
                if (
                    doc.revision != previous.document.revision + 1
                    or record.available_at < previous.available_at
                ):
                    raise PersistenceConflict("News requires consecutive monotonic revisions")
            elif doc.revision != 1:
                raise PersistenceConflict("News must start at revision one")
            connection.execute(
                "INSERT INTO internal_news "
                "(source, document_id, revision, available_at, payload) VALUES (%s,%s,%s,%s,%s)",
                (
                    record.source,
                    doc.document_id,
                    doc.revision,
                    record.available_at,
                    Jsonb(record.model_dump(mode="json")),
                ),
            )
        return record

    def as_of(self, at: datetime) -> tuple[NewsRecord, ...]:
        aware(at)
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            self._scope(connection)
            rows = connection.execute(
                "SELECT payload FROM internal_news WHERE available_at <= %s "
                "ORDER BY available_at, source, document_id, revision",
                (at,),
            )
            records = [NewsRecord.model_validate_json(json.dumps(row["payload"])) for row in rows]
        return tuple(records)
