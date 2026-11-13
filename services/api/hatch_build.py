"""Bundle the canonical wire contract, also when building a wheel from an sdist."""

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        root = Path(self.root)
        source = root.parent.parent / "packages/contracts/v1/schema.json"
        target = root / "src/saham_signal/storage_contract.json"
        if source.is_file():
            target.write_bytes(source.read_bytes())
        elif not target.is_file():
            raise RuntimeError("Canonical storage contract missing from source distribution")
        build_data.setdefault("artifacts", []).append("src/saham_signal/storage_contract.json")
