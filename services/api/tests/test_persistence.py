"""Simulation-only contract and PostgreSQL acceptance tests for SS-010."""

import json
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from jsonschema import ValidationError
from psycopg import sql
from psycopg.conninfo import make_conninfo

from saham_signal.adapters.feed import (
    SIMULATION_PROFILE,
    MarketJournalSink,
    simulation_messages,
    validate_observation,
)
from saham_signal.adapters.persistence import SCHEMA, Journal, PersistenceConflict
from saham_signal.application.feed import FeedIngestor
from saham_signal.domain.persistence import Kind, Record
from saham_signal.migrate import migrate

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = json.loads((ROOT / "packages/contracts/v1/examples.json").read_text())
NOW = datetime(2026, 11, 12, 3, tzinfo=UTC)


def test_feed_journal_roundtrip(database: tuple[str, str]) -> None:
    _, runtime = database
    journal = Journal(runtime, "research", "")
    ingestor = FeedIngestor(
        SIMULATION_PROFILE,
        "research",
        lot_shares=lambda *_: 100,
        validate=validate_observation,
        commit=MarketJournalSink(journal),
        snapshot_request=lambda *_: None,
    )
    messages = list(simulation_messages(Path(__file__).parent / "fixtures/feed-simulation.json"))
    received = datetime(2026, 11, 13, 3, 2, tzinfo=UTC)
    trade = messages[2]
    for message in [
        messages[0],
        messages[1],
        trade,
        replace(trade, revision=2, payload={**trade.payload, "quantity": 300}),
        messages[4],
        trade,
    ]:
        ingestor.ingest(message, received_at=received, available_at=received, processed_at=received)
    rows = journal.replay(received)
    assert len(rows) == 5
    assert {row["data_origin"] for row in rows} == {"simulation"}
    trade_rows = [row for row in rows if row["payload"]["event_type"] == "trade"]
    assert {row["version"] for row in trade_rows} == {1, 2}
    latest = journal.snapshot("MarketEvent", trade_rows[0]["entity_id"], received)
    assert latest is not None
    assert latest["payload"]["lots"] == 3
    assert journal.replay(received - timedelta(microseconds=1)) == []


def test_packaged_contract_matches_canonical() -> None:
    assert SCHEMA == json.loads((ROOT / "packages/contracts/v1/schema.json").read_text())


def record(kind: Kind = "Signal", *, version: int = 1) -> Record:
    payload = deepcopy(next(x["payload"] for x in EXAMPLES if x["schema"] == kind))
    if kind == "Signal":
        payload["version"] = version
    key = {
        "Signal": "signal_id",
        "Fill": "fill_id",
        "Position": "position_id",
        "MarketEvent": "event_id",
        "Experiment": "experiment_id",
    }[kind]
    return Record(
        kind=kind,
        entity_id=payload[key],
        version=version,
        idempotency_key=f"{kind}-{version}",
        event_time=NOW,
        received_at=NOW,
        available_at=NOW,
        processed_at=NOW,
        sequence="1",
        source="sim-fixture",
        data_origin="simulation",
        actor="simulation-test",
        reason="SIMULATION ONLY",
        payload=payload,
    )


def test_rejects_invalid_contract_before_connecting() -> None:
    fill = record("Fill")
    fill.payload["price_idr"] = 1000.01
    with pytest.raises(ValidationError):
        Journal("invalid-dsn", "research", "pilot-sim").append([fill])


def test_envelope_guards() -> None:
    value = record()
    for invalid in (
        replace(value, available_at=NOW - timedelta(seconds=1)),
        replace(value, event_time=NOW.replace(tzinfo=None)),
        replace(value, sequence="-1"),
        replace(value, version=0),
        replace(value, entity_id="different"),
        replace(value, actor=""),
    ):
        with pytest.raises(ValueError):
            invalid.document("research", "pilot-sim")
    with pytest.raises(ValueError):
        value.document("live", "pilot-sim")
    with pytest.raises(ValueError):
        value.document("research", "")
    with pytest.raises(ValueError):
        record("Position").document("research", "someone-else")
    with pytest.raises(ValueError):
        record("MarketEvent").document("paper", "")


