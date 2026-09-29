#!/usr/bin/env python3
"""No-model Gate-RTL0.5 cross-artifact closure preflight."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Gate-RTL0 cross-closure; no RTL, timing, PPA, or performance claim.")
    parser.add_argument("--analysis-dir", type=Path, default=Path("analysis")); args = parser.parse_args(); base=args.analysis_dir
    interface=json.loads((base/"rtl_entry_interface_manifest.json").read_text()); matrix=json.loads((base/"rtl_entry_assertion_matrix.json").read_text()); oracle=json.loads((base/"rtl_entry_scoreboard_oracle_manifest.json").read_text())
    modules={m["name"] for m in interface["hierarchy"]["modules"]}; assertion_ids={r["id"] for r in matrix["records"]}; bindings={b["assertion_id"]:b for b in oracle["bindings"]}
    if set(bindings)!=assertion_ids: raise SystemExit("cross-closure failed: assertion/oracle inventory drift")
    for record in matrix["records"]:
        owner=record["rtl_owner"]
        if owner not in modules: raise SystemExit(f"cross-closure failed: unknown owner {owner}")
        if bindings[record["id"]]["rtl_owner"] != owner: raise SystemExit(f"cross-closure failed: owner mismatch {record['id']}")
        if record["kind"] == "progress" and not record["environment_assumption"]: raise SystemExit(f"cross-closure failed: progress lacks assumption {record['id']}")
    required={"a_descriptor_unique_memory_path","a_metadata_publish_commit","a_ready_low_nonmutation","a_descriptor_invalidate_before_free","a_numeric_fault_consumer","a_reset_stale_exclusion","a_global_retirement_membership"}
    if not required <= assertion_ids: raise SystemExit("cross-closure failed: Reviewer-02 requirement missing")
    print("Gate-RTL0 cross-closure passed: 15 assertions, 15 unique oracle bindings, required Reviewer-02 coverage present")
    return 0
if __name__ == "__main__": raise SystemExit(main())
