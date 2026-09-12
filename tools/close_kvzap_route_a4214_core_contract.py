"""A4.2.14 Qwen Route-A anchor closure; a hash-bound no-model archive report."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4214-core-contract-closure-1.0"
SCHEMAS = {
    "a4200": "kvzap-route-a4200-observed-resource-contract-1.0",
    "a4201": "kvzap-route-a4201-contract-sensitivity-matrix-1.0",
    "a428": "kvzap-route-a428-matched-horizon-workload-stability-1.0",
    "a4211": "kvzap-route-a4211-partitioned-backpressure-sensitivity-2.0",
    "a4212": "kvzap-route-a4212-dispatch-epoch-evidence-1.0",
    "a4213": "kvzap-route-a4213-same-layer-group-contract-1.0",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.2.14 Qwen Route-A Core Contract closure; no model execution or hardware specification.")
    for name in SCHEMAS:
        parser.add_argument(f"--{name}-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, schema: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != schema or value.get("status") != "complete":
        raise ValueError(f"invalid completed input: {path}")
    return value


def require_guards(data: dict[str, Any], *names: str) -> None:
    guards = data.get("observational_guards", {})
    if any(guards.get(name) is not True for name in names):
        raise ValueError(f"required guard absent: {names}")


def qwen_descriptor(a4200: dict[str, Any], a428: dict[str, Any], a4212: dict[str, Any], a4213: dict[str, Any]) -> dict[str, Any]:
    workloads: dict[str, Any] = {}
    group_widths: set[int] = set()
    for workload, source in a428["per_workload"].items():
        dispatch = a4212["per_workload"][workload]["summary"]
        sharing = a4213["per_workload"][workload]["summary"]
        histogram = sharing["query_heads_per_kv_head_group_histogram"]
        group_widths.update(int(width) for width in histogram)
        workloads[workload] = {
            "actual_policy_decode_calls": source["actual_policy_decode_calls"],
            "logical_attention_events": source["summary"]["event_count"],
            "source_combination_fractions": source["summary"]["source_combination_fractions"],
            "fan_in_fractions": source["summary"]["fan_in_fractions"],
            "packed_page_tail_witness_distribution": source["summary"]["packed_page_witness_distribution"],
            "forward_epoch_count": dispatch["forward_epoch_count"],
            "layer_dispatch_epoch_count": dispatch["layer_dispatch_epoch_count"],
            "query_heads_per_kv_head_group_histogram": histogram,
            "source_dispatch_control_units": {
                "independent": sharing["independent_source_dispatch_control_units_total"],
                "group_shared": sharing["shared_kv_head_group_source_dispatch_control_units_total"],
                "logical_elided": sharing["dispatch_control_units_elided_total"],
            },
            "per_query_state_and_merge_instances": {
                "partial_softmax": sharing["partial_softmax_state_instances_unchanged"],
                "online_merge": sharing["online_merge_instances_unchanged"],
            },
        }
    scope = a4200["contract"]["contract_scope"]
    return {
        "scope": {key: scope[key] for key in ("model", "model_revision", "predictor", "predictor_revision", "threshold", "hot_window_tokens", "page_tokens", "admission_budget_retained_tokens_per_layer_call", "observed_layer_count", "observed_kv_head_count")},
        "workload_descriptor": workloads,
        "qwen_specific_group_width_values": sorted(group_widths),
        "descriptor_interpretation": "These fixed-request values bound only the Qwen3-8B/KVzap anchor; they are neither universal workload ranges nor hardware dimensions.",
    }


def build_contract(a4200: dict[str, Any]) -> dict[str, Any]:
    return {
        "lifecycle": ["Original retain/drop decision is available no later than maturity for the Route-A fast path.", "Hot records remain outside cold storage; mature retained records enter ordered pending staging and may append to sealed packed pages.", "Packed records preserve original positions and append order."],
        "attention": ["Each evaluation has one partial-or-skip decision for hot, pending, and packed.", "One numerically stable online-softmax merge follows those source decisions.", "Same-mask dense attention remains the semantic comparator; Full-KV bypass is a distinct no-admission control."],
        "dependency": ["Cross-layer order is preserved.", "Same-layer/KV-head-group source/page-descriptor control may be shared only when its source snapshot is identical.", "Each distinct query retains its own partial-softmax state and online merge."],
        "data_plane_interfaces": a4200["contract"]["data_plane_interfaces"],
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    inputs = {name: load(getattr(args, f"{name}_report"), schema) for name, schema in SCHEMAS.items()}
    require_guards(inputs["a4200"], "all_layer_all_head_external_storage_semantics_verified", "unresolved_hardware_parameters_explicit")
    require_guards(inputs["a4201"], "all_unresolved_contract_parameters_mapped", "no_hardware_parameter_selected")
    require_guards(inputs["a428"], "all_workloads_a424_event_guards_verified", "all_workloads_semantics_certified", "shared_actual_policy_decode_calls")
    require_guards(inputs["a4211"], "a4212_dispatch_epoch_binding_verified", "no_hardware_parameter_selected")
    require_guards(inputs["a4212"], "reconstructed_forward_epoch_layer_order_verified", "same_kv_head_group_source_snapshot_consistency_verified")
    require_guards(inputs["a4213"], "same_kv_head_group_snapshot_consistency_revalidated", "no_mask_or_attention_semantics_modified")
    if set(inputs["a428"]["per_workload"]) != set(inputs["a4212"]["per_workload"]) or set(inputs["a428"]["per_workload"]) != set(inputs["a4213"]["per_workload"]):
        raise ValueError("workload coverage differs across A428/A4212/A4213")
    for workload, row in inputs["a428"]["per_workload"].items():
        if inputs["a4212"]["per_workload"][workload]["ordered_event_sha256"] != row["logical_event_sha256"] or inputs["a4213"]["per_workload"][workload]["ordered_event_sha256"] != row["logical_event_sha256"]:
            raise ValueError(f"logical-event hash binding mismatch: {workload}")
    config = {name: {"path": str(getattr(args, f"{name}_report")), "sha256": sha256(getattr(args, f"{name}_report"))} for name in SCHEMAS}
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "archive_status": "Qwen3-8B/KVzap Route-A anchor closed; not an architecture specification, hardware parameter freeze, or RTL gate.",
        "route_a_core_contract_v1": build_contract(inputs["a4200"]),
        "qwen3_8b_kvzap_resource_descriptor": qwen_descriptor(inputs["a4200"], inputs["a428"], inputs["a4212"], inputs["a4213"]),
        "modeled_sensitivity_retained_unselected": {"a4211_arrival_contracts": inputs["a4211"]["config"]["arrival_contracts"], "a4211_placements": inputs["a4211"]["config"]["placements"], "a4201_unresolved_parameters": [row["parameter"] for row in inputs["a4201"]["report"]["matrix"]]},
        "portability_boundary": {
            "semantic_portability_preconditions": ["Decision is stable by maturity and does not revive or invalidate mature records.", "The algorithm can expose retained K/V, original positions, and a same-mask dense semantic comparator.", "The model can expose layer/KV-head/query-head mapping and a traceable attention dispatch order."],
            "not_established": ["Cross-model or cross-algorithm semantic portability.", "Universal source, page, fan-in, GQA-group, pending, or dispatch-control distribution.", "FIFO/PTE/bank/burst/merge precision/PE/scheduler/controller timing selection.", "HBM traffic, latency, throughput, energy, area, acceleration, architecture specification, or RTL readiness."],
            "next_scope": "A second supported KVzap model should run M0-M3 portability gates; a non-KVzap method enters only after satisfying the listed lifecycle preconditions.",
        },
        "observational_guards": {"all_input_hashes_and_required_guards_verified": True, "three_workload_qwen_descriptor_coverage_verified": True, "core_contract_separates_portable_from_qwen_specific_fields": True, "no_hardware_parameter_selected": True},
        "boundaries": ["This closure archives the current Qwen3-8B/KVzap evidence anchor. It does not convert source accounting, Python-reference observations, or virtual A4211 sensitivity into hardware measurements or specifications.", "A4.2.11 modeled rows remain sensitivity evidence only; the closure deliberately selects no placement, buffer, reducer, or service parameter."],
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a4214_core_contract_closure_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.14 completed: {path}")


if __name__ == "__main__":
    main()
