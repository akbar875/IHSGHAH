"""Explicit isolated operator job: one bounded plaintext envelope on stdin.

No startup hooks, fetch, URLs, model calls, or market credentials. Registry is
operator-owned local configuration. The dedicated news role needs only INSERT/
SELECT on internal_news and USAGE on its sequence, never personal/market tables.
"""

import os
import sys
from pathlib import Path

from pydantic import Field

from saham_signal.adapters.news import NewsRepository
from saham_signal.application.news import (
    Extraction,
    InternalModel,
    NewsIngestor,
    NewsInput,
    SourceGrant,
)


class Registry(InternalModel):
    grants: tuple[SourceGrant, ...] = Field(max_length=100)
    symbols: frozenset[str] = Field(max_length=1000)


class Envelope(InternalModel):
    source: str = Field(min_length=1, max_length=128)
    document: NewsInput
    extraction: Extraction | None = None


def main() -> None:
    try:
        if len(sys.argv) != 2:
            raise ValueError("Expected operator registry file")
        registry_bytes = Path(sys.argv[1]).read_bytes()
        if len(registry_bytes) > 128000:
            raise ValueError("Oversized registry")
        registry = Registry.model_validate_json(registry_bytes)
        payload = sys.stdin.buffer.read(70001)
        if len(payload) > 70000:
            raise ValueError("Oversized news envelope")
        envelope = Envelope.model_validate_json(payload)
        dsn = os.environ["NEWS_DATABASE_URL"]
        ingestor = NewsIngestor(NewsRepository(dsn), registry.grants, registry.symbols)
        ingestor.ingest(envelope.source, envelope.document, envelope.extraction)
        print("Internal news committed")
    except Exception:
        raise SystemExit("Internal news rejected; inspect operator configuration") from None


if __name__ == "__main__":
    main()
