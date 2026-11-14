"""Review an internal sealed campaign/journal JSON file; never starts observation."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from saham_signal.application.observation import Campaign, Entry, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--as-of", required=True, type=datetime.fromisoformat)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    if set(data) != {"campaign", "campaign_sha256", "entries"}:
        raise ValueError("Expected sealed campaign and entries")
    campaign = Campaign.model_validate(data["campaign"])
    if campaign.seal() != data["campaign_sha256"]:
        raise ValueError("Campaign seal mismatch")
    entries = TypeAdapter(tuple[Entry, ...]).validate_python(data["entries"])
    print(json.dumps(report(campaign, entries, args.as_of), indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Observation review failed; verify sealed inputs and timestamps") from None
