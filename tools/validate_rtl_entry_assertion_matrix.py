#!/usr/bin/env python3
"""Validate the no-model Gate-RTL0.3 assertion planning matrix."""
from __future__ import annotations
import argparse, json
from pathlib import Path

REQUIRED = {"contract_invariant", "rtl_owner", "sva_property", "directed_test", "random_scenario", "environment_assumption", "coverage_bin"}
EXPECTED = {"a_descriptor_unique_memory_path", "a_metadata_publish_commit", "a_ready_low_nonmutation", "a_descriptor_invalidate_before_free", "a_numeric_fault_consumer", "a_reset_stale_exclusion", "a_global_retirement_membership", "a_authority_conservation", "a_fifo_credit_losslessness", "a_gqa_release", "a_stale_response", "a_exactly_one_terminal", "p_accepted_to_terminal", "p_retire_to_ack", "p_credit_return"}

def validate(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "kvzap-route-a-rtl-entry-assertion-matrix-1.0": raise ValueError("unexpected schema_version")
    if set(data.get("required_columns", [])) != REQUIRED: raise ValueError("required_columns drift")
    records = data.get("records", [])
    ids = {record.get("id") for record in records}
    if ids != EXPECTED or len(ids) != len(records): raise ValueError("record inventory drift")
    for record in records:
        if not REQUIRED <= set(record): raise ValueError(f"missing matrix columns: {record.get('id')}")
        if record["kind"] not in {"safety", "progress"}: raise ValueError(f"unknown kind: {record['id']}")
        if record["kind"] == "progress" and not record["environment_assumption"]: raise ValueError(f"progress lacks assumption: {record['id']}")

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Gate-RTL0.3 assertion planning only; no RTL, timing, or PPA claim.")
    parser.add_argument("--matrix", type=Path, default=Path("analysis/rtl_entry_assertion_matrix.json"))
    args = parser.parse_args()
    try: validate(args.matrix)
    except (OSError, ValueError, json.JSONDecodeError) as error: raise SystemExit(f"assertion matrix validation failed: {error}") from error
    print(f"Gate-RTL0 assertion matrix passed: {args.matrix}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
