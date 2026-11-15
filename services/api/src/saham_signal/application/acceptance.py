"""Evidence review for SS-026. Decisions are operator assertions, never inferred licenses."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saham_signal.application.paper import ObservationProtocol
from saham_signal.domain.instruments import aware
from saham_signal.domain.persistence import digest

REQUIREMENTS = {
    "G0": {
        "ingest_rights",
        "analysis_model_rights",
        "storage_replay_rights",
        "display_alert_rights",
        "feed_quality",
        "history_quality",
        "cost_capacity",
    },
    "G1": {
        "locked_holdout",
        "positive_expectancy_ci",
        "risk_budget",
        "robustness",
        "calibration_fill_validation",
    },
}
TITLES = (
    "Feed putus",
    "Heartbeat saham sepi",
    "Nominal dan likuiditas",
    "ARA tanpa penjual",
    "ARB tanpa pembeli",
    "Berita terlambat",
    "Reconnect/out-of-order",
    "Partial fill",
    "Riwayat/proyeksi",
    "Tekanan transaksi",
    "Versi dan deduplikasi",
    "Mobile 360px",
)


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Proof(Frozen):
    check: str
    passed: bool = Field(strict=True)
    origin: Literal["market", "simulation"]
    reference: str = Field(min_length=1, max_length=512, pattern=r"\S")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GateDecision(Frozen):
    gate: Literal["G0", "G1"]
    decision: Literal["passed", "pending", "no-go"]
    release: str = Field(pattern=r"^[0-9a-f]{40}$")
    reviewer: str = Field(min_length=1, max_length=128, pattern=r"\S")
    reviewed_at: datetime
    valid_until: datetime
    reason: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    proofs: tuple[Proof, ...] = ()
    data_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model_artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    validation_ref: str | None = None
    maximum_brier: Decimal | None = None
    maximum_fill_rate_error: Decimal | None = None
    maximum_drawdown_idr: Decimal | None = None

    @model_validator(mode="after")
    def check(self) -> Self:
        aware(self.reviewed_at)
        aware(self.valid_until)
        if self.valid_until <= self.reviewed_at:
            raise ValueError("Decision requires an expiry after review")
        names = [p.check for p in self.proofs]
        if len(set(names)) != len(names) or set(names) - REQUIREMENTS[self.gate]:
            raise ValueError("Duplicate or unknown gate checks")
        if self.decision == "passed":
            if not self.data_manifest_sha256:
                raise ValueError("Passing gate must bind its data manifest")
            if set(names) != REQUIREMENTS[self.gate] or any(
                not p.passed or p.origin != "market" for p in self.proofs
            ):
                raise ValueError("Passing gate needs every check and market evidence")
            if self.gate == "G1":
                if not self.model_artifact_sha256:
                    raise ValueError("Passing G1 must bind a model artifact")
                # Reuse the same finite Decimal/range validation as the frozen protocol.
                from datetime import timedelta

                protocol = ObservationProtocol(
                    self.reviewed_at,
                    self.reviewed_at + timedelta(seconds=1),
                    self.validation_ref,
                    self.maximum_brier,
                    self.maximum_fill_rate_error,
                    self.maximum_drawdown_idr,
                )
                if not protocol.document()["budgets_complete"]:
                    raise ValueError("Passing G1 requires reviewed validation tolerances")
        return self


def validate_acceptance(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the actual verifier's v1 format/hash; hashes are not reviewer approval."""
    body = {k: v for k, v in payload.items() if k != "sha256"}
    expected = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if payload.get("format") not in {"SS-026-acceptance-v1", "SS-026-reviewed-e2e-v2"} or (
        payload.get("sha256") != expected or payload.get("paper_live_enabled") is not False
    ):
        raise ValueError("Invalid acceptance receipt integrity")
    if payload["format"] == "SS-026-acceptance-v1":
        if (
            payload.get("origin") != "simulation"
            or payload.get("scope") != ("component-and-browser; no licensed-feed E2E")
            or payload.get("paper_live_enabled") is not False
        ):
            raise ValueError("Synthetic receipt cannot be relabelled as licensed evidence")
    else:
        if (payload.get("origin"), payload.get("scope")) != ("market", "licensed-feed-e2e"):
            raise ValueError("Reviewed E2E provenance required")
        if not isinstance(payload.get("reviewer"), str) or not payload["reviewer"].strip():
            raise ValueError("E2E reviewer required")
        aware(datetime.fromisoformat(payload["reviewed_at"]))
        hashes = payload.get("gate_review_sha256", {})
        if set(hashes) != {"G0", "G1"} or any(
            not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
            for v in hashes.values()
        ):
            raise ValueError("Reviewed E2E must bind both gate review hashes")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 12:
        raise ValueError("All twelve scenario results required")
    if any(not isinstance(s, dict) or type(s.get("scenario")) is not int for s in scenarios):
        raise ValueError("Integer scenario numbers required")
    if {s.get("scenario") for s in scenarios} != set(range(1, 13)):
        raise ValueError("Unique scenario numbers 1..12 required")
    for scenario in scenarios:
        if scenario.get("status") not in {"passed", "blocked"}:
            raise ValueError("Unknown scenario result")
        if (
            not isinstance(scenario.get("evidence"), list)
            or not scenario["evidence"]
            or any(
                not isinstance(e, dict)
                or e.get("source") not in {"pytest", "playwright"}
                or not e.get("test")
                or e.get("status") not in {"passed", "blocked"}
                for e in scenario["evidence"]
            )
        ):
            raise ValueError("Scenario requires named test evidence")
        if scenario["status"] == "passed" and any(
            e["status"] != "passed" for e in scenario["evidence"]
        ):
            raise ValueError("Failed evidence cannot claim a passing scenario")
    if not payload.get("evidence_hashes") or any(
        not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
        for v in payload["evidence_hashes"].values()
    ):
        raise ValueError("Source result SHA256 required")
    if type(payload.get("acceptance_passed")) is not bool or (
        payload["acceptance_passed"] and any(s["status"] != "passed" for s in scenarios)
    ):
        raise ValueError("Inconsistent acceptance result")
    return payload


