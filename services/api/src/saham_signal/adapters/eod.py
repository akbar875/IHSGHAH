"""Explicit fixed-origin download and atomic local publication. No automatic polling."""

import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic
from typing import Any
from urllib.request import HTTPRedirectHandler, Request, build_opener

from saham_signal.application.eod import DOWNLOAD, MAX_SOURCE_BYTES, Snapshot, import_csv


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Request | None:
        return None


def publish(snapshot: Snapshot, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, prefix="eod-", suffix=".tmp", delete=False
        ) as target:
            temporary = Path(target.name)
            target.write(snapshot.model_dump_json(indent=2) + "\n")
            target.flush()
            os.fsync(target.fileno())
        temporary.replace(output)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def download_and_import(output: Path, available_at: datetime) -> Snapshot:
    """No URL/configurable destination upstream, auth, redirects, subscriptions or retries."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        request = Request(DOWNLOAD, headers={"User-Agent": "Saham-Signal-research/1.0"})
        deadline = monotonic() + 90
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_SOURCE_BYTES:
                raise ValueError("Source exceeds size limit")
            with NamedTemporaryFile(
                "wb", dir=output.parent, prefix="eod-source-", suffix=".csv", delete=False
            ) as target:
                temporary = Path(target.name)
                size = 0
                while block := response.read(65536):
                    if monotonic() > deadline:
                        raise ValueError("Source download exceeded time budget")
                    size += len(block)
                    if size > MAX_SOURCE_BYTES:
                        raise ValueError("Source exceeds size limit")
                    target.write(block)
        # This is observed availability of the whole snapshot, never historical availability.
        snapshot = import_csv(temporary, max(available_at, datetime.now(UTC)))
        publish(snapshot, output)
        return snapshot
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
