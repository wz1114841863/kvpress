#!/usr/bin/env python3
"""A4.3.0 Route-A pre-spec resource-contract/envelope/fallback gate.

This no-model gate records existing evidence boundaries.  It does not select
hardware parameters or turn modeled inputs into hardware measurements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a43-resource-contract-envelope-fallback-1.0"
INPUT_SCHEMAS = {
    "c5": "cross-frontend-c5-hardware-direction-decision-1.0",
    "a4200": "kvzap-route-a4200-observed-resource-contract-1.0",
    "a4201": "kvzap-route-a4201-contract-sensitivity-matrix-1.0",
    "a4211": "kvzap-route-a4211-partitioned-backpressure-sensitivity-2.0",
    "a4214": "kvzap-route-a4214-core-contract-closure-1.0",
    "m6": "kvzap-route-a-m6-cross-model-fixed-horizon-envelope-1.2",
    "a317": "kvzap-route-a317-contract-policy-sweep-1.0",
    "a318": "kvzap-route-a318-contract-breach-1.0",
}
UNRESOLVED_PARAMETERS = (
    "pending_FIFO_depth_and_overflow_policy",
    "page_table_entry_bits_and_allocator_seal_policy",
    "bank_mapping_burst_gather_format",
    "merge_state_precision_and_PE_scheduler_interface",
    "bypass_switch_timing_and_admission_service_rate",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_input(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required input is absent: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != schema:
        raise ValueError(f"invalid {schema} input: {path}")
    if schema not in {INPUT_SCHEMAS["a317"], INPUT_SCHEMAS["a318"]} and data.get("status") != "complete":
        raise ValueError(f"input is not complete: {path}")
    return data


def require_true(data: dict[str, Any], names: tuple[str, ...], label: str) -> None:
    guards = data.get("observational_guards")
    if not isinstance(guards, dict) or any(guards.get(name) is not True for name in names):
        raise ValueError(f"{label} lacks required true guard(s): {names}")


def resource_rows(a4200: dict[str, Any], a4201: dict[str, Any]) -> list[dict[str, Any]]:
    observed = {row["name"]: row for row in a4200["contract"]["unresolved_hardware_contract_parameters"]}
    matrix = {row["parameter"]: row for row in a4201["report"]["matrix"]}
    if set(observed) != set(UNRESOLVED_PARAMETERS):
        raise ValueError("A4200 unresolved parameters differ from the A4.3 contract")
    if set(matrix) != set(UNRESOLVED_PARAMETERS):
        raise ValueError("A4201 parameter mapping differs from the A4.3 contract")
    return [{
        "parameter": name,
        "functional_or_observed_boundary": observed[name]["reason"],
        "status": "unresolved_not_selected",
        "modeled_candidate_axis": matrix[name]["candidate_modeled_range"],
        "next_evidence_needed": matrix[name]["next_binding_needed"],
    } for name in UNRESOLVED_PARAMETERS]


def conditioned_rows(m6: dict[str, Any]) -> list[dict[str, Any]]:
    groups = m6.get("per_model_fixed_workload_descriptors")
    if not isinstance(groups, dict):
        raise ValueError("M6 fixed-workload descriptors are absent")
    rows = [row for values in groups.values() for row in values]
    identities = {(row.get("model_anchor"), row.get("workload")) for row in rows}
    if len(rows) != 6 or len(identities) != 6:
        raise ValueError("M6 must retain exactly six distinct model/workload rows")
    if {anchor for anchor, _ in identities} != {"qwen3_8b_kvzap", "nous_llama31_8b_kvzap"}:
        raise ValueError("M6 model anchors differ from the accepted two-anchor scope")
    if any(row.get("actual_policy_decode_calls") != 7 for row in rows):
        raise ValueError("M6 rows lack the matched seven-call fixed horizon")
    return sorted(rows, key=lambda row: (str(row["model_anchor"]), str(row["workload"])))


def fallback_contract(
    a4200: dict[str, Any], a4201: dict[str, Any], a317: dict[str, Any], a318: dict[str, Any], a317_sha256: str
) -> dict[str, Any]:
    bypass = a4200["contract"]["control_plane_contract"]["full_kv_bypass"]
    if bypass.get("required_behavior") != "No Route-A admission or cold-state ownership is entered when bypass is selected.":
        raise ValueError("A4200 Full-KV bypass is not the required zero-admission control")
    bypass_matrix = next(row for row in a4201["report"]["matrix"] if row["parameter"] == UNRESOLVED_PARAMETERS[-1])
    if "preserve bypass as a true zero-admission control" not in bypass_matrix["next_binding_needed"]:
        raise ValueError("A4201 does not preserve Full-KV bypass as a true control")
    if a317["assumptions"].get("protected_semantic") != "Full KV with zero admission":
        raise ValueError("A317 protected semantic is not Full-KV zero admission")
    if a318.get("breach_workload") not in a317.get("workloads", {}):
        raise ValueError("A318 breach workload is absent from A317")
    if a318["source_sha256"].get("honest_manifest_sha256") != a317_sha256:
        raise ValueError("A318 does not bind the supplied A317 manifest")
    return {
        "required_control": "Full-KV bypass: no Route-A admission or cold-state ownership.",
        "fast_path_condition": "Route-A admission is separately selected; continuation evidence is not an implicit length predictor.",
        "modeled_breach_boundary": {
            "workload": a318["breach_workload"],
            "statement": "A false continuation declaration can incur modeled performance loss without changing semantic safety; this is not hardware timing.",
        },
        "a317_workload_contract_rows": [{
            "workload": name,
            "declared_minimum_continuation_calls": value["declared_minimum_continuation_calls"],
            "observed_decode_model_calls_audit_only": value["observed_decode_model_calls"],
        } for name, value in sorted(a317["workloads"].items())],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.3.0 no-model Route-A resource-contract/workload-envelope/Full-KV-fallback gate; no hardware sizing."
    )
    for name in INPUT_SCHEMAS:
        parser.add_argument(f"--{name.replace('_', '-')}-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    inputs = {name: load_input(getattr(args, f"{name}_report"), schema) for name, schema in INPUT_SCHEMAS.items()}
    c5_gate = inputs["c5"].get("c5_gate")
    if not isinstance(c5_gate, dict) or any(c5_gate.get(name) is not True for name in ("c0_c4_hash_chain_verified", "route_a_primary_direction_evidence_bound")):
        raise ValueError("C5 lacks required completed direction guards")
    if c5_gate.get("rtl_authorized") is not False:
        raise ValueError("C5 unexpectedly authorizes RTL")
    require_true(inputs["a4200"], ("unresolved_hardware_parameters_explicit",), "A4200")
    require_true(inputs["a4201"], ("all_unresolved_contract_parameters_mapped", "no_hardware_parameter_selected"), "A4201")
    require_true(inputs["a4211"], ("no_hardware_parameter_selected", "partition_and_burst_contracts_explicit"), "A4211")
    require_true(inputs["a4214"], ("all_input_hashes_and_required_guards_verified", "no_hardware_parameter_selected"), "A4214")
    require_true(inputs["m6"], ("all_input_hashes_and_required_guards_verified", "qwen_and_llama_rows_kept_separate", "no_hardware_parameter_selected"), "M6")
    rows = conditioned_rows(inputs["m6"])
    resources = resource_rows(inputs["a4200"], inputs["a4201"])
    fallback = fallback_contract(inputs["a4200"], inputs["a4201"], inputs["a317"], inputs["a318"], sha256(args.a317_report))
    config = {name: {"path": str(getattr(args, f"{name}_report")), "sha256": sha256(getattr(args, f"{name}_report"))} for name in INPUT_SCHEMAS}
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "no-model provenance-bound functional/trace-derived and modeled-input ledger; not a measured or modeled hardware result",
        "resource_contract_ledger": resources,
        "conditioned_workload_envelope": {"rows": rows, "row_count": len(rows), "interpretation": "Six fixed-horizon descriptors remain model/workload-separated; normalized variation is not a hardware resource range."},
        "full_kv_fallback_contract": fallback,
        "architecture_spec_gate": {"eligible": False, "reason": "All five resource fields retain candidate/model-only or unresolved status; this gate selects no parameter.", "rtl_authorized": False},
        "observational_guards": {
            "all_input_hashes_and_required_guards_verified": True,
            "six_model_workload_rows_kept_separate": True,
            "full_kv_bypass_zero_admission_control_verified": True,
            "all_resource_parameters_remain_unselected": True,
            "architecture_spec_not_authorized": True,
            "rtl_not_authorized": True,
        },
        "boundaries": [
            "This gate does not choose FIFO/PTE/page/bank/burst/merge precision/PE/scheduler/controller parameters.",
            "M6 rows are fixed-request logical descriptor coverage, not a workload distribution or hardware resource envelope.",
            "A317/A318 are offline modeled policy evidence; neither establishes hardware timing, HBM traffic, latency, throughput, energy, area, or acceleration.",
            "Full-KV bypass is a semantic/control requirement, not a measured controller implementation or timing contract.",
            "Cross-frontend C5 remains a Route-A direction decision only; no common semantic abstraction is promoted to hardware commonality.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a43_resource_contract_envelope_fallback_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.3.0 completed: {output}")


if __name__ == "__main__":
    main()
