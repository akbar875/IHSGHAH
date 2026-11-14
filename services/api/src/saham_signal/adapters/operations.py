"""Cross-process kill switch with compare-and-swap and append-only audit."""

import psycopg
from psycopg.rows import dict_row

from saham_signal.adapters.persistence import Journal
from saham_signal.application.operations import Action, Control, change
from saham_signal.domain.mode import Mode


class PostgresControl:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def read(self, mode: Mode) -> Control:
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=2) as conn:
            conn.execute("SET LOCAL statement_timeout='3s'")
            Journal(self.dsn, mode, "")._scope(conn)
            row = conn.execute(
                "SELECT revision,blocked,reason,release FROM operation_events "
                "WHERE mode=%s ORDER BY revision DESC LIMIT 1",
                (mode,),
            ).fetchone()
            return Control(**row) if row else Control()

    def write(
        self, mode: Mode, expected: int, action: Action, release: str, evidence: str, actor: str
    ) -> Control:
        if not 1 <= len(actor.strip()) <= 128:
            raise ValueError("Operator identity required")
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=2) as conn:
            conn.execute("SET LOCAL statement_timeout='3s'")
            Journal(self.dsn, mode, "")._scope(conn)
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"ops:{mode}",))
            row = conn.execute(
                "SELECT revision,blocked,reason,release FROM operation_events "
                "WHERE mode=%s ORDER BY revision DESC LIMIT 1",
                (mode,),
            ).fetchone()
            previous = Control(**row) if row else Control()
            if previous.revision != expected:
                raise ValueError("Control revision conflict")
            result = change(previous, action, release, evidence)
            conn.execute(
                "INSERT INTO operation_events(mode,revision,blocked,reason,release,evidence,actor) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (mode, result.revision, result.blocked, result.reason, release, evidence, actor),
            )
            return result
