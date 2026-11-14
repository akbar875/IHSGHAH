"""Internal SS-027 evidence review. No execution, gate approval or promotion ports.

Imported session receipts are assertions, not proof of licensed prospective data.
Keep the original sealed manifest and journal externally to detect replacement.
"""

from collections import Counter
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from random import Random
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saham_signal.application.paper import ObservationProtocol
from saham_signal.domain.instruments import JAKARTA, aware
from saham_signal.domain.persistence import digest

D = Decimal


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Campaign(Frozen):
    campaign_id: str = Field(min_length=1)
    origin: Literal["simulation", "prospective"]
    frozen_at: datetime
    starts_at: datetime
    ends_at: datetime
    validation_ref: str | None = None
    maximum_brier: Decimal | None = None
    maximum_fill_rate_error: Decimal | None = None
    maximum_drawdown_idr: Decimal | None = None
    model_version: str = Field(min_length=1)
    fee_version: str = Field(min_length=1)
    assumptions_ref: str = Field(min_length=1)
    holdout_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    calendar_ref: str = Field(min_length=1)
    minimum_sessions: int = Field(default=60, strict=True, ge=60)
    minimum_trades: int = Field(default=300, strict=True, ge=300)
    minimum_effective_clusters: int = Field(default=30, strict=True, ge=2)
    block_sessions: int = Field(default=5, strict=True, ge=1)
    bootstrap_samples: int = Field(default=1000, strict=True, ge=100, le=10000)
    seed: int = Field(default=27, strict=True)

    def protocol(self) -> ObservationProtocol:
        return ObservationProtocol(
            self.frozen_at,
            self.starts_at,
            self.validation_ref,
            self.maximum_brier,
            self.maximum_fill_rate_error,
            self.maximum_drawdown_idr,
            self.minimum_sessions,
            self.minimum_trades,
        )

    @model_validator(mode="after")
    def check(self) -> Self:
        self.protocol()
        aware(self.ends_at)
        if self.ends_at <= self.starts_at:
            raise ValueError("Observation window must end after it starts")
        return self

    def seal(self) -> str:
        return digest(self.model_dump(mode="json"))


class Trial(Frozen):
    trial_id: str = Field(min_length=1)
    signal_cluster: str = Field(min_length=1)
    decision_at: datetime
    resolved_at: datetime | None = None
    evidence_ref: str = Field(min_length=1)
    eligible: bool = Field(strict=True)
    filled: bool = Field(strict=True)
    target_hit: bool | None = Field(default=None, strict=True)
    probability: Decimal | None = Field(default=None, ge=0, le=1)
    predicted_fill: Decimal = Field(ge=0, le=1)
    # Mark-to-market net equity contribution, including fees and open risk.
    net_equity_idr: Decimal
    symbol: str = Field(min_length=1)
    regime: str = Field(min_length=1)
    liquidity: str = Field(min_length=1)
    nominal_idr: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def check(self) -> Self:
        aware(self.decision_at)
        if self.resolved_at is not None:
            aware(self.resolved_at)
            if self.resolved_at < self.decision_at:
                raise ValueError("Outcome cannot precede decision")
        if self.filled and not self.eligible:
            raise ValueError("Ineligible trial cannot fill")
        if self.target_hit is not None and (not self.filled or self.resolved_at is None):
            raise ValueError("Target label requires resolved paper fill")
        if not self.eligible and self.net_equity_idr != 0:
            raise ValueError("Ineligible trial cannot contribute equity")
        return self


class Session(Frozen):
    session: date
    completed_at: datetime
    source_receipt: str = Field(min_length=1)
    model_version: str
    fee_version: str
    # Includes equity of positions carried across sessions, not just closed PnL.
    closing_equity_idr: Decimal
    trials: tuple[Trial, ...] = ()


class Entry(Frozen):
    sequence: int = Field(strict=True, ge=1)
    campaign_sha256: str
    previous_sha256: str
    receipt: Session
    sha256: str


def entry_hash(entry: Entry) -> str:
    return digest(entry.model_dump(mode="json", exclude={"sha256"}))


