#!/usr/bin/env python3
"""Validate native WCG1 isolation artifacts; timing failure is a result, not PASS."""
import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path


def check(root: Path) -> dict:
    result = {"evidence_class": "one_bank_logic_mapping_propagated_cell_clock_sta_not_top_or_physical_signoff", "sides": {}}
    for side in ("reference", "gated"):
        directory = root / side
        log = (directory / "native.log").read_text(errors="replace")
        assert f"KVZAP_WCG1_SIDE_RUN_PASS side={side}" in log, side
        assert (directory / "exit_status").read_text().strip() == "0", side
        for path in [directory / "native.log", *directory.rglob("*.rpt")]:
            assert not re.search(r"^\s*(?:Error:|Fatal:)", path.read_text(errors="replace"), re.M), path
        result["sides"][side] = {}
        for stage in ("raw", "repaired"):
            dest = directory / stage
            reports = ["area", "references", "qor", "constraints", "clocks", "gating", "setup", "hold", "check_design", "check_timing"]
            if side == "gated":
                reports += ["gate_setup", "gate_hold", "gated_data_hold"]
            for name in [*(f"{v}.rpt" for v in reports), "mapped.v", "mapped.ddc", "mapped.sdc", "metrics.tsv"]:
                assert (dest / name).stat().st_size > 0, dest / name
            rows = list(csv.DictReader((dest / "metrics.tsv").open(), delimiter="\t"))
            m = {r["metric"]: r["value"] for r in rows}
            assert len(rows) == len(m), "duplicate metric"
            assert int(m["data_flops"]) == 10176
            assert int(m["clock_gates"]) == (128 if side == "gated" else 0)
            assert float(m["period_ns"]) == 2 and m["propagated"] == "true", m
            for key in ("total_area", "max_slack_ns", "min_slack_ns") + (("gate_max_slack_ns", "gate_min_slack_ns") if side == "gated" else ()):
                m[key] = float(m[key])
                assert math.isfinite(m[key]), key
            assert m["total_area"] > 0
            assert not re.search(r"\b(?:GTECH_\w+|SEQGEN)\b", (dest / "mapped.v").read_text()), "unmapped logic"
            # DC must show actual propagated cell-clock capture, not an ideal branch.
            if side == "gated":
                hold = (dest / "gated_data_hold.rpt").read_text()
                gate_delays = re.findall(r"\w+_gate_\d+/Q\s+\(CKLNQ\w+\)\s+([-+0-9.eE]+)", hold)
                assert gate_delays and any(float(v) > 0 for v in gate_delays), "missing nonzero gate capture arc"
                assert re.search(r"clock gating setup", (dest / "gate_setup.rpt").read_text(), re.I), "no gating setup check"
                assert re.search(r"clock gating hold", (dest / "gate_hold.rpt").read_text(), re.I), "no gating hold check"
            m["setup_closed"] = m["max_slack_ns"] >= 0
            m["hold_closed"] = m["min_slack_ns"] >= 0
            m["gate_checks_closed"] = side == "reference" or min(m["gate_max_slack_ns"], m["gate_min_slack_ns"]) >= 0
            result["sides"][side][stage] = m
    result["area_change"] = {}
    for stage in ("raw", "repaired"):
        ref, gated = (result["sides"][s][stage] for s in ("reference", "gated"))
        result["area_change"][stage] = {
            "saved_area": ref["total_area"] - gated["total_area"],
            "reduction_percent": 100 * (1 - gated["total_area"] / ref["total_area"]),
            "both_sides_timing_closed": all(m[k] for m in (ref, gated) for k in ("setup_closed", "hold_closed", "gate_checks_closed")),
        }
    result["tool_input_artifact_closure"] = "PASS"
    result["artifact_sha256"] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in (".ddc", ".v", ".sdc", ".rpt", ".tsv")}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    result = check(args.root)
    path = args.root / "result.json"
    assert not path.exists(), "refusing to overwrite result"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print("KVZAP_WCG1_MAPPING_POSTCHECK_PASS")


if __name__ == "__main__":
    main()
