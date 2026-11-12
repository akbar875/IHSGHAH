"""Portability smoke test against the exact same generated JSON/fixtures as JS."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1] / "v1"
schema = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(schema)
examples = json.loads((ROOT / "examples.json").read_text(encoding="utf-8"))
for example in examples:
    validator = Draft202012Validator(
        {**schema, "$ref": f"#/$defs/{example['schema']}"},
        format_checker=FormatChecker(),
    )
    validator.validate(example["payload"])
    if example["schema"] == "FillRequest":
        for field, value in [("price_idr", 1000.1), ("lots", 0.5),
                             ("filled_at", "2026-02-30T03:00:00Z")]:
            assert not validator.is_valid({**example["payload"], field: value}), field
print(f"Python JSON Schema: {len(examples)} fixtures valid; negative cases rejected.")
