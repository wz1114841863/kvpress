#!/usr/bin/env python3
"""A4.14.0 workload-aligned M2 metadata binding; declared model only."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kvpress.route_a_replay import REPLAY_SOURCE_SCHEMA, load_replay_events, sha256_file
from tools.analyze_kvzap_route_a4721_metadata_physical_dse import bank_index
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.simulate_kvzap_route_a410_queue_contract import LOCAL_CAPACITY, SHARED_CAPACITY, STAGING_CAPACITY
from tools.simulate_kvzap_route_a4122_metadata_cycle_energy import macro_metrics, replay
from tools.simulate_kvzap_route_a492_record_granular_engine import MicroOp
from tools.analyze_kvzap_route_a480_commit_aware_backlog import ScheduledTransaction
from tools.validate_kvzap_route_a4112b_external_storage_binding import (
    MANIFEST_SCHEMA,
    PAGE_TOKENS,
    WINDOW,
    expected_heads,
    mature_positions,
    read_events,
    validate_event_rows,
)


SCHEMA = "kvzap-route-a4140-workload-aligned-metadata-cost-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")
M2 = "M2_replicated_or_duplicated_control_storage"
POST_TRACE_DRAIN_LIMIT = 4096
EXPECTED = {
    "a4112b": ("kvzap-route-a4112b-external-storage-binding-1.0", "57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3"),
    "a4120": ("kvzap-route-a4120-metadata-interface-inventory-1.0", "e5a7ad30b45be7acbda7c2b0b788fdfa4ee74553d6fc93bc9317dce0c4be3534"),
    "a4121": ("kvzap-route-a4121-metadata-macro-envelope-1.0", "d5f0f436251cb607b884e3102788caf2e775e398542686ad9ca88b58a96e3f7d"),
    "a4122": ("kvzap-route-a4122-metadata-cycle-energy-1.0", "e2578b08b852036b500ed9ce8dbba8ea9c55ec45b75a6eea02a3893473feb415"),
    "a410": ("kvzap-route-a410-queue-staging-credit-contract-1.0", "97f9cec11c8ffff95ce8405d303f35ddf76ea2c4078512f0d98d38e6ec0ec9e4"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.14.0 fixed-Qwen lifecycle to M2 metadata binding; declared replay and CACTI proxy only, not hardware timing, PPA, architecture, or RTL.")
    for label in EXPECTED:
        parser.add_argument(f"--{label.replace('_', '-')}-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate exact inputs and reconstructability without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_exact(path: Path, label: str) -> dict[str, Any]:
    schema, digest = EXPECTED[label]
    if not path.is_file() or sha256_file(path) != digest:
        raise ValueError(f"A4.14.0 requires exact accepted {label} SHA-256 input")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != schema or report.get("status") != "complete":
        raise ValueError(f"{label} is incomplete or schema-incompatible")
    return report


def fixed_ha8(a410: dict[str, Any]) -> dict[str, Any]:
    config = a410.get("config", {})
    if (config.get("fixed_execution"), config.get("local_capacity_per_bank"), config.get("shared_capacity_per_layer"), config.get("staging_capacity_per_layer")) != ("A4.9.2 record-granular only", LOCAL_CAPACITY, SHARED_CAPACITY, STAGING_CAPACITY):
        raise ValueError("A4.10 fixed queue/execution contract changed")
    rows = [row.get("candidate") for row in a410.get("candidate_context_rows", []) if row.get("candidate", {}).get("name") == "ha8_wide"]
    expected = {"name": "ha8_wide", "banks": 8, "mapping": "head_affine_v1", "read_ports": 2, "write_ports": 2, "rmw_lanes": 2, "queue_groups_per_bank": 32, "commit_slots": 0}
    if not rows or any(candidate != expected for candidate in rows):
        raise ValueError("A4.10 exact HA8-wide catalog is absent or changed")
    return expected


def validate_reports(args: argparse.Namespace) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, dict[str, float]]]:
    reports = {label: read_exact(getattr(args, f"{label}_report"), label) for label in EXPECTED}
    if reports["a4121"].get("input_artifacts", {}).get("a4120_report_sha256") != EXPECTED["a4120"][1]:
        raise ValueError("A4.12.1 does not bind A4.12.0")
    if reports["a4122"].get("input_artifacts", {}).get("a4120_report_sha256") != EXPECTED["a4120"][1] or reports["a4122"].get("input_artifacts", {}).get("a410_report_sha256") != EXPECTED["a410"][1]:
        raise ValueError("A4.12.2 binding chain is incomplete")
    needed_411 = ("a4111_external_storage_exact_token_guard_remains_bound", "trace_on_external_storage_is_token_identical_to_trace_off_and_dense", "prefill_armed_external_storage_lifecycle_observed", "fixed_a410_parameters_not_retuned", "unmapped_hardware_fields_not_synthesized")
    if not all(reports["a4112b"].get("semantic_guards", {}).get(key) is True for key in needed_411):
        raise ValueError("A4.11.2b external-storage guard chain is incomplete")
    needed_4122 = ("ha8_wide_record_granular_and_a410_queue_contract_fixed", "single_commit_boundary_fifo_ownership_and_dependency_release_remain_commit_gated", "no_global_commit_slot_synthesized_when_a492_ha8_wide_declares_none", "m3_register_energy_not_invented")
    if not all(reports["a4122"].get("semantic_guards", {}).get(key) is True for key in needed_4122):
        raise ValueError("A4.12.2 corrected metadata service guards are incomplete")
    candidate = fixed_ha8(reports["a410"])
    macros = macro_metrics(reports["a4121"])
    if {"replicated_head_control", "span_owner_primary"} - set(macros):
        raise ValueError("M2 CACTI access metrics are absent")
    return reports, candidate, macros


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not a JSON object")
    return value


def replay_source(manifest: dict[str, Any]) -> dict[int, dict[tuple[int, int], tuple[bool, float]]]:
    config = manifest.get("config", {})
    required = ("model_name", "model_revision", "predictor_name", "predictor_revision", "threshold", "window_size", "page_tokens", "context_repetitions", "max_new_tokens", "seed")
    if any(name not in config for name in required):
        raise ValueError("lifecycle manifest lacks fixed replay configuration")
    if (config.get("window_size"), config.get("page_tokens"), config.get("admission_budget")) != (WINDOW, PAGE_TOKENS, 512):
        raise ValueError("lifecycle manifest differs from the frozen external-storage setup")
    source_dir = Path(manifest.get("replay_source", {}).get("directory", ""))
    source = read_json(source_dir / "a41_replay_mask_source_manifest.json", "replay source manifest")
    if source.get("schema_version") != REPLAY_SOURCE_SCHEMA or source.get("status") != "complete":
        raise ValueError("replay source is incomplete or schema-incompatible")
    event_path = source_dir / str(source.get("event_file", ""))
    if sha256_file(event_path) != source.get("event_file_sha256"):
        raise ValueError("replay event source SHA-256 mismatch")
    events = load_replay_events(event_path)
    if set(events) != set(range(36)) or sum(len(rows) for rows in events.values()) != source.get("event_count"):
        raise ValueError("replay source layer/event coverage changed")
    return events


def reconstruct_transactions(events: list[dict[str, Any]], replay_events: dict[int, dict[tuple[int, int], tuple[bool, float]]], candidate: dict[str, Any]) -> tuple[list[ScheduledTransaction], dict[int, tuple[MicroOp, ...]]]:
    previous_by_head: dict[tuple[int, int], int] = {}
    transactions: list[ScheduledTransaction] = []
    members: dict[int, tuple[MicroOp, ...]] = {}
    for event in events:
        layer, ordinal = int(event["layer"]), int(event["logical_transition_sequence"])
        positions = list(mature_positions(event))
        for row in event["heads"]:
            head = int(row["kv_head"])
            retained = [position for position in positions if bool(replay_events[layer][(head, position)][0])]
            if len(retained) != int(row["matured_kept_tokens"]) or len(positions) - len(retained) != int(row["matured_dropped_tokens"]):
                raise ValueError("reconstructed frozen-mask maturity differs from lifecycle trace")
            for span in sorted({position // PAGE_TOKENS for position in retained}):
                index, head_key = len(transactions), (layer, head)
                predecessors = frozenset(() if head_key not in previous_by_head else (previous_by_head[head_key],))
                head_object, span_object = ("head_control", (layer, head)), ("span_owner", (layer, head, span))
                head_bank = bank_index(candidate["mapping"], candidate["banks"], head_object, layer=layer, head=head)
                span_bank = bank_index(candidate["mapping"], candidate["banks"], span_object, layer=layer, head=head)
                op_members = (MicroOp(index, head_object, head_bank, "rmw"), MicroOp(index, span_object, span_bank, "rmw"))
                transactions.append(ScheduledTransaction(index=index, phase="external_lifecycle_append", checkpoint=ordinal, layer=layer, head=head, arrival_ordinal=ordinal, predecessors=predecessors, demands=Counter((item.bank, item.operation) for item in op_members), banks=frozenset(item.bank for item in op_members)))
                members[index] = op_members
                previous_by_head[head_key] = index
    return transactions, members


def m2_fixed_provision(a4121: dict[str, Any]) -> dict[str, Any]:
    rows = {row["name"]: row for row in a4121.get("candidate_rows", [])}
    row = rows.get(M2)
    if row is None or row.get("register_area_included") is not True:
        raise ValueError("A4.12.1 complete M2 provisioned proxy is absent")
    return {"physical_candidate": M2, "public_cacti_sram_proxy_area_mm2": float(row["cacti_proxy_macro_area_mm2"]), "fixed_cost_rule": "One fixed provisioned M2 metadata-engine public-CACTI proxy. It is reported once per experiment, never summed once per workload.", "boundary": row.get("area_boundary")}


def workload_row(binding: dict[str, Any], candidate: dict[str, Any], macros: dict[str, dict[str, float]]) -> tuple[dict[str, Any], dict[str, Path]]:
    workload = str(binding.get("workload"))
    manifest_path, trace_path = Path(binding.get("manifest", "")), Path(binding.get("lifecycle_trace", ""))
    if sha256_file(manifest_path) != binding.get("manifest_sha256") or sha256_file(trace_path) != binding.get("lifecycle_trace_sha256"):
        raise ValueError(f"{workload}: accepted lifecycle artifact hash mismatch")
    manifest = read_json(manifest_path, f"{workload} lifecycle manifest")
    if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest.get("status") != "complete":
        raise ValueError(f"{workload}: lifecycle manifest is incomplete")
    events = read_events(trace_path); heads = expected_heads(events); validate_event_rows(events, heads)
    transactions, members = reconstruct_transactions(events, replay_source(manifest), candidate)
    conversion = binding.get("fixed_token_span_transaction_conversion", {})
    if len(transactions) != int(conversion.get("generated_transaction_groups", -1)) or conversion.get("token_to_span_tokens") != PAGE_TOKENS or conversion.get("transaction_members") != ["head_control_rmw", "span_owner_rmw"]:
        raise ValueError(f"{workload}: A4.11.2b conversion/group count changed")
    opportunities = [("external_lifecycle_append", int(event["logical_transition_sequence"])) for event in events]
    result = replay(transactions, opportunities, members, M2, macros, POST_TRACE_DRAIN_LIMIT)
    if not result["drained_within_declared_bound"] or result["trace_end_residual_backlog"] != 0:
        raise RuntimeError(f"{workload}: fixed M2 replay did not drain losslessly")
    return {"workload": workload, "exact_generated_token_ids_sha256": binding["exact_generated_token_ids_sha256"], "trace_bound_source": {"lifecycle_manifest_sha256": binding["manifest_sha256"], "lifecycle_trace_sha256": binding["lifecycle_trace_sha256"], "lifecycle_event_count": len(events)}, "deterministic_conversion": {"token_to_span_tokens": PAGE_TOKENS, "transaction_group_count": len(transactions), "transaction_members": ["head_control_rmw", "span_owner_rmw"], "per_head_fifo_predecessor": True, "boundary": "Frozen replay-mask retained tokens are lowered to append-event/layer/KV-head/64-token-span groups; this is deterministic conversion, not observed hardware activity."}, "m2_declared_metadata_replay": result, "evidence_classes": {"trace_bound": ["lifecycle source hashes and exact token guard"], "deterministic_accounting": ["retained token to 64-token transaction group"], "declared_model": ["bank mapping, queue state, M2 service coordinate, drain"], "public_cacti_proxy": ["M2 pJ/access multiplied by explicit replayed accesses"]}}, {"manifest": manifest_path, "trace": trace_path}


def materialize(output: Path, report_paths: dict[str, Path], sources: dict[str, dict[str, Path]]) -> dict[str, Any]:
    folder = output / "input_artifacts"; folder.mkdir()
    copied: dict[str, Any] = {"reports": {}, "lifecycle": {}}
    for label, path in report_paths.items():
        target = folder / f"{label}_source.json"; shutil.copyfile(path, target)
        if sha256_file(target) != EXPECTED[label][1]: raise AssertionError("report changed while materializing")
        copied["reports"][label] = {"source_path": str(path), "materialized_copy": str(target), "sha256": sha256_file(target)}
    for workload, paths in sources.items():
        target_dir = folder / "lifecycle" / workload; target_dir.mkdir(parents=True)
        copied["lifecycle"][workload] = {}
        for kind, path in paths.items():
            target = target_dir / path.name; shutil.copyfile(path, target)
            copied["lifecycle"][workload][kind] = {"source_path": str(path), "materialized_copy": str(target), "sha256": sha256_file(target)}
    return copied


def main() -> None:
    args = parse_args()
    reports, candidate, macros = validate_reports(args)
    bindings = {str(row["workload"]): row for row in reports["a4112b"].get("workloads", [])}
    if set(bindings) != set(WORKLOADS): raise ValueError("A4.11.2b workload coverage changed")
    rows_and_sources = [workload_row(bindings[workload], candidate, macros) for workload in WORKLOADS]
    rows, sources = zip(*rows_and_sources)
    if args.preflight_only:
        print("A4.14.0 preflight passed: exact A4.11.2b/A4.12/A4.10 inputs, lifecycle hashes, fixed conversion, M2 drain, and declared queue semantics validated; no output created.")
        return
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    paths = {label: getattr(args, f"{label}_report") for label in EXPECTED}
    artifacts = materialize(args.output_dir, paths, dict(zip(WORKLOADS, sources)))
    config = {"stage": "A4.14.0", "workloads": list(WORKLOADS), "fixed_execution": "HA8-wide record-granular", "fixed_queue_contract": "local32/shared256/staging512", "metadata_candidate": M2, "post_trace_drain_limit": POST_TRACE_DRAIN_LIMIT, "selection_boundary": "M1 remains rejected and M3 remains unestimated/incomplete; neither is rerun or selected."}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "execution_classification": "workload-aligned deterministic lifecycle conversion plus fixed declared M2 metadata replay and public-CACTI access-energy proxy; not hardware timing, physical FIFO, PPA, architecture, or RTL evidence", "config": config, "config_hash": stable_hash(config), "input_artifacts": artifacts, "fixed_provisioned_m2_proxy": m2_fixed_provision(reports["a4121"]), "workload_rows": list(rows), "semantic_guards": {"exact_accepted_a4112b_a4120_a4121_a4122_a410_inputs_bound": True, "all_three_qwen_external_storage_workloads_bound": True, "prefill_armed_exact_token_and_lifecycle_guards_inherited": True, "transaction_group_counts_match_a4112b_fixed_conversion": True, "ha8_wide_record_granular_local32_shared256_staging512_fixed": True, "only_complete_m2_mapping_replayed_m1_rejected_m3_unestimated": True, "single_commit_boundary_fifo_ownership_dependency_and_lossless_credit_preserved": True, "all_workload_m2_replays_drain_losslessly": True, "m2_fixed_area_not_repeated_per_workload": True, "metadata_and_payload_service_coordinates_not_summed": True, "no_pruning_admission_queue_execution_scheduler_or_payload_variant_introduced": True, "no_hardware_measurement_or_rtl_claim": True}, "boundaries": ["Lifecycle maturity is direct software observation; token-to-span transaction groups are deterministic conversion; bank/queue/M2 service/drain fields are declared model only.", "M2 area and pJ/access are public-CACTI proxy inputs. M2 area is fixed provisioned hardware cost and is not workload-dependent.", "Declared metadata service coordinates must remain separate from A4.13.5 payload service coordinates. This report makes no combined cycle, throughput, measured energy, physical FIFO depth, architecture or RTL claim."]}
    path = args.output_dir / "a4140_workload_aligned_metadata_cost_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.14.0 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} workloads={len(rows)}")


if __name__ == "__main__":
    main()
