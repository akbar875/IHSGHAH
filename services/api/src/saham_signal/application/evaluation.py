"""SS-016 research boundary: sealed protocol, nominal replay and OOS evidence.

No Signal/Fill persistence, serving cache, release, or broker ports. Callers persist
the protocol before unlocking the holdout and journal the one-use evaluation receipt.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from decimal import Context, Decimal, localcontext
from random import Random
from typing import Any, Literal

from saham_signal.application.features import FeatureSnapshot
from saham_signal.application.instruments import ReferenceRepository, lookup
from saham_signal.application.replay import FeeSchedule, Frame, Order, ReplayPolicy, _json, replay
from saham_signal.application.risk import PlanSpec, RiskInputs, RiskPolicy, evaluate, money
from saham_signal.domain.instruments import JAKARTA, ReferenceUnavailable, aware, positive_integer
from saham_signal.domain.persistence import digest

D = Decimal
Split = Literal["train", "validation", "test", "holdout"]
LABEL_RULE = "target-before-stop; ambiguous bar=stop; unclosed=censored"


@dataclass(frozen=True)
class Baseline:
    name: str
    kind: Literal["trend", "momentum", "volatility"]
    minimum_return: Decimal
    maximum_volatility: Decimal
    use_pressure: bool = True
    use_volume: bool = True

    def __post_init__(self) -> None:
        if not self.name or self.kind not in ("trend", "momentum", "volatility"):
            raise ValueError("Unknown baseline")
        money(self.minimum_return)
        money(self.maximum_volatility)
        if self.maximum_volatility == 0:
            raise ValueError("Positive volatility limit required")

    def score(self, features: FeatureSnapshot) -> int | None:
        """Three fixed bins; thresholds/ablations must be selected before holdout.

        A score is a rule strength, never a probability. Missing inputs abstain.
        """
        ret, vol = features.return_fraction, features.volatility_fraction
        if ret is None or vol is None:
            return None
        if ret < self.minimum_return or vol > self.maximum_volatility:
            return None
        if self.use_pressure and (
            features.buy_pressure is None or features.buy_pressure < D("0.5")
        ):
            return None
        if self.use_volume and (features.relative_volume is None or features.relative_volume < 1):
            return None
        strength = ret / self.maximum_volatility
        if self.kind == "momentum":
            volume = features.relative_volume if self.use_volume else D(1)
            assert volume is not None
            strength *= volume
        elif self.kind == "volatility":
            strength = (self.maximum_volatility - vol) / self.maximum_volatility
        return min(2, max(0, int(strength * 3)))


@dataclass(frozen=True)
class Protocol:
    id: str
    dataset_version: str
    dataset_hash: str
    context_hash: str
    code_version: str
    universe_evidence: str  # Historical membership including suspensions/delistings.
    frozen_at: datetime
    train_start: datetime
    train_end: datetime
    validation_end: datetime
    test_end: datetime
    holdout_start: datetime
    holdout_end: datetime
    label_horizon: timedelta
    purge: timedelta
    embargo: timedelta
    baselines: tuple[Baseline, ...]
    champion: str
    nominals_idr: tuple[Decimal, ...]
    risk: RiskPolicy
    execution: ReplayPolicy
    max_drawdown_idr: Decimal
    minimum_sessions: int
    minimum_calibration: int
    maximum_brier: Decimal
    bootstrap_block_sessions: int
    bootstrap_samples: int = 1000
    seed: int = 16
    label: str = LABEL_RULE

    def __post_init__(self) -> None:
        stamps = (
            self.train_start,
            self.train_end,
            self.validation_end,
            self.test_end,
            self.holdout_start,
            self.holdout_end,
        )
        for stamp in (*stamps, self.frozen_at):
            aware(stamp)
        if any(a >= b for a, b in zip(stamps, stamps[1:], strict=False)):
            raise ValueError("Chronological, disjoint split boundaries required")
        if not self.validation_end <= self.frozen_at < self.test_end:
            raise ValueError("Freeze after validation, before test ends and holdout starts")
        if self.label_horizon <= timedelta(0) or self.purge < self.label_horizon:
            raise ValueError("Purge must cover the positive label horizon")
        if self.embargo < timedelta(0):
            raise ValueError("Negative embargo")
        if self.label != LABEL_RULE:
            raise ValueError("Unsupported label rule")
        if not all((self.id, self.dataset_version, self.code_version, self.universe_evidence)):
            raise ValueError("Dataset, code and historical universe evidence required")
        for fingerprint in (self.dataset_hash, self.context_hash):
            if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
                raise ValueError("Expected dataset/context SHA256")
        names = [b.name for b in self.baselines]
        if not names or len(set(names)) != len(names) or self.champion not in names:
            raise ValueError("Unique frozen baselines and champion required")
        if not self.nominals_idr or len(set(self.nominals_idr)) != len(self.nominals_idr):
            raise ValueError("Unique nominal grid required")
        for value in (*self.nominals_idr, self.max_drawdown_idr, self.maximum_brier):
            money(value)
        if min(self.nominals_idr) <= 0 or not 0 < self.maximum_brier < 1:
            raise ValueError("Invalid nominal/calibration budget")
        for count in (
            self.minimum_sessions,
            self.minimum_calibration,
            self.bootstrap_block_sessions,
            self.bootstrap_samples,
        ):
            positive_integer(count)
        if self.bootstrap_samples < 100 or type(self.seed) is not int:
            raise ValueError("At least 100 bootstrap draws and integer seed required")

    @property
    def hash(self) -> str:
        return digest(document(asdict(self)))

    def split(self, case: "Case") -> Split | None:
        bounds: tuple[tuple[Split, datetime, datetime], ...] = (
            ("train", self.train_start, self.train_end),
            ("validation", self.train_end, self.validation_end),
            ("test", max(self.validation_end, self.frozen_at), self.test_end),
            ("holdout", self.holdout_start, self.holdout_end),
        )
        for name, start, end in bounds:
            # Both the feature window and full label interval stay inside the fold.
            if (
                start + self.embargo <= case.features.window_start <= case.spec.entry_from
                and case.spec.entry_from + self.purge < end
                and case.label_end < end
            ):
                return name
        return None


def document(value: Any) -> Any:
    if isinstance(value, timedelta):
        return {"microseconds": value // timedelta(microseconds=1)}
    if isinstance(value, dict):
        return {key: document(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [document(item) for item in value]
    return _json(value)


@dataclass(frozen=True)
class Case:
    id: str
    features: FeatureSnapshot
    spec: PlanSpec
    inputs: RiskInputs
    frames: tuple[Frame, ...]
    label_end: datetime
    regime: str
    liquidity: str

    def __post_init__(self) -> None:
        aware(self.label_end)
        f, s = self.features, self.spec
        if not all((self.id, self.regime, self.liquidity)):
            raise ValueError("Case metadata required")
        if s.mode != "research" or f.mode != "research" or self.inputs.portfolio.mode != "research":
            raise ValueError("Evaluation only accepts research inputs")
        if f.symbol != s.symbol or f.as_of != s.entry_from or self.inputs.at != s.entry_from:
            raise ValueError("Feature/decision identity and cutoff must match")
        if not f.window_start <= f.as_of < s.exit_deadline <= self.label_end:
            raise ValueError("Invalid feature/label horizon")
        if f.data_origin not in ("simulation", "market"):
            raise ValueError("Unknown data origin")
        if f.data_origin != self.inputs.feed.data_origin:
            raise ValueError("Mixed feature/feed origin")
        if any(
            frame.symbol != s.symbol or not s.entry_from <= frame.available_at <= self.label_end
            for frame in self.frames
        ):
            raise ValueError("Frame outside label or symbol")


def dataset_hash(cases: Sequence[Case]) -> str:
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("Duplicate case identity")
    return digest(document([asdict(c) for c in sorted(cases, key=lambda c: c.id)]))


def context_hash(
    cases: Sequence[Case],
    references: ReferenceRepository,
    fees: Sequence[FeeSchedule],
) -> str:
    snapshots: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda c: c.id):
        stamps = {case.spec.entry_from, *(f.available_at for f in case.frames)}
        for at in sorted(stamps):
            try:
                value = document(asdict(lookup(references, case.spec.symbol, "regular", at, at)))
            except ReferenceUnavailable as exc:
                value = {"unavailable": str(exc)}
            snapshots.append({"symbol": case.spec.symbol, "at": at.isoformat(), "value": value})
    return digest({"references": snapshots, "fees": document([asdict(f) for f in fees])})


def execute(
    case: Case,
    baseline: Baseline,
    nominal: Decimal,
    protocol: Protocol,
    references: ReferenceRepository,
    fees: Sequence[FeeSchedule],
) -> dict[str, Any]:
    """Recompute risk/fees/depth for every account and nominal; no shared cache.

    Each case is a standalone hypothetical plan. Portfolio equity is not advanced
    between cases; overlapping positions cannot establish portfolio-level G1.
    """
    money(nominal)
    if nominal <= 0:
        raise ValueError("Positive nominal required")
    score = baseline.score(case.features)
    inputs = replace(
        case.inputs,
        portfolio=replace(
            case.inputs.portfolio,
            free_cash_idr=min(nominal, case.inputs.portfolio.free_cash_idr),
        ),
        trigger_met=case.inputs.trigger_met and score is not None,
    )
    decision = evaluate(case.spec, inputs, references, fees, protocol.risk)
    row: dict[str, Any] = {
        "case": case.id,
        "account": case.spec.account,
        "nominal_idr": str(nominal),
        "symbol": case.spec.symbol,
        "session": case.spec.entry_from.astimezone(JAKARTA).date().isoformat(),
        "at": case.spec.entry_from.isoformat(),
        "label_end": case.label_end.isoformat(),
        "regime": case.regime,
        "liquidity": case.liquidity,
        "horizon_seconds": int(protocol.label_horizon.total_seconds()),
        "score": score,
        "eligible": decision.allowed,
        "reason": decision.reason,
        "risk": document(asdict(decision)),
        "requested": decision.shares,
        "filled": 0,
        "exited": 0,
        "open": 0,
        "net_idr": "0",
        "cash_flow_idr": "0",
        "target": None,
        "probability": None,
        "research_probability": None,
        "fill_probability": None,
        "time_to_fill_seconds": None,
        "slippage_idr": "0",
        "turnover_idr": "0",
    }
    if not decision.allowed:
        return row
    s = case.spec
    lower_limit = lookup(
        references, s.symbol, "regular", s.entry_from, s.entry_from
    ).limits.lower_idr
    orders = (
        Order("entry", s.symbol, "buy", decision.shares, s.entry_idr, s.entry_from, s.expires_at),
        # The dated lower limit permits adverse stop execution inside daily limits.
        Order(
            "exit",
            s.symbol,
            "sell",
            decision.shares,
            lower_limit,
            s.entry_from,
            s.exit_deadline,
            s.stop_idr,
            s.target_idr,
        ),
    )
    result = replay(
        references,
        fees,
        orders,
        case.frames,
        policy=protocol.execution,
        seed=protocol.seed,
        data_limits=("SS-016 standalone hypothetical plan; no actual fills",),
    )
    buys = [f for f in result["fills"] if f["side"] == "buy"]
    sells = [f for f in result["fills"] if f["side"] == "sell"]
    filled = sum(f["shares"] for f in buys)
    exited = sum(f["shares"] for f in sells)
    row.update(
        filled=filled,
        exited=exited,
        open=filled - exited,
        cash_flow_idr=result["net_cash_flow_idr"],
        replay=result,
        # Censored positions get no invented realized P&L or successful label.
        net_idr=result["net_cash_flow_idr"] if filled == exited else None,
        target=int(all(f["trigger"] == "target" for f in sells))
        if filled == exited and filled
        else None,
        turnover_idr=str(sum((D(f["gross_idr"]) for f in result["fills"]), D(0))),
        slippage_idr=str(
            sum((D(f["price_idr"] - inputs.ask_idr) * f["shares"] for f in buys), D(0))
        ),
    )
    if buys:
        row["time_to_fill_seconds"] = str(
            D(str((datetime.fromisoformat(buys[0]["filled_at"]) - s.entry_from).total_seconds()))
        )
    return row


def calibrate(rows: Sequence[dict[str, Any]], minimum: int) -> dict[int, Decimal]:
    """Validation-only empirical target frequency, conditional on full exit.

    These are candidate calibrators; held-out Brier/reliability are still required.
    They never calibrate fill probability or justify live probability publication.
    """
    bins: dict[int, list[int]] = defaultdict(list)
    for row in rows:
        if row["target"] is not None and row["score"] is not None:
            bins[row["score"]].append(row["target"])
    return {
        key: D(sum(values)) / len(values) for key, values in bins.items() if len(values) >= minimum
    }


def metrics(rows: Sequence[dict[str, Any]], protocol: Protocol) -> dict[str, Any]:
    attempts = [r for r in rows if r["eligible"]]
    closed = [r for r in attempts if r["filled"] and r["open"] == 0]
    values = [D(r["net_idr"]) for r in closed]
    # Use final cash-flow receipt order; report this as realized-plan drawdown only.
    equity = peak = drawdown = D(0)
    for row in sorted(closed, key=lambda r: (r["label_end"], r["case"])):
        equity += D(row["net_idr"])
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    sessions: dict[str, list[Decimal]] = defaultdict(list)
    for row in closed:
        sessions[row["session"]].append(D(row["net_idr"]))
    groups = [sessions[key] for key in sorted(sessions)]
    interval = None
    if len(groups) >= max(protocol.minimum_sessions, 2 * protocol.bootstrap_block_sessions):
        rng = Random(protocol.seed)
        estimates = []
        block = protocol.bootstrap_block_sessions
        for _ in range(protocol.bootstrap_samples):
            sampled: list[list[Decimal]] = []
            while len(sampled) < len(groups):
                start = rng.randrange(len(groups) - block + 1)
                sampled.extend(groups[start : start + block])
            observations = [value for group in sampled[: len(groups)] for value in group]
            estimates.append(sum(observations, D(0)) / len(observations))
        estimates.sort()
        interval = [str(estimates[int(len(estimates) * q)]) for q in (0.025, 0.975)]
    calibrated = [r for r in closed if r["research_probability"] is not None]
    reliability = []
    for score in range(3):
        group = [r for r in calibrated if r["score"] == score]
        if group:
            reliability.append(
                {
                    "bin": score,
                    "count": len(group),
                    "predicted": str(
                        sum((D(r["research_probability"]) for r in group), D(0)) / len(group)
                    ),
                    "observed": str(D(sum(r["target"] for r in group)) / len(group)),
                }
            )
    requested = sum(r["requested"] for r in attempts)
    filled = sum(r["filled"] for r in attempts)
    times = [
        D(r["time_to_fill_seconds"]) for r in attempts if r["time_to_fill_seconds"] is not None
    ]
    ordered_values = sorted(values)
    return {
        "observations": len(rows),
        "eligible": len(attempts),
        "closed": len(closed),
        "sessions": len(groups),
        "coverage": str(D(len(attempts)) / len(rows)) if rows else None,
        "abstention": str(D(len(rows) - len(attempts)) / len(rows)) if rows else None,
        "expectancy_net_idr": str(sum(values, D(0)) / len(values)) if values else None,
        "expectancy_95_block_ci_idr": interval,
        "realized_plan_drawdown_idr": str(drawdown),
        "net_idr": str(sum(values, D(0))),
        "losses_idr": [str(v) for v in ordered_values if v < 0],
        "tail_5pct_idr": str(ordered_values[int((len(values) - 1) * 0.05)]) if values else None,
        "fill_share_rate": str(D(filled) / requested) if requested else None,
        "mean_time_to_first_fill_seconds": str(sum(times, D(0)) / len(times)) if times else None,
        "open_shares": sum(r["open"] for r in attempts),
        "turnover_idr": str(sum((D(r["turnover_idr"]) for r in attempts), D(0))),
        "entry_slippage_idr": str(sum((D(r["slippage_idr"]) for r in attempts), D(0))),
        "tp_before_stop": str(D(sum(r["target"] for r in closed)) / len(closed))
        if closed
        else None,
        "precision_net_positive": str(D(sum(v > 0 for v in values)) / len(values))
        if values
        else None,
        "closed_fill_coverage": str(D(len(closed)) / len(attempts)) if attempts else None,
        "calibration": {
            "count": len(calibrated),
            "reliability": reliability,
            "brier": str(
                sum(((D(r["research_probability"]) - r["target"]) ** 2 for r in calibrated), D(0))
                / len(calibrated)
            )
            if calibrated
            else None,
            "coverage": str(D(len(calibrated)) / len(closed)) if closed else None,
            "fill_probability": None,
        },
        "projection_interval_coverage": None,
    }


class Study:
    """One sealed dataset/protocol; evaluate once, including the final holdout.

    This in-process guard is not a durable lock. Persist protocol + consumed receipt
    atomically in the experiment journal before handing the report to researchers.
    Never reconstruct a Study to reuse an unlocked holdout for model selection.
    """

    def __init__(self, protocol: Protocol) -> None:
        self.protocol = protocol
        self._consumed = False

    def run(
        self,
        cases: Sequence[Case],
        references: ReferenceRepository,
        fees: Sequence[FeeSchedule],
        *,
        evaluated_at: datetime,
    ) -> dict[str, Any]:
        with localcontext(Context(prec=60)):
            return self._run(cases, references, fees, evaluated_at=evaluated_at)

    def _run(
        self,
        cases: Sequence[Case],
        references: ReferenceRepository,
        fees: Sequence[FeeSchedule],
        *,
        evaluated_at: datetime,
    ) -> dict[str, Any]:
        aware(evaluated_at)
        p = self.protocol
        if self._consumed:
            raise ValueError("Holdout already consumed; create a new prospective dataset")
        if evaluated_at < p.holdout_end or dataset_hash(cases) != p.dataset_hash:
            raise ValueError("Holdout incomplete or dataset differs from sealed manifest")
        if context_hash(cases, references, fees) != p.context_hash:
            raise ValueError("Reference/fee context differs from sealed protocol")
        if len({c.spec.account for c in cases}) != 1:
            raise ValueError("Study must isolate one account")
        for case in cases:
            if case.label_end - case.spec.entry_from > p.label_horizon:
                raise ValueError("Label exceeds frozen horizon")
        # Burn receipt before any model execution, including failed experiments.
        self._consumed = True
        report: dict[str, Any] = {
            "version": "SS-016-v1",
            "protocol": document(asdict(p)),
            "protocol_hash": p.hash,
            "evaluated_at": evaluated_at.isoformat(),
            "status": "experiment",
            "mode": "research",
            "data_origins": sorted({c.features.data_origin for c in cases}),
            "execution_origin": "simulation",
            "auto_promotion": False,
            "live_alerts_enabled": False,
            "holdout_consumed": True,
            "experiments": [],
            "excluded_cases": sorted(c.id for c in cases if p.split(c) is None),
            "limitations": [
                "hypothetical independent plans, not a portfolio backtest or executable signal",
                "realized closed-plan drawdown excludes unrealized losses; open positions block G1",
                "session-block percentile bootstrap; draws are not independent market observations",
                "target calibration conditional on complete exit; no fill/projection model",
                "G0 vendor evidence and independent portfolio/risk review still required",
            ],
        }
        for baseline in p.baselines:
            for nominal in p.nominals_idr:
                folds: dict[str, list[dict[str, Any]]] = {
                    name: [] for name in ("train", "validation", "test", "holdout")
                }
                for case in sorted(cases, key=lambda c: (c.spec.entry_from, c.id)):
                    split = p.split(case)
                    if split is not None:
                        folds[split].append(execute(case, baseline, nominal, p, references, fees))
                calibration = calibrate(folds["validation"], p.minimum_calibration)
                for oos_split in ("test", "holdout"):
                    for row in folds[oos_split]:
                        probability = calibration.get(row["score"])
                        row["research_probability"] = (
                            str(probability) if probability is not None else None
                        )
                summary = {split: metrics(rows, p) for split, rows in folds.items()}
                breakdown = {}
                for dimension in ("regime", "liquidity", "symbol", "session", "horizon_seconds"):
                    breakdown[dimension] = {
                        str(value): metrics(
                            [r for r in folds["holdout"] if r[dimension] == value], p
                        )
                        for value in sorted({r[dimension] for r in folds["holdout"]})
                    }
                report["experiments"].append(
                    {
                        "experiment_id": digest(
                            {
                                "protocol": p.hash,
                                "baseline": baseline.name,
                                "nominal_idr": str(nominal),
                            }
                        ),
                        "status": "experiment",
                        "baseline": document(asdict(baseline)),
                        "nominal_idr": str(nominal),
                        "role": "champion" if baseline.name == p.champion else "challenger",
                        "calibration_source": "validation only",
                        "calibration_bins": document(calibration),
                        "metrics": summary,
                        "holdout_breakdown": breakdown,
                        "ranking": {
                            split: [
                                {
                                    "at": stamp,
                                    "candidates": [
                                        {
                                            "case": row["case"],
                                            "rank": position + 1,
                                            "target_reward_idr": row["risk"]["reward_idr"],
                                            "risk_idr": row["risk"]["risk_idr"],
                                            "shares": row["requested"],
                                            "expected_net_idr": None,
                                            "probability": None,
                                            "fill_probability": None,
                                        }
                                        for position, row in enumerate(
                                            rank(
                                                [r for r in rows if r["at"] == stamp],
                                                account=cases[0].spec.account,
                                                nominal=nominal,
                                            )
                                        )
                                    ],
                                }
                                for stamp in sorted({r["at"] for r in rows})
                            ]
                            for split, rows in folds.items()
                        },
                        "walk_forward": [
                            {
                                "split": split,
                                "session": session,
                                "metrics": metrics(
                                    [r for r in folds[split] if r["session"] == session], p
                                ),
                                "calibration_cutoff": p.validation_end.isoformat(),
                                "refit": False,
                            }
                            for split in ("test", "holdout")
                            for session in sorted({r["session"] for r in folds[split]})
                        ],
                        "rows": folds,
                    }
                )
        # Licensed data/portfolio evidence is absent from this boundary. A good
        # closed-plan score alone must never become an automatic research GO.
        report["g1"] = {
            "decision": "no-go",
            "status": "experiment",
            "auto_promotion": False,
            "reasons": [
                "G0 evidence not adjudicated",
                "portfolio risk and independent release approval required",
            ],
            "checks": [gate_checks(e, p) for e in report["experiments"]],
        }
        report["report_hash"] = digest(report)
        return report


def gate_checks(experiment: dict[str, Any], p: Protocol) -> dict[str, Any]:
    h = experiment["metrics"]["holdout"]
    ci = h["expectancy_95_block_ci_idr"]
    brier = h["calibration"]["brier"]
    groups = experiment["holdout_breakdown"]
    diversified = all(
        len(groups[key]) >= 2
        and all(
            group["expectancy_net_idr"] is not None and D(group["expectancy_net_idr"]) > 0
            for group in groups[key].values()
        )
        for key in ("symbol", "session", "regime")
    )
    return {
        "baseline": experiment["baseline"]["name"],
        "nominal_idr": experiment["nominal_idr"],
        "positive_expectancy_ci": ci is not None and D(ci[0]) > 0,
        "risk_budget": D(h["realized_plan_drawdown_idr"]) <= p.max_drawdown_idr,
        "no_failed_exits": h["open_shares"] == 0,
        "calibration": brier is not None
        and D(brier) <= p.maximum_brier
        and h["calibration"]["count"] >= p.minimum_calibration
        and h["calibration"]["coverage"] == "1",
        "diversified": diversified,
    }


def rank(rows: Sequence[dict[str, Any]], *, account: str, nominal: Decimal) -> list[dict[str, Any]]:
    """Rank one isolated scope by conservative net reward per risk IDR.

    No uncalibrated expected-value/fill percentages are invented. The score is
    conditional net target reward / stop risk, with executable shares from SS-015.
    """
    money(nominal)
    if any(r["account"] != account or D(r["nominal_idr"]) != nominal for r in rows):
        raise ValueError("Mixed account or nominal ranking scope")
    candidates = [r for r in rows if r["eligible"] and D(r["risk"]["risk_idr"]) > 0]
    return sorted(
        candidates,
        key=lambda r: (
            -(D(r["risk"]["reward_idr"]) / D(r["risk"]["risk_idr"])),
            -D(r["risk"]["reward_idr"]),
            r["symbol"],
            r["case"],
        ),
    )
