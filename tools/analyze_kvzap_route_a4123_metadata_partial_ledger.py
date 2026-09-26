#!/usr/bin/env python3
"""A4.12.3 metadata-side partial ledger; deliberately no payload net benefit."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a4123-metadata-partial-ledger-1.0"
EXPECTED = {
    "a4112b": ("kvzap-route-a4112b-external-storage-binding-1.0", "57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3"),
    "a4120": ("kvzap-route-a4120-metadata-interface-inventory-1.0", "e5a7ad30b45be7acbda7c2b0b788fdfa4ee74553d6fc93bc9317dce0c4be3534"),
    "a4121": ("kvzap-route-a4121-metadata-macro-envelope-1.0", "d5f0f436251cb607b884e3102788caf2e775e398542686ad9ca88b58a96e3f7d"),
    "a4122": ("kvzap-route-a4122-metadata-cycle-energy-1.0", "e2578b08b852036b500ed9ce8dbba8ea9c55ec45b75a6eea02a3893473feb415"),
}
M1 = "M1_banked_sram_pipelined_rmw"
M2 = "M2_replicated_or_duplicated_control_storage"
M3 = "M3_register_hot_state_with_sram_backing"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.12.3 frozen metadata-cost and logical-benefit partial ledger; not payload traffic, net benefit, PPA, or RTL.")
    p.add_argument("--a4112b-report", type=Path, required=True)
    p.add_argument("--a4120-report", type=Path, required=True)
    p.add_argument("--a4121-report", type=Path, required=True)
    p.add_argument("--a4122-report", type=Path, required=True)
    p.add_argument("--preflight-only", action="store_true", help="Validate exact frozen inputs and ledger boundaries without output.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def read_exact(path: Path, label: str) -> dict[str, Any]:
    schema, digest = EXPECTED[label]
    if not path.is_file() or sha256_file(path) != digest:
        raise ValueError(f"A4.12.3 requires exact accepted {label} SHA-256")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != schema or report.get("status") != "complete":
        raise ValueError(f"{label} is incomplete or schema-incompatible")
    return report


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * q)] if ordered else 0.0


def validate(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    reports = {label: read_exact(getattr(args, f"{label}_report"), label) for label in EXPECTED}
    if reports["a4121"].get("input_artifacts", {}).get("a4120_report_sha256") != EXPECTED["a4120"][1]:
        raise ValueError("A4.12.1 is not bound to A4.12.0")
    a4122_guards = reports["a4122"].get("semantic_guards", {})
    needed = ("ha8_wide_record_granular_and_a410_queue_contract_fixed", "no_global_commit_slot_synthesized_when_a492_ha8_wide_declares_none", "single_commit_boundary_fifo_ownership_and_dependency_release_remain_commit_gated", "m3_register_energy_not_invented")
    if not all(a4122_guards.get(key) is True for key in needed):
        raise ValueError("A4.12.2 correction or boundaries are incomplete")
    a4112_guards = reports["a4112b"].get("semantic_guards", {})
    needed_4112 = ("a4111_external_storage_exact_token_guard_remains_bound", "trace_on_external_storage_is_token_identical_to_trace_off_and_dense", "prefill_armed_external_storage_lifecycle_observed", "fixed_a410_parameters_not_retuned", "unmapped_hardware_fields_not_synthesized")
    if not all(a4112_guards.get(key) is True for key in needed_4112):
        raise ValueError("A4.11.2b software binding guard incomplete")
    return reports


def benefit_rows(a4112b: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for workload in a4112b.get("workloads", []):
        direct = workload["direct_software_observation"]
        kept, dropped = int(direct["matured_kept_tokens"]), int(direct["matured_dropped_tokens"])
        total = kept + dropped
        if total <= 0 or int(direct["logical_admission_service_tokens"]) != kept:
            raise ValueError("A4.11.2b matured lifecycle accounting is inconsistent")
        rows.append({
            "workload": workload["workload"],
            "direct_software_observation": {
                "matured_cold_tokens_total": total,
                "matured_kept_tokens": kept,
                "matured_dropped_tokens": dropped,
                "trace_end_residual_pending_tokens": int(direct["trace_end_residual_pending_tokens"]),
            },
            "logical_capacity_potential": {
                "cold_kv_tokens_removed_at_maturity": dropped,
                "removed_fraction_of_matured_cold_tokens": dropped / total,
                "logical_compression_of_matured_cold_tokens": total / kept if kept else None,
            },
            "logical_attention_work_potential": {
                "future_cold_source_traversal_token_units_avoided_per_one_future_traversal": dropped,
                "future_traversal_count_observed": None,
                "realized_attention_operations_or_traffic": "not_observed",
                "boundary": "A dropped matured cold token can remove one logical source token unit on each later cold-source traversal. A4.11.2b does not observe the number of such traversals, so this is an unamortized potential rather than realized attention work or traffic savings.",
            },
        })
    if {row["workload"] for row in rows} != {"retrieval", "summarization", "reasoning"}:
        raise ValueError("A4.11.2b workload coverage changed")
    return rows


def macro_area_rows(a4121: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {row["name"]: row for row in a4121.get("candidate_rows", [])}
    if set(rows) != {M1, M2, M3}: raise ValueError("A4.12.1 candidate set changed")
    return rows


def cost_rows(a4121: dict[str, Any], a4122: dict[str, Any]) -> list[dict[str, Any]]:
    macro = macro_area_rows(a4121)
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in (M1, M2, M3)}
    for row in a4122.get("candidate_context_rows", []): grouped[str(row["physical_candidate"])].append(row["result"])
    if any(len(rows) != 168 for rows in grouped.values()): raise ValueError("A4.12.2 context coverage is incomplete")
    result=[]
    for name in (M1, M2, M3):
        rows=grouped[name]; drained=sum(bool(row["drained_within_declared_bound"]) for row in rows)
        energy=[float(row["estimated_sram_dynamic_energy_pj_excluding_unestimated_registers"]) for row in rows]
        cycles=[int(row["service_model_cycles_elapsed"]) for row in rows]
        disposition = "rejected_not_all_contexts_drain" if drained != len(rows) else "service_feasible_under_fixed_declared_model"
        completeness = "complete_sram_proxy_only" if name == M2 else "incomplete_register_area_and_energy" if name == M3 else "complete_sram_proxy_only_but_service_rejected"
        result.append({
            "physical_candidate": name,
            "disposition": disposition,
            "metadata_cost_proxy": {
                "a4121_public_cacti_sram_proxy_area_mm2": float(macro[name]["cacti_proxy_macro_area_mm2"]),
                "a4121_register_area_included": bool(macro[name]["register_area_included"]),
                "a4122_contexts_drained": drained,
                "a4122_context_count": len(rows),
                "a4122_service_model_cycles": {"p50": percentile(cycles,.5), "p95": percentile(cycles,.95), "max": max(cycles)},
                "a4122_estimated_sram_dynamic_energy_pj_excluding_unestimated_registers": {"p50": percentile(energy,.5), "p95": percentile(energy,.95), "max": max(energy)},
                "cost_completeness": completeness,
            },
            "comparison_boundary": "These area and per-context metadata estimates come from a distinct fixed trace set from the A4.11.2b software workloads. They cannot be divided into a net benefit, amortized against tokens, or compared as payload/serving energy.",
        })
    return result


def materialize(paths: dict[str, Path], output_dir: Path) -> dict[str, str]:
    inputs = output_dir / "input_artifacts"; inputs.mkdir()
    copies={}
    for label,path in paths.items():
        target=inputs / f"{label}_source.json"; shutil.copyfile(path,target)
        if sha256_file(target) != EXPECTED[label][1]: raise AssertionError("input changed while materializing")
        copies[label]=str(target)
    return copies


def main() -> None:
    args=parse_args(); reports=validate(args)
    if args.preflight_only:
        print("A4.12.3 preflight passed: exact A4.11.2b/A4.12.0/A4.12.1/A4.12.2 bindings and partial-ledger boundaries validated; no output created.")
        return
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    paths={label:getattr(args,f"{label}_report") for label in EXPECTED}
    copies=materialize(paths,args.output_dir)
    config={"stage":"A4.12.3","candidate_disposition_source":"A4.12.2 corrected _02 only","benefit_source":"A4.11.2b prefill-armed external-storage lifecycle only","pairing":"prohibited: software workloads and metadata model contexts are not one-to-one aligned","payload_stage":"A4.13 required before full Route-A ledger"}
    report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"execution_classification":"metadata-side partial ledger joining direct lifecycle logical potential with declared CACTI/service-model metadata costs; not payload traffic, net benefit, PPA, architecture selection, or RTL evidence","config":config,"config_hash":stable_hash(config),"input_artifacts":{label:{"sha256":EXPECTED[label][1],"materialized_copy":copies[label]} for label in EXPECTED},"logical_benefit_rows":benefit_rows(reports["a4112b"]),"metadata_cost_rows":cost_rows(reports["a4121"],reports["a4122"]),"semantic_guards":{"exact_accepted_a4112b_a4120_a4121_a4122_inputs_bound":True,"a4122_corrected_no_global_commit_slot_required":True,"m1_retained_as_rejected_not_hidden":True,"m3_register_cost_remains_unestimated":True,"benefit_and_cost_workloads_not_numerically_paired":True,"logical_attention_potential_not_relabelled_as_realized_traffic_or_compute":True,"no_payload_movement_or_attention_datapath_cost_invented":True,"no_queue_execution_scheduler_pruning_or_admission_variant_introduced":True},"boundaries":["A4.11.2b matured-token accounting is direct software observation; token-to-capacity and one-future-traversal source-unit interpretations are logical potentials only.","A4.12.1 area and A4.12.2 energy/cycle values are metadata-only declared/public-proxy costs. They exclude payload, HBM, attention datapath, register cost where stated, controller logic, timing, and layout.","The cost and benefit sources have distinct workload/context coverage. No benefit-per-area, benefit-per-energy, traffic, speedup, or Route-A net-benefit figure is produced. A4.13 then A4.14 are required."]}
    output=args.output_dir/"a4123_metadata_partial_ledger_report.json"; output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"A4.12.3 complete: {output} sha256={hashlib.sha256(output.read_bytes()).hexdigest()} benefit_rows={len(report['logical_benefit_rows'])} cost_rows={len(report['metadata_cost_rows'])}")


if __name__ == "__main__": main()
