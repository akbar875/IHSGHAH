"""Frozen paired news ablation around SS-016 deterministic baseline/replay."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from decimal import Context, Decimal, localcontext
from random import Random
from typing import Any

from saham_signal.application.evaluation import (
    Case,
    Protocol,
    Study,
    document,
    execute,
    metrics,
)
from saham_signal.application.instruments import ReferenceRepository
from saham_signal.application.news import NewsRecord, event_count
from saham_signal.application.replay import FeeSchedule
from saham_signal.domain.persistence import digest


def news_hash(records: Sequence[NewsRecord]) -> str:
    return digest(
        {
            "news": sorted(
                (r.model_dump(mode="json") for r in records),
                key=lambda r: (
                    r["source"],
                    r["document"]["document_id"],
                    r["document"]["revision"],
                ),
            )
        }
    )


@dataclass(frozen=True)
class NewsProtocol:
    baseline: Protocol
    news_dataset_hash: str
    window: timedelta = timedelta(days=1)
    rule: str = "require-verified-mapped-event-v1"

    def __post_init__(self) -> None:
        if (
            self.window <= timedelta(0)
            or self.rule != "require-verified-mapped-event-v1"
            or len(self.news_dataset_hash) != 64
            or any(c not in "0123456789abcdef" for c in self.news_dataset_hash)
        ):
            raise ValueError("Invalid frozen news protocol")

    @property
    def hash(self) -> str:
        return digest(document(asdict(self)))


class FrozenNews:
    def __init__(self, records: Sequence[NewsRecord]) -> None:
        self.records = tuple(records)

    def as_of(self, at: datetime) -> Sequence[NewsRecord]:
        return tuple(r for r in self.records if r.available_at <= at)


class NewsStudy:
    """Persist the protocol and one-use receipt as for SS-016 before unlocking.

    A fixed news gate can only suppress baseline entries. It cannot create an
    entry from sentiment or modify deterministic prices, sizing, fees or fills.
    """

    def __init__(self, protocol: NewsProtocol) -> None:
        self.protocol = protocol
        self.baseline = Study(protocol.baseline)

    def run(
        self,
        cases: Sequence[Case],
        records: Sequence[NewsRecord],
        references: ReferenceRepository,
        fees: Sequence[FeeSchedule],
        *,
        evaluated_at: datetime,
    ) -> dict[str, Any]:
        p = self.protocol
        if news_hash(records) != p.news_dataset_hash:
            raise ValueError("News dataset differs from frozen manifest")
        # Study validates split/purge/embargo, market/fee hashes and burns receipt.
        base = self.baseline.run(cases, references, fees, evaluated_at=evaluated_at)
        store = FrozenNews(records)
        experiments = []
        with localcontext(Context(prec=60)):
            for experiment in base["experiments"]:
                baseline = next(
                    b for b in p.baseline.baselines if b.name == experiment["baseline"]["name"]
                )
                nominal = Decimal(experiment["nominal_idr"])
                filtered: dict[str, list[dict[str, Any]]] = {
                    split: [] for split in ("train", "validation", "test", "holdout")
                }
                for case in sorted(cases, key=lambda c: (c.spec.entry_from, c.id)):
                    split = p.baseline.split(case)
                    if split is None:
                        continue
                    count = event_count(
                        store, case.spec.symbol, case.spec.entry_from, window=p.window
                    )
                    gated = replace(
                        case,
                        inputs=replace(
                            case.inputs, trigger_met=case.inputs.trigger_met and count > 0
                        ),
                    )
                    row = execute(gated, baseline, nominal, p.baseline, references, fees)
                    row["news_count"] = count
                    filtered[split].append(row)
                paired = paired_delta(
                    experiment["rows"]["holdout"], filtered["holdout"], p.baseline
                )
                experiments.append(
                    {
                        "baseline": baseline.name,
                        "nominal_idr": str(nominal),
                        "without_news": experiment["metrics"],
                        "with_news": {
                            split: metrics(rows, p.baseline) for split, rows in filtered.items()
                        },
                        "paired_holdout": paired,
                        "rows": filtered,
                    }
                )
        report = {
            "version": "SS-024-v1",
            "mode": "research",
            "status": "experiment",
            "execution_origin": "simulation",
            "data_origins": sorted({r.grant.origin for r in records}),
            "protocol_hash": p.hash,
            "news_dataset_hash": p.news_dataset_hash,
            "baseline_report_hash": base["report_hash"],
            "evaluated_at": evaluated_at.isoformat(),
            "experiments": experiments,
            "ranking_enabled": False,
            "auto_promotion": False,
            "decision": "disabled_pending_licensed_oos_and_independent_review",
            "limitations": [
                "fixed gate ablation, no sentiment-driven entry or fitted news model",
                "paired session bootstrap includes zero for suppressed plans",
                "unclosed positions censor the comparison; no invented exit profit",
                "no production source, G0/G1 and prospective G2/G3 remain pending",
            ],
        }
        report["report_hash"] = digest(report)
        return report


def paired_delta(
    baseline: Sequence[dict[str, Any]], news: Sequence[dict[str, Any]], p: Protocol
) -> dict[str, Any]:
    """Compare same opportunities after identical replay costs, by session blocks."""
    if [r["case"] for r in baseline] != [r["case"] for r in news]:
        raise ValueError("Paired cases differ")
    if any(r["open"] for r in (*baseline, *news)):
        return {
            "mean_net_delta_idr": None,
            "ci95_idr": None,
            "measurable_benefit": False,
            "reason": "unclosed_positions",
        }
    sessions: dict[str, list[Decimal]] = {}
    for before, after in zip(baseline, news, strict=True):
        sessions.setdefault(before["session"], []).append(
            Decimal(after["net_idr"]) - Decimal(before["net_idr"])
        )
    groups = [sessions[s] for s in sorted(sessions)]
    values = [v for group in groups for v in group]
    interval = None
    block = p.bootstrap_block_sessions
    if len(groups) >= max(p.minimum_sessions, 2 * block):
        rng = Random(p.seed)
        samples = []
        for _ in range(p.bootstrap_samples):
            selected: list[list[Decimal]] = []
            while len(selected) < len(groups):
                start = rng.randrange(len(groups) - block + 1)
                selected.extend(groups[start : start + block])
            draw = [v for group in selected[: len(groups)] for v in group]
            samples.append(sum(draw, Decimal(0)) / len(draw))
        samples.sort()
        interval = [str(samples[int(len(samples) * q)]) for q in (0.025, 0.975)]
    return {
        "opportunities": len(values),
        "sessions": len(groups),
        "mean_net_delta_idr": str(sum(values, Decimal(0)) / len(values)) if values else None,
        "ci95_idr": interval,
        "measurable_benefit": interval is not None and Decimal(interval[0]) > 0,
        "reason": "research_only_no_promotion",
    }