def validate(campaign: Campaign, entries: tuple[Entry, ...], as_of: datetime) -> None:
    aware(as_of)
    previous = campaign.seal()
    sessions: set[date] = set()
    trial_ids: set[str] = set()
    trial_receipts: set[str] = set()
    receipts: set[str] = set()
    last_completed = campaign.starts_at
    last_date: date | None = None
    for i, entry in enumerate(entries, 1):
        s = entry.receipt
        aware(s.completed_at)
        if (entry.sequence, entry.campaign_sha256, entry.previous_sha256) != (
            i,
            campaign.seal(),
            previous,
        ) or entry.sha256 != entry_hash(entry):
            raise ValueError("Journal chain or campaign seal mismatch")
        if s.session in sessions or s.source_receipt in receipts:
            raise ValueError("Duplicate session or source receipt")
        if last_date is not None and s.session <= last_date:
            raise ValueError("Sessions must be chronological")
        if s.session.weekday() >= 5:
            raise ValueError("Weekend is not a regular exchange session")
        if (s.model_version, s.fee_version) != (campaign.model_version, campaign.fee_version):
            raise ValueError("Version change requires a new campaign")
        if not last_completed <= s.completed_at <= min(as_of, campaign.ends_at):
            raise ValueError("Receipt outside observation window or out of order")
        if s.completed_at.astimezone(JAKARTA).date() < s.session:
            raise ValueError("Receipt cannot complete before its session")
        if s.session < campaign.starts_at.astimezone(JAKARTA).date():
            raise ValueError("Session predates campaign")
        for t in s.trials:
            if t.trial_id in trial_ids:
                raise ValueError("Duplicate trial; retries must reuse the original journal")
            if t.evidence_ref in trial_receipts:
                raise ValueError("Duplicate trial evidence cannot count as another trade")
            if not campaign.starts_at <= t.decision_at <= s.completed_at:
                raise ValueError("Decision outside observation window")
            if t.decision_at.astimezone(JAKARTA).date() != s.session:
                raise ValueError("Decision must belong to the WIB session")
            if t.resolved_at is not None and t.resolved_at > s.completed_at:
                raise ValueError("Future outcome in session receipt")
            trial_ids.add(t.trial_id)
            trial_receipts.add(t.evidence_ref)
        sessions.add(s.session)
        receipts.add(s.source_receipt)
        previous, last_completed, last_date = entry.sha256, s.completed_at, s.session


def append(campaign: Campaign, entries: tuple[Entry, ...], receipt: Session) -> tuple[Entry, ...]:
    """Return a new chain; never edit old receipts or silently refit a protocol."""
    entry = Entry(
        sequence=len(entries) + 1,
        campaign_sha256=campaign.seal(),
        previous_sha256=entries[-1].sha256 if entries else campaign.seal(),
        receipt=receipt,
        sha256="",
    )
    result = (*entries, entry.model_copy(update={"sha256": entry_hash(entry)}))
    validate(campaign, result, receipt.completed_at)
    return result


def estimates(sessions: tuple[Session, ...]) -> dict[str, Decimal | None]:
    trials = [t for s in sessions for t in s.trials if t.eligible]
    errors = [
        (t.probability - D(int(t.target_hit))) ** 2
        for t in trials
        if t.probability is not None and t.target_hit is not None
    ]
    brier = sum(errors, D(0)) / len(errors) if errors else None
    fill_error = (
        abs(sum((D(int(t.filled)) - t.predicted_fill for t in trials), D(0)) / len(trials))
        if trials
        else None
    )
    # Opening equity is normalized to zero; closure snapshots must include open MTM.
    peak = drawdown = D(0)
    for s in sessions:
        peak = max(peak, s.closing_equity_idr)
        drawdown = max(drawdown, peak - s.closing_equity_idr)
    return {
        "brier": brier,
        "fill_rate_error": fill_error,
        "session_close_drawdown_idr": drawdown if sessions else None,
    }


def report(campaign: Campaign, entries: tuple[Entry, ...], as_of: datetime) -> dict[str, Any]:
    with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
        return _report(campaign, entries, as_of)


