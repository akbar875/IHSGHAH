"""Import free attributed daily data for local research; never starts live/paper."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from saham_signal.adapters.eod import download_and_import, publish
from saham_signal.application.eod import import_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--download", action="store_true")
    source.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    now = datetime.now(UTC)
    if args.download:
        snapshot = download_and_import(args.output, now)
    else:
        snapshot = import_csv(args.input, now)
        publish(snapshot, args.output)
    print(
        json.dumps(
            {
                "provider": snapshot.provider,
                "source": snapshot.source,
                "license": snapshot.license,
                "source_sha256": snapshot.source_sha256,
                "snapshot_sha256": snapshot.sha256,
                "latest_date": str(snapshot.latest_date),
                "available_at": snapshot.available_at.isoformat(),
                "quality": snapshot.quality,
                "mode": "research",
                "frequency": "daily",
                "signals_enabled": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "EOD import failed; previous snapshot retained; check source and output"
        ) from None
