"""Build fail-closed PRD-14 receipts from actual pytest and Playwright results.

This is synthetic component/browser qualification, not a vendor-connected E2E run
or a G0/G1/G2 decision. Missing, skipped, flaky or failed evidence blocks the check.
"""

import argparse
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

BACKEND = {
    1: ["test_disconnect_warns_without_generating_exit_and_retry_failed_sink"],
    2: ["test_quiet_stock_with_healthy_heartbeats_keeps_old_trade_age"],
    3: ["test_exact_fee_cash_risk_and_liquidity_boundaries"],
    4: ["test_ara_no_sellers_never_fills"],
    5: ["test_arb_no_buyers_keeps_position_open"],
    6: ["test_late_availability_mapping_and_untrusted_text"],
    7: ["test_gap_stale_snapshot_and_reconnect_require_new_snapshot"],
    8: ["test_actual_quantity_partial_exit_stop_and_close"],
    9: ["test_cache_isolation_copy_bounds_and_expiry"],
    10: ["test_numeric_features_and_pressure_are_distinct_from_book"],
    11: [
        "test_durable_races_restart_scope_and_immutability",
        "test_postgres_paper_receipt_retry_rls_immutability_and_restore",
        "test_feed_baseline_risk_execution_report_is_deterministic_and_separate",
    ],
    12: [],
}
WEB = {
    11: ["paper report separates simulation and actual fills at 360px"],
    7: ["full snapshot replacement removes old levels, failed refresh clears book"],
    9: ["validated synthetic projection renders coverage bands and expires without a refetch"],
    12: ["touch viewport keeps plan above book and no horizontal overflow"],
}


def receipt(
    backend: Path, browser: Path, revision: str, *, worktree_dirty: bool = False
) -> dict[str, Any]:
    junit = ET.fromstring(backend.read_text(encoding="utf-8"))
    results: dict[str, list[bool]] = {}
    for case in junit.iter("testcase"):
        name = case.attrib.get("name", "")
        passed = not any(case.find(kind) is not None for kind in ("failure", "error", "skipped"))
        results.setdefault(name, []).append(passed)
    web = json.loads(browser.read_text(encoding="utf-8"))
    web_results: dict[str, list[bool]] = {}

    def visit(suite: dict[str, Any]) -> None:
        for spec in suite.get("specs", []):
            tests = spec.get("tests", [])
            passed = bool(tests) and all(
                t.get("status") == "expected"
                and bool(t.get("results"))
                and all(r.get("status") == "passed" for r in t["results"])
                for t in tests
            )
            web_results.setdefault(spec["title"], []).append(passed)
        for child in suite.get("suites", []):
            visit(child)

    visit(web)
    scenarios = []
    for number, names in BACKEND.items():
        evidence = []
        for source, required, actual in (
            ("pytest", names, results),
            ("playwright", WEB.get(number, []), web_results),
        ):
            for name in required:
                matches = actual.get(name, [])
                evidence.append(
                    {
                        "source": source,
                        "test": name,
                        "status": "passed" if matches and all(matches) else "blocked",
                    }
                )
        scenarios.append(
            {
                "scenario": number,
                "evidence": evidence,
                "status": "passed"
                if evidence and all(e["status"] == "passed" for e in evidence)
                else "blocked",
            }
        )
    # A crash/failure elsewhere must never be hidden by a selected passing test.
    suite_failed = any(
        int(s.attrib.get(k, 0)) for s in junit.iter("testsuite") for k in ("failures", "errors")
    ) or bool(web.get("errors"))
    suite_failed |= any(not all(values) for values in web_results.values())
    body = {
        "format": "SS-026-acceptance-v1",
        "revision": revision,
        "revision_kind": "worktree-base" if worktree_dirty else "commit",
        "origin": "simulation",
        "scope": "component-and-browser; no licensed-feed E2E",
        "evidence_hashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (backend, browser)
        },
        "scenarios": scenarios,
        "acceptance_passed": not suite_failed and all(s["status"] == "passed" for s in scenarios),
        "paper_live_enabled": False,
        "g0": "pending",
        "g1": "no-go",
        "g2": "not-started",
        "tolerances": {
            "validation_ref": None,
            "maximum_brier": None,
            "maximum_fill_rate_error": None,
            "maximum_drawdown_idr": None,
        },
        "observation_plan": {
            "minimum_sessions": 60,
            "minimum_eligible_trades": 300,
            "rule": "both minima; review effective sample dependence",
            "synthetic_runs_count_toward_g2": False,
        },
    }
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return {**body, "sha256": fingerprint}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend", type=Path)
    parser.add_argument("browser", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    report = receipt(args.backend, args.browser, revision, worktree_dirty=dirty)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for scenario in report["scenarios"]:
        print(f"PRD 14.{scenario['scenario']}: {scenario['status']}")
    if not report["acceptance_passed"]:
        raise SystemExit("Critical acceptance missing or failed; progression blocked")
    print("Synthetic qualification passed; paper live/G2 remain blocked")


if __name__ == "__main__":
    main()