def _report(campaign: Campaign, entries: tuple[Entry, ...], as_of: datetime) -> dict[str, Any]:
    validate(campaign, entries, as_of)
    sessions = tuple(e.receipt for e in entries)
    trials = [t for s in sessions for t in s.trials]
    attempts = [t for t in trials if t.eligible]
    eligible = [t for t in attempts if t.filled]
    # A cluster can span sessions. Treat all trials in it as fully dependent.
    clusters = Counter(t.signal_cluster for t in eligible)
    effective = D(len(eligible) ** 2) / sum(n * n for n in clusters.values()) if clusters else D(0)
    metrics = estimates(sessions)
    intervals: dict[str, list[str] | None] = dict.fromkeys(metrics)
    if len(sessions) >= max(campaign.minimum_sessions, 2 * campaign.block_sessions):
        rng = Random(campaign.seed)
        draws: dict[str, list[Decimal]] = {key: [] for key in metrics}
        for _ in range(campaign.bootstrap_samples):
            sampled: list[Session] = []
            while len(sampled) < len(sessions):
                start = rng.randrange(len(sessions) - campaign.block_sessions + 1)
                sampled.extend(sessions[start : start + campaign.block_sessions])
            # Reconstruct equity from session increments to avoid reordered level jumps.
            increments = {
                s.session: s.closing_equity_idr
                - (sessions[i - 1].closing_equity_idr if i else D(0))
                for i, s in enumerate(sessions)
            }
            equity = D(0)
            path: list[Session] = []
            for s in sampled[: len(sessions)]:
                equity += increments[s.session]
                path.append(s.model_copy(update={"closing_equity_idr": equity}))
            for key, value in estimates(tuple(path)).items():
                if value is not None:
                    draws[key].append(value)
        for key, values in draws.items():
            if len(values) == campaign.bootstrap_samples:
                values.sort()
                intervals[key] = [str(values[int((len(values) - 1) * q)]) for q in (0.025, 0.975)]
    reasons = ["G0_G1_AND_SS026_PROSPECTIVE_EVIDENCE_UNAVAILABLE", "OPERATOR_REVIEW_REQUIRED"]
    if campaign.origin == "simulation":
        reasons.append("SIMULATION_EXCLUDED_FROM_G2")
    if len(sessions) < campaign.minimum_sessions or len(eligible) < campaign.minimum_trades:
        reasons.append("MINIMUM_OBSERVATION_INCOMPLETE")
    if effective < campaign.minimum_effective_clusters:
        reasons.append("DEPENDENT_SAMPLE_INSUFFICIENT")
    if any(t.probability is None or t.target_hit is None for t in eligible):
        reasons.append("CALIBRATION_OR_OUTCOMES_INCOMPLETE")
    if as_of < campaign.ends_at:
        reasons.append("FROZEN_WINDOW_INCOMPLETE")
    budgets = campaign.protocol().document()["budgets_complete"]
    if not budgets:
        reasons.append("VALIDATION_TOLERANCES_MISSING")
    limits = {
        "brier": campaign.maximum_brier,
        "fill_rate_error": campaign.maximum_fill_rate_error,
        "session_close_drawdown_idr": campaign.maximum_drawdown_idr,
    }
    checks: dict[str, str] = {}
    for key, limit in limits.items():
        value, interval = metrics[key], intervals[key]
        checks[key] = (
            "pending"
            if limit is None or value is None
            else "breach"
            if value > limit
            else "uncertain"
            if interval is None or D(interval[1]) > limit
            else "within_tolerance"
        )
    breach = "breach" in checks.values()
    if breach:
        reasons.append("TOLERANCE_BREACH_STOP_AND_REVIEW")
    if any(v in ("pending", "uncertain") for v in checks.values()):
        reasons.append("UNCERTAINTY_OR_METRICS_INSUFFICIENT")
    breakdown: dict[str, dict[str, int]] = {}
    for key in ("symbol", "regime", "liquidity", "nominal_idr"):
        breakdown[key] = dict(Counter(str(getattr(t, key)) for t in eligible))
    body = {
        "schema_version": 1,
        "campaign": campaign.model_dump(mode="json"),
        "campaign_sha256": campaign.seal(),
        "as_of": as_of.isoformat(),
        "journal_head": entries[-1].sha256 if entries else campaign.seal(),
        "g2": "no-go" if breach else "pending",
        "model_promoted": False,
        "paper_live_enabled": False,
        "reasons": reasons,
        "observed_sessions": len(sessions),
        "eligible_attempts": len(attempts),
        "eligible_paper_trades": len(eligible),
        "g2_credited_sessions": 0,
        "g2_credited_trades": 0,
        "first_session": str(sessions[0].session) if sessions else None,
        "last_session": str(sessions[-1].session) if sessions else None,
        "elapsed_calendar_days": (sessions[-1].session - sessions[0].session).days + 1
        if sessions
        else 0,
        "signal_clusters": len(clusters),
        "largest_cluster": max(clusters.values(), default=0),
        "cluster_effective_sample": str(effective),
        "dependence_method": "Kish cluster weights; fully dependent within cluster; not IID trades",
        "uncertainty_method": "95% moving session-block percentile bootstrap; validation-frozen",
        "metrics": {k: str(v) if v is not None else None for k, v in metrics.items()},
        "intervals_95": intervals,
        "checks": checks,
        "breakdown": breakdown,
        "limits": [
            "Imported receipts and calendar require independent verification",
            "Session-close MTM drawdown excludes intraday peaks",
            "Cluster ESS is a diagnostic, not proof of independent samples",
            "Bootstrap cannot prove safety in unseen regimes",
        ],
    }
    return {**body, "sha256": digest(body)}
