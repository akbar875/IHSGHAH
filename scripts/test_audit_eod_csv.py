"""Synthetic records only; no downloaded market data in tests."""

import tempfile
import unittest
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location(
    "audit_eod", Path(__file__).with_name("audit-eod-csv.py")
)
assert spec and spec.loader
module = module_from_spec(spec)
spec.loader.exec_module(module)


class AuditTests(unittest.TestCase):
    def run_audit(self, rows):
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parent
        ) as directory:
            path = Path(directory) / "synthetic.csv"
            path.write_text(",".join(module.FIELDS) + "\n" + rows, encoding="utf-8")
            return module.audit(path)

    def test_duplicates_order_and_ohlc_are_reported(self):
        result = self.run_audit(
            "2026-11-13,SYNTH,100,110,90,105,105,0\n"
            "2026-11-12,SYNTH,100,95,90,105,105,100\n"
            "2026-11-12,SYNTH,100,110,90,105,105,100\n"
        )
        self.assertEqual(result["metrics"]["duplicate_symbol_date"], 1)
        self.assertEqual(result["metrics"]["out_of_order_within_symbol"], 1)
        self.assertEqual(result["metrics"]["invalid_ohlc_bounds"], 1)
        self.assertEqual(result["metrics"]["zero_volume"], 1)
        self.assertFalse(result["live_eligible"])
        self.assertEqual(result["g0"], "PENDING")

    def test_nonfinite_missing_and_invalid_dates(self):
        result = self.run_audit(
            "2026-11-13,SYNTH,NaN,110,90,105,105,100\n"
            "2026-11-13,SYNTH,100,110,90,,105,100\n"
            "2026-02-30,SYNTH,100,110,90,105,105,100\n"
            "2026-11-14,SYNTH,-1,110,90,105,105,-2\n"
        )
        for name in [
            "invalid_numeric",
            "missing_or_extra_fields",
            "invalid_date",
            "weekend_rows",
            "nonpositive_price",
            "invalid_volume",
        ]:
            self.assertEqual(result["metrics"][name], 1, name)

    def test_empty_and_wrong_schema_fail(self):
        with self.assertRaises(ValueError):
            self.run_audit("")
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parent
        ) as directory:
            path = Path(directory) / "wrong.csv"
            path.write_text("unexpected\nvalue\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.audit(path)


if __name__ == "__main__":
    unittest.main()
