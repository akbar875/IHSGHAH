"""Import trusted operator evidence; print status/check admission. No live-start command."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from saham_signal.adapters.paper_evidence import PostgresPaperEvidence
from saham_signal.application.acceptance import require_admission
from saham_signal.config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["import", "status", "check-admission"])
    parser.add_argument("--kind", choices=["acceptance", "protocol", "G0", "G1"])
    parser.add_argument("--file", type=Path)
    parser.add_argument("--backend", type=Path)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--actor")
    parser.add_argument("--expected-cursor", type=int)
    args = parser.parse_args()
    config = load_settings()
    if config.app_mode != "paper" or not config.pilot_account_id:
        raise ValueError("Isolated paper configuration/account required")
    store = PostgresPaperEvidence(config.database_url.get_secret_value(), config.pilot_account_id)
    if args.action == "import":
        if not args.kind or not args.file or not args.actor or args.expected_cursor is None:
            raise ValueError("Kind, file, actor and expected cursor required")
        if args.file.stat().st_size > 1048576:
            raise ValueError("Evidence exceeds 1 MiB")
        payload = json.loads(args.file.read_text(encoding="utf-8-sig"))
        if args.kind == "acceptance":
            if not args.backend or not args.browser:
                raise ValueError("Original backend/browser result files required")
            for file in (args.backend, args.browser):
                if (
                    payload.get("evidence_hashes", {}).get(file.name)
                    != hashlib.sha256(file.read_bytes()).hexdigest()
                ):
                    raise ValueError("Source result hash mismatch")
        cursor = store.record(args.kind, payload, args.expected_cursor, args.actor)
        print(json.dumps({"kind": args.kind, "cursor": cursor}))
    else:
        report = store.report(config.paper_release_sha, datetime.now(UTC), paused=False)
        print(json.dumps(report, indent=2))
        if args.action == "check-admission":
            require_admission(report["acceptance"])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Paper evidence action failed or admission blocked; review operator inputs"
        ) from None