def test_simulated_fills_cannot_be_relabelled_and_future_fills_are_hidden() -> None:
    for kind in ("Fill", "Position"):
        value = record(kind)
        with pytest.raises(ValueError, match="provenance"):
            replace(value, data_origin="market").document("research", "pilot-sim")
    position = record("Position")
    position.payload["fills"][0]["recorded_at"] = "2026-11-12T04:00:00Z"
    with pytest.raises(ValueError, match="newer"):
        position.document("research", "pilot-sim")


@pytest.fixture
def database() -> Iterator[tuple[str, str]]:
    dsn = os.environ.get("PERSISTENCE_TEST_DSN")
    if not dsn:
        pytest.skip("Set PERSISTENCE_TEST_DSN to a disposable PostgreSQL research database")
    name = "ss010_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.execute("SELECT current_database()").fetchone() == ("saham_signal_research",)
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(name)))
    owner = make_conninfo(dsn, options=f"-c search_path={name},public")
    runtime = make_conninfo(dsn, options=f"-c search_path={name},public -c role={name}")
    try:
        migrate(owner)
        with psycopg.connect(owner) as connection:
            connection.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    sql.Identifier(name),
                    sql.Identifier(name),
                )
            )
            # Broader test grants prove triggers/RLS work even beyond normal runtime grants.
            connection.execute(
                sql.SQL("GRANT ALL ON ALL TABLES IN SCHEMA {} TO {}").format(
                    sql.Identifier(name),
                    sql.Identifier(name),
                )
            )
            connection.execute(
                sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
                    sql.Identifier(name),
                    sql.Identifier(name),
                )
            )
        yield owner, runtime
    finally:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


def scope(connection: psycopg.Connection[Any], user_id: str = "pilot-sim") -> None:
    connection.execute("SELECT set_config('ss.mode', 'research', true)")
    connection.execute("SELECT set_config('ss.user_id', %s, true)", (user_id,))


def test_empty_migration_repeat_and_checksum(database: tuple[str, str]) -> None:
    owner, _ = database
    migrate(owner)
    with psycopg.connect(owner) as connection:
        assert connection.execute("SELECT count(*) FROM schema_migrations").fetchone() == (5,)
        connection.execute("UPDATE schema_migrations SET checksum = 'tampered'")
    with pytest.raises(RuntimeError, match="checksum"):
        migrate(owner)


def test_duplicate_concurrent_delivery_has_one_effect(database: tuple[str, str]) -> None:
    _, runtime = database
    journal = Journal(runtime, "research", "pilot-sim")
    batch = [record("Fill"), record("Position")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: journal.append(batch), range(8)))
    assert all(result == results[0] for result in results)
    assert len(journal.replay(NOW)) == 2
    changed = replace(batch[0], reason="changed content")
    with pytest.raises(PersistenceConflict):
        journal.append([changed])
    with psycopg.connect(runtime) as connection:
        scope(connection)
        assert connection.execute("SELECT count(*) FROM audit_versions").fetchone() == (2,)


def test_fixed_precision_and_atomic_rollback(database: tuple[str, str]) -> None:
    _, runtime = database
    journal = Journal(runtime, "research", "pilot-sim")
    fill = record("Fill")
    fill.payload.update(price_idr="9999999999999999.99", fees_idr="0.01")
    journal.append([fill, record("Position")])
    with psycopg.connect(runtime) as connection:
        scope(connection)
        price, fee = connection.execute("SELECT price_idr, fees_idr FROM fills").fetchone() or ()
        assert price == Decimal("9999999999999999.99")
        assert fee == Decimal("0.01")
    with pytest.raises(PersistenceConflict):
        journal.append([record(), record("Position", version=3)])
    assert journal.snapshot("Signal", record().entity_id, NOW) is None


