"""Explicit operator CLI; no runtime route, training scheduler or promotion."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from saham_signal.application.daily_study import consume, fingerprint, load, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    identity = {
        "protocol_sha256": fingerprint(args.protocol),
        "source_sha256": fingerprint(args.input),
        "code_sha256": fingerprint(Path(__file__).with_name("application") / "daily_study.py"),
        "started_at": datetime.now(UTC).isoformat(),
        "status": "consumed-before-evaluation",
    }
    if identity["source_sha256"] != protocol["source_sha256"]:
        parser.error("Source differs from frozen protocol")
    consume(args.receipt, identity)
    panel, quality = load(args.input)
    result = run(panel, protocol)
    report = {**identity, "status": "completed", "quality": quality, **result}
    # Decision rows are research exposures, never actual/paper fills. Keep them local.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "g1": result["g1"]}, indent=2))


if __name__ == "__main__":
    main()
