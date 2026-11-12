#!/usr/bin/env python3
"""Check recorded A4.14.1 availability and optionally the saved ledger data."""

from __future__ import annotations

import argparse
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/synthesis_eligibility_manifest.json"
REPORT = (
    ROOT / "analysis/experiments/route_a4141_accounted_net_benefit_ledger_01"
    / "a4141_accounted_net_benefit_ledger_report.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-local-artifacts", action="store_true",
        help="Read the saved ledger and its direct JSON inputs; check schema and accounting totals.",
    )
    args = parser.parse_args()
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    recovery = data["a4141_local_provenance_recovery"]
    assert recovery["status"] == "complete_read_only_recovery_and_preflight"
    assert recovery["recovered_artifact_count"] > 0
    if not args.require_local_artifacts:
        print("PASS: recorded A4.14.1 recovery status is readable")
        return 0

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["schema_version"] == "kvzap-route-a4141-accounted-net-benefit-ledger-1.0"
    assert report["status"] == "complete"
    assert {row["workload"] for row in report["workload_rows"]} == {
        "retrieval", "summarization", "reasoning",
    }
    for artifact in report["input_artifacts"].values():
        source = json.loads((ROOT / artifact["materialized_copy"]).read_text(encoding="utf-8"))
        assert source["status"] == "complete"
    for row in report["workload_rows"]:
        for profile in row["profile_rows"]:
            hbm = profile["payload_hbm"]
            assert hbm["full_fair_bytes"] > 0
            assert hbm["route_total_bytes_including_p3"] == (
                hbm["route_attention_bytes"] + hbm["route_p3_admission_bytes"]
            )
            assert isclose(
                hbm["route_over_full_byte_ratio"],
                hbm["route_total_bytes_including_p3"] / hbm["full_fair_bytes"],
            )
            energy = profile["dynamic_energy"]
            assert isclose(
                energy["differential_omitted_cost_budget_pj_per_request"],
                energy["full_accounted_dynamic_energy_pj"] - energy["route_accounted_dynamic_energy_pj"],
            )
    print("PASS: saved A4.14.1 ledger and direct inputs are readable; byte and energy totals agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