def test_historical_signal_and_point_in_time_replay(database: tuple[str, str]) -> None:
    _, runtime = database
    journal = Journal(runtime, "research", "pilot-sim")
    first = record()
    later = NOW + timedelta(seconds=10)
    second = replace(record(version=2), available_at=later, processed_at=later, sequence="0")
    second.payload["state"] = "CANCELLED"
    journal.append([first, second])
    assert journal.snapshot("Signal", first.entity_id, NOW) == first.payload
    assert journal.snapshot("Signal", first.entity_id, later) == second.payload
    assert len(journal.replay(NOW)) == 1
    # Event time alone must never expose data that was not yet available.
    assert len(journal.replay(NOW - timedelta(seconds=1))) == 0
    with pytest.raises(PersistenceConflict):
        journal.append([replace(first, idempotency_key="overwrite-attempt")])
    assert len(journal.replay(later)) == 2


def test_late_market_event_sequence_and_experiment(database: tuple[str, str]) -> None:
    _, runtime = database
    market = Journal(runtime, "research", "")
    high = replace(record("MarketEvent"), sequence="99999999999999999999")
    high.payload["sequence"] = high.sequence
    late = replace(record("MarketEvent"), entity_id="late-sim", idempotency_key="late-sim")
    late.payload["event_id"] = late.entity_id
    market.append([high, late])
    assert [row["entity_id"] for row in market.replay(NOW)] == [late.entity_id, high.entity_id]
    journal = Journal(runtime, "research", "pilot-sim")
    journal.append([record("Experiment")])
    assert len(journal.replay(NOW)) == 1


def test_account_mode_isolation_and_immutable_sql(database: tuple[str, str]) -> None:
    _, runtime = database
    journal = Journal(runtime, "research", "pilot-sim")
    journal.append([record()])
    assert Journal(runtime, "research", "other").replay(NOW) == []
    with pytest.raises(ValueError, match="Database"):
        Journal(runtime, "paper", "pilot-sim").replay(NOW)
    with psycopg.connect(runtime) as connection:
        assert connection.execute("SELECT count(*) FROM journal").fetchone() == (0,)
        scope(connection, "other")
        assert connection.execute("SELECT count(*) FROM signal_versions").fetchone() == (0,)
        scope(connection)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "INSERT INTO journal (mode, user_id, kind, entity_id, version, idempotency_key, "
                "content_digest, event_time, received_at, available_at, processed_at, sequence, "
                "source, data_origin, contract_version, actor, reason, payload) "
                "SELECT mode, 'intruder', kind, entity_id, version, 'intruder', content_digest, "
                "event_time, received_at, available_at, processed_at, sequence, source, "
                "data_origin, contract_version, actor, reason, payload FROM journal"
            )
    for statement in (
        "UPDATE journal SET reason = 'edit'",
        "DELETE FROM journal",
        "TRUNCATE journal",
    ):
        with psycopg.connect(runtime) as connection:
            scope(connection)
            with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                connection.execute(statement)


def test_retention_default_hold_and_explicit_candidate(database: tuple[str, str]) -> None:
    owner, runtime = database
    journal = Journal(runtime, "research", "pilot-sim")
    journal.append([record()])
    with psycopg.connect(owner) as connection:
        connection.execute(
            "INSERT INTO retention_policy VALUES "
            "('research', 'sim-fixture', 1, true, 'sim-approval')"
        )
        scope(connection)
        assert connection.execute("SELECT count(*) FROM retention_candidates").fetchone() == (0,)
        connection.execute(
            "INSERT INTO journal (mode, user_id, kind, entity_id, version, idempotency_key, "
            "content_digest, event_time, received_at, available_at, processed_at, sequence, "
            "source, data_origin, contract_version, actor, reason, payload, recorded_at) "
            "SELECT mode, user_id, kind, 'old-sim', version, 'old-sim', content_digest, "
            "event_time, received_at, available_at, processed_at, sequence, source, "
            "data_origin, contract_version, actor, reason, payload, now() - interval '2 days' "
            "FROM journal"
        )
        assert connection.execute("SELECT count(*) FROM retention_candidates").fetchone() == (0,)
        connection.execute("UPDATE retention_policy SET legal_hold = false")
        # New records are not expired just because their source event_time is old.
        assert connection.execute("SELECT count(*) FROM retention_candidates").fetchone() == (1,)
