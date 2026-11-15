"""Mode/account-scoped evidence and separate paper/manual reporting at one DB snapshot."""

from datetime import datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from saham_signal.adapters.persistence import Journal
from saham_signal.application.acceptance import (
    GateDecision,
    assess,
    protocol_from_document,
    require_admission,
    validate_acceptance,
)
from saham_signal.domain.instruments import aware
from saham_signal.domain.persistence import digest


def fill_reports(receipt: dict[str, Any] | None, positions: list[dict[str, Any]]) -> dict[str, Any]:
    actual_fills = [fill for state in positions for fill in state["position"]["fills"]]
    if any(f.get("origin") != "manual" for f in actual_fills) or len(
        {f["fill_id"] for f in actual_fills}
    ) != len(actual_fills):
        raise ValueError("Actual ledger has invalid fill provenance or duplicate identity")
    paper_fills = receipt["paper_fills"] if receipt else []
    return {
        "combined_pnl": None,
        "paper": {
            "source": "paper_qualification",
            "origin": "simulation",
            "available": receipt is not None,
            "as_of": receipt["as_of"] if receipt else None,
            "receipt_sha256": receipt["sha256"] if receipt else None,
            "fill_count": len(paper_fills),
            "buy_shares": sum(f["shares"] for f in paper_fills if f["side"] == "buy"),
            "sell_shares": sum(f["shares"] for f in paper_fills if f["side"] == "sell"),
            "open_shares": sum(receipt["paper_positions"].values()) if receipt else 0,
            "net_cash_flow_idr": receipt["execution"]["net_cash_flow_idr"] if receipt else None,
        },
        "actual": {
            "source": "manual_position_events",
            "source_mode": "paper",
            "origin": "manual",
            "available": True,
            "broker_verified": False,
            "fill_count": len(actual_fills),
            "buy_lots": sum(f["lots"] for f in actual_fills if f["side"] == "BUY"),
            "sell_lots": sum(f["lots"] for f in actual_fills if f["side"] == "SELL"),
            "remaining_lots": sum(s["position"]["remaining_lots"] for s in positions),
            "realized_pnl_idr": format(
                sum((Decimal(s["realized_pnl_idr"]) for s in positions), Decimal(0)), ".2f"
            ),
        },
    }


class PostgresPaperEvidence:
    def __init__(self, dsn: str, account: str) -> None:
        if not account or len(account) > 128:
            raise ValueError("Account required")
        self.dsn, self.account = dsn, account

    def record(self, kind: str, payload: dict[str, Any], expected_cursor: int, actor: str) -> int:
        if kind in {"G0", "G1"}:
            review = GateDecision.model_validate(payload)
            if review.gate != kind or review.reviewer != actor:
                raise ValueError("Gate/reviewer identity mismatch")
        elif kind == "acceptance":
            validate_acceptance(payload)
            if payload["format"] == "SS-026-reviewed-e2e-v2" and payload["reviewer"] != actor:
                raise ValueError("E2E reviewer identity mismatch")
        elif kind == "protocol":
            protocol_from_document(payload)
        else:
            raise ValueError("Unknown evidence kind")
        if type(expected_cursor) is not int or expected_cursor < 0 or not actor.strip():
            raise ValueError("Expected cursor and actor required")
        fingerprint = digest(payload)
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=3) as conn:
            conn.execute("SET LOCAL statement_timeout='5s'")
            Journal(self.dsn, "paper", self.account)._scope(conn)
            role = conn.execute("SELECT paper_evidence_operator() AS allowed").fetchone()
            if not role or not role["allowed"]:
                raise ValueError("Evidence import requires a separate BYPASSRLS operator")
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"paper-evidence:{self.account}",),
            )
            duplicate = conn.execute(
                "SELECT cursor,actor FROM paper_evidence WHERE mode='paper' AND user_id=%s "
                "AND kind=%s AND content_digest=%s",
                (self.account, kind, fingerprint),
            ).fetchone()
            if duplicate:
                if duplicate["actor"] != actor:
                    raise ValueError("Receipt already belongs to another reviewer")
                return int(duplicate["cursor"])
            current = conn.execute(
                "SELECT coalesce(max(cursor),0) AS cursor FROM paper_evidence "
                "WHERE mode='paper' AND user_id=%s AND kind=%s",
                (self.account, kind),
            ).fetchone()
            if not current or current["cursor"] != expected_cursor:
                raise ValueError("Evidence revision conflict")
            row = conn.execute(
                "INSERT INTO paper_evidence(mode,user_id,kind,content_digest,actor,payload) "
                "VALUES ('paper',%s,%s,%s,%s,%s) RETURNING cursor",
                (self.account, kind, fingerprint, actor, Jsonb(payload)),
            ).fetchone()
            assert row
            return int(row["cursor"])

    def report(self, release: str | None, at: datetime, *, paused: bool) -> dict[str, Any]:
        aware(at)
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=3) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL statement_timeout='5s'")
            Journal(self.dsn, "paper", self.account)._scope(conn)
            rows = list(
                conn.execute(
                    "SELECT DISTINCT ON (kind) kind,cursor,content_digest,payload "
                    "FROM paper_evidence "
                    "WHERE mode='paper' AND user_id=%s ORDER BY kind,cursor DESC",
                    (self.account,),
                )
            )
            for row in rows:
                if digest(row["payload"]) != row["content_digest"]:
                    raise ValueError("Stored evidence integrity mismatch")
            latest = conn.execute(
                "SELECT snapshot FROM paper_qualification WHERE mode='paper' AND user_id=%s "
                "ORDER BY recorded_at DESC,content_digest DESC LIMIT 1",
                (self.account,),
            ).fetchone()
            receipt = latest["snapshot"] if latest else None
            if (
                receipt
                and digest({k: v for k, v in receipt.items() if k != "sha256"})
                != (receipt["sha256"])
            ):
                raise ValueError("Stored paper receipt integrity mismatch")
            positions = [
                r["snapshot"]
                for r in conn.execute(
                    "SELECT DISTINCT ON (position_id) snapshot FROM manual_position_events "
                    "WHERE mode='paper' AND user_id=%s ORDER BY position_id,cursor DESC",
                    (self.account,),
                )
            ]
            control = conn.execute(
                "SELECT blocked FROM operation_events WHERE mode='paper' "
                "ORDER BY revision DESC LIMIT 1"
            ).fetchone()
            assessment = assess(
                release,
                at,
                {r["kind"]: r["payload"] for r in rows},
                paused=paused or not control or bool(control["blocked"]),
            )
            assessment["evidence_cursors"] = {r["kind"]: r["cursor"] for r in rows}
            reports = fill_reports(receipt, positions)
            assessment["criteria"]["paper_actual_fills_separated"] = True
            return {
                "receipt": receipt,
                "acceptance": assessment,
                "fill_reports": reports,
            }

    def require_admission(self, release: str, at: datetime, *, paused: bool) -> dict[str, Any]:
        result = self.report(release, at, paused=paused)
        require_admission(result["acceptance"])
        return result
