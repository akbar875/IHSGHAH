"""Operator-only CLI. Credentials stay in environment, never argv or backup."""

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import cast

from saham_signal.adapters.backup import backup, restore
from saham_signal.adapters.operations import PostgresControl
from saham_signal.application.operations import Action
from saham_signal.config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="SS-025 operator controls")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    control = sub.add_parser("control")
    control.add_argument("action", choices=["pause", "drift", "rollback", "resume"])
    control.add_argument("--expected-revision", type=int, required=True)
    control.add_argument("--release", required=True)
    control.add_argument("--evidence", required=True)
    control.add_argument("--actor", required=True)
    save = sub.add_parser("backup")
    save.add_argument("path", type=Path)
    recover = sub.add_parser("restore")
    recover.add_argument("path", type=Path)
    recover.add_argument("--confirm-empty-target", required=True)
    args = parser.parse_args()
    try:
        config = load_settings()
        dsn, mode = config.database_url.get_secret_value(), config.app_mode
        store = PostgresControl(dsn)
        if args.command == "status":
            result = asdict(store.read(mode))
        elif args.command == "control":
            result = asdict(
                store.write(
                    mode,
                    args.expected_revision,
                    cast(Action, args.action),
                    args.release,
                    args.evidence,
                    args.actor,
                )
            )
        elif args.command == "backup":
            document = backup(dsn, mode)
            # Exclusive creation protects an existing recovery point.
            descriptor = os.open(args.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(document, stream, sort_keys=True)
            result = {"sha256": document["sha256"]}
        else:
            target = os.environ["RESTORE_DATABASE_URL"]
            result = restore(
                target,
                mode,
                json.loads(args.path.read_text(encoding="utf-8")),
                args.confirm_empty_target,
            )
        print(json.dumps(result))
    except Exception:
        raise SystemExit(
            "Operation failed; verify scope, revision, evidence and operator access"
        ) from None


if __name__ == "__main__":
    main()
