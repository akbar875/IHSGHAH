"""Reproducible SS-024 ablation evidence, entirely invented and internal."""

import json
from datetime import timedelta
from typing import Any

from saham_signal.adapters.evaluation_simulation import at, fixture
from saham_signal.application.news import (
    Extraction,
    NewsInput,
    NewsRecord,
    SourceGrant,
    content_hash,
)
from saham_signal.application.news_evaluation import NewsProtocol, NewsStudy, news_hash


def simulation() -> dict[str, Any]:
    p, cases, refs, fees = fixture()
    grant = SourceGrant(
        source="invented-official",
        evidence="SIMULATION ONLY, not a vendor license",
        valid_from=at(1) - timedelta(days=1),
        valid_to=at(31) + timedelta(days=1),
        storage=True,
        analysis=True,
        origin="simulation",
        credibility="official",
    )
    records = []
    for i, case in enumerate(cases):
        text = f"SIMULATION ONLY event-{i} {case.spec.symbol}"
        records.append(
            NewsRecord(
                source=grant.source,
                grant=grant,
                document=NewsInput(
                    document_id=f"sim-{i}", revision=1, published_at=case.spec.entry_from, text=text
                ),
                content_hash=content_hash(text),
                received_at=case.spec.entry_from,
                available_at=case.spec.entry_from,
                extraction=Extraction(
                    symbols=(case.spec.symbol,),
                    event="other",
                    summary="",
                    method="deterministic",
                    version="explicit-ticker-v1",
                ),
            )
        )
    result: dict[str, Any] = {
        "label": "SIMULATION ONLY — no measured production benefit",
        "ranking_enabled": False,
        "variants": {},
    }
    for name, dataset in (("absent", ()), ("all_mapped", tuple(records))):
        report = NewsStudy(NewsProtocol(p, news_hash(dataset))).run(
            cases, dataset, refs, fees, evaluated_at=at(31)
        )
        result["variants"][name] = {
            "protocol_hash": report["protocol_hash"],
            "report_hash": report["report_hash"],
            "news_dataset_hash": report["news_dataset_hash"],
            "decision": report["decision"],
            "experiments": [
                {
                    "baseline": e["baseline"],
                    "nominal_idr": e["nominal_idr"],
                    "paired_holdout": e["paired_holdout"],
                    "without_news_expectancy_idr": e["without_news"]["holdout"][
                        "expectancy_net_idr"
                    ],
                    "with_news_expectancy_idr": e["with_news"]["holdout"]["expectancy_net_idr"],
                    "without_news_open_shares": e["without_news"]["holdout"]["open_shares"],
                    "with_news_open_shares": e["with_news"]["holdout"]["open_shares"],
                }
                for e in report["experiments"]
            ],
        }
    return result


if __name__ == "__main__":
    print(json.dumps(simulation(), indent=2, sort_keys=True))
