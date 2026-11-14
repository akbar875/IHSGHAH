"""Operator offline qualification: stdout report, optional isolated paper persistence."""

import argparse
import json

from saham_signal.adapters.paper import PostgresPaper
from saham_signal.adapters.paper_simulation import run
from saham_signal.config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    report = run()
    if args.persist:
        config = load_settings()
        if config.app_mode != "paper" or not config.pilot_account_id:
            raise ValueError("Persistence requires isolated APP_MODE=paper configuration")
        # The fixture owns its account; never relabel a receipt to another owner.
        if config.pilot_account_id != report["account"]:
            raise ValueError("PILOT_ACCOUNT_ID must match the synthetic fixture account")
        PostgresPaper(config.database_url.get_secret_value(), config.pilot_account_id).append(
            report
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper qualification failed; check configuration and inputs") from None