def protocol_from_document(payload: dict[str, Any]) -> ObservationProtocol:
    manifest = dict(payload["manifest"])
    for field in ("frozen_at", "starts_at"):
        manifest[field] = datetime.fromisoformat(manifest[field])
    for field in ("maximum_brier", "maximum_fill_rate_error", "maximum_drawdown_idr"):
        if manifest[field] is not None:
            manifest[field] = Decimal(manifest[field])
    protocol = ObservationProtocol(**manifest)
    if protocol.document() != payload:
        raise ValueError("Frozen protocol integrity mismatch")
    return protocol


def assess(
    release: str | None, at: datetime, evidence: dict[str, dict[str, Any]], *, paused: bool
) -> dict[str, Any]:
    aware(at)
    reasons: list[str] = []
    receipt = validate_acceptance(evidence["acceptance"]) if "acceptance" in evidence else None
    scenarios = [
        {"scenario": i, "title": title, "status": "missing", "evidence": []}
        for i, title in enumerate(TITLES, 1)
    ]
    if receipt:
        for scenario in receipt["scenarios"]:
            scenarios[scenario["scenario"] - 1].update(scenario)
    qualification_passed = bool(receipt and receipt["acceptance_passed"])
    if not qualification_passed:
        reasons.append("CRITICAL_ACCEPTANCE_INCOMPLETE")
    if (
        not release
        or not receipt
        or receipt.get("revision") != release
        or (receipt.get("revision_kind") != "commit")
    ):
        reasons.append("ACCEPTANCE_RELEASE_MISMATCH")
    if (
        not receipt
        or receipt.get("scope") != "licensed-feed-e2e"
        or (receipt.get("origin") != "market")
    ):
        reasons.append("LICENSED_E2E_EVIDENCE_MISSING")
    gates: dict[str, Any] = {}
    decisions: dict[str, GateDecision] = {}
    for gate in REQUIREMENTS:
        raw = evidence.get(gate)
        decision = GateDecision.model_validate(raw) if raw else None
        current = bool(
            decision
            and decision.release == release
            and decision.reviewed_at <= at < decision.valid_until
        )
        status = decision.decision if decision and current else "pending"
        gates[gate] = {
            "decision": status,
            "current": current,
            "review": raw,
            "sha256": digest(raw) if raw else None,
        }
        if status != "passed":
            reasons.append(f"{gate}_NOT_PASSED")
        elif decision:
            decisions[gate] = decision
    protocol = protocol_from_document(evidence["protocol"]) if "protocol" in evidence else None
    if len(decisions) == 2 and (
        decisions["G0"].data_manifest_sha256 != decisions["G1"].data_manifest_sha256
        or not receipt
        or receipt.get("data_manifest_sha256") != decisions["G1"].data_manifest_sha256
        or receipt.get("model_artifact_sha256") != decisions["G1"].model_artifact_sha256
    ):
        reasons.append("MODEL_DATA_EVIDENCE_MISMATCH")
    if receipt and receipt["format"] == "SS-026-reviewed-e2e-v2":
        reviewed = datetime.fromisoformat(receipt["reviewed_at"])
        if reviewed > at or any(
            receipt["gate_review_sha256"][g] != digest(evidence.get(g, {}))
            or (g in decisions and reviewed < decisions[g].reviewed_at)
            for g in REQUIREMENTS
        ):
            reasons.append("E2E_REVIEW_MISMATCH")
    if not protocol or not protocol.document()["budgets_complete"]:
        reasons.append("VALIDATION_TOLERANCES_MISSING")
    elif g1 := decisions.get("G1"):
        if (
            any(
                getattr(protocol, field) != getattr(g1, field)
                for field in (
                    "validation_ref",
                    "maximum_brier",
                    "maximum_fill_rate_error",
                    "maximum_drawdown_idr",
                )
            )
            or protocol.frozen_at < g1.reviewed_at
        ):
            reasons.append("PROTOCOL_VALIDATION_MISMATCH")
    if protocol and protocol.starts_at < at:
        reasons.append("OBSERVATION_START_REQUIRES_REVIEW")
    if protocol and any(protocol.starts_at >= d.valid_until for d in decisions.values()):
        reasons.append("GATE_EXPIRES_BEFORE_START")
    if paused:
        reasons.append("OPERATIONS_BLOCKED")
    return {
        "release": release,
        "as_of": at.isoformat(),
        "scenarios": scenarios,
        "acceptance_passed": qualification_passed,
        "acceptance_sha256": receipt["sha256"] if receipt else None,
        "gates": gates,
        "protocol": protocol.document() if protocol else None,
        "can_advance": not reasons,
        "reasons": reasons,
        "criteria": {
            "scenario_results_and_evidence": bool(receipt),
            "g0_g1_passed": all(g["decision"] == "passed" for g in gates.values()),
            "critical_failures_block_advancement": not qualification_passed
            and bool(reasons)
            or qualification_passed,
        },
    }


def require_admission(assessment: dict[str, Any]) -> None:
    if assessment.get("can_advance") is not True or assessment.get("reasons") != []:
        raise ValueError("Paper advancement blocked by evidence review")
