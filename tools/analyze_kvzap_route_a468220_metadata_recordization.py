#!/usr/bin/env python3
"""A4.6.8.2.2.0 strict metadata-recordization gate for Route-A.

It transforms only already-validated A4.6.8.2.0 metadata primitives into a
minimal logical record-access trace.  It neither creates payload movement nor
changes the preceding FIFO, grant, source, or lifecycle contract.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a4682_access_epoch_trace import SCHEMA as A4682_SCHEMA, TRACE_SCHEMA as A4682_TRACE_SCHEMA
from tools.analyze_kvzap_route_a46821_metadata_organization_sensitivity import SCHEMA as A46821_SCHEMA
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a468220-metadata-recordization-1.0"
TRACE_SCHEMA = "kvzap-route-a468220-record-access-record-1.0"
PAYLOAD = {"payload_reference_create", "payload_reference_release"}
RECORD_TYPES = ("frontier_control", "span_descriptor", "ownership_link", "selection_control")
PHASES = ("activation", "steady_state_append", "steady_state_dequeue")
PRIMITIVE_CONTRACT = {
    "source_head_metadata_read": ("frontier_control", "read"),
    "oldest_source_compare": ("selection_control", "read"),
    "span_create": ("span_descriptor", "write"),
    "ownership_link": ("ownership_link", "write"),
    "span_partial_dequeue": ("span_descriptor", "rmw"),
    "span_head_remaining_update": ("span_descriptor", "rmw"),
    "source_head_update": ("frontier_control", "rmw"),
    "span_release": ("span_descriptor", "release"),
    "ownership_unlink": ("ownership_link", "release"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.6.8.2.2.0 no-model strict metadata-recordization gate; no physical layout or traffic inference.")
    parser.add_argument("--a4682-report", type=Path, required=True)
    parser.add_argument("--a4682-trace", type=Path, required=True)
    parser.add_argument("--a46821-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate bound reports, guards, and trace hash without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def context(event: dict[str, Any]) -> tuple[str, str, int, str]:
    return (str(event["anchor"]), str(event["workload"]), int(event["evaluation_horizon_append_opportunities"]), str(event["organization_label"]))


def record_identity(event: dict[str, Any], record_type: str) -> tuple[Any, ...]:
    layer, head = int(event["layer"]), int(event["kv_head"])
    if record_type == "frontier_control":
        return (layer, head, str(event["source"]))
    if record_type == "selection_control":
        return (layer, head)
    if record_type == "span_descriptor":
        return (layer, head, int(event["span_id"]))
    if record_type == "ownership_link":
        return (layer, head, str(event["source"]), int(event["span_id"]))
    raise ValueError(f"unknown record type {record_type}")


def primitive_to_record(event: dict[str, Any]) -> dict[str, Any]:
    primitive = str(event["primitive"])
    if primitive not in PRIMITIVE_CONTRACT:
        raise ValueError(f"unmapped non-payload primitive {primitive}")
    record_type, access_kind = PRIMITIVE_CONTRACT[primitive]
    return {
        "context": context(event), "phase": str(event["phase"]), "logical_checkpoint": int(event["logical_checkpoint"]),
        "layer": int(event["layer"]), "kv_head": int(event["kv_head"]), "source": event.get("source"),
        "record_type": record_type, "record_identity": record_identity(event, record_type), "access_kind": access_kind,
        "primitive": primitive, "span_id": event.get("span_id"), "birth_opportunity": event.get("birth_opportunity"),
        "within_head_sequence_start": event.get("within_head_sequence_start"),
    }


def merge_compatible(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    """The sole permitted merge is an adjacent same-span dequeue/remaining RMW pair."""
    return (
        previous["primitive"] == "span_partial_dequeue"
        and current["primitive"] == "span_head_remaining_update"
        and previous["context"] == current["context"]
        and previous["phase"] == current["phase"]
        and previous["logical_checkpoint"] == current["logical_checkpoint"]
        and previous["record_type"] == current["record_type"] == "span_descriptor"
        and previous["record_identity"] == current["record_identity"]
        and previous["source"] == current["source"]
        and previous["birth_opportunity"] == current["birth_opportunity"]
        and previous["within_head_sequence_start"] == current["within_head_sequence_start"]
    )


class Writer:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.raw = path.open("wb")
        self.gz = gzip.GzipFile(filename="", mode="wb", fileobj=self.raw, mtime=0)
        self.text = io.TextIOWrapper(self.gz, encoding="utf-8", newline="\n")
        self.count = 0

    def write(self, op: dict[str, Any]) -> None:
        payload = {"schema_version": TRACE_SCHEMA, **op}
        self.text.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        self.count += 1

    def close(self) -> None:
        self.text.close()
        self.raw.close()


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    a4682 = read_completed(args.a4682_report, A4682_SCHEMA, "A4.6.8.2.0")
    a46821 = read_completed(args.a46821_report, A46821_SCHEMA, "A4.6.8.2.1")
    trace_sha = sha256_file(args.a4682_trace)
    if a4682.get("access_epoch_trace", {}).get("schema_version") != A4682_TRACE_SCHEMA or a4682["access_epoch_trace"].get("sha256") != trace_sha:
        raise ValueError("A4.6.8.2.0 finalized trace hash/schema mismatch")
    if a46821.get("input_artifacts", {}).get("a4682_report_sha256") != sha256_file(args.a4682_report) or a46821.get("input_artifacts", {}).get("a4682_trace_sha256") != trace_sha:
        raise ValueError("A4.6.8.2.1 does not hash-bind supplied A4.6.8.2.0 inputs")
    required_4682 = ("complete_hash_chain_validated", "fixed_a464_grants_not_rescheduled", "a4670_canonical_fifo_replayed_after_each_event", "exact_pending_birth_order_oldest_and_source_ownership_reconstructible", "a4681_primitive_totals_matched_phase_by_phase", "no_payload_movement_inferred_from_lifecycle")
    required_46821 = ("complete_hash_chain_and_finalized_a4682_trace_validated", "fixed_a4682_fifo_grants_source_affiliation_and_event_order_not_rescheduled", "metadata_classes_cover_all_nonpayload_trace_primitives", "payload_reference_primitives_explicitly_excluded_from_metadata_service_observer", "no_payload_movement_or_hardware_cost_inferred")
    if not all(a4682.get("semantic_guards", {}).get(name) is True for name in required_4682):
        raise ValueError("A4.6.8.2.0 semantic guards incomplete")
    if not all(a46821.get("semantic_guards", {}).get(name) is True for name in required_46821):
        raise ValueError("A4.6.8.2.1 semantic guards incomplete")
    return a4682, a46821


def emit_group(*, group: list[dict[str, Any]], writer: Writer, summaries: dict[tuple[str, str, int, str], Counter[str]], record_types: dict[tuple[str, str, int, str], Counter[str]]) -> None:
    first = group[0]
    primitives = [item["primitive"] for item in group]
    merged = len(group) == 2
    if len(group) not in (1, 2) or (merged and not merge_compatible(group[0], group[1])):
        raise AssertionError("invalid strict same-record merge group")
    key = first["context"]
    summaries[key]["conservative_record_ops"] += len(group)
    summaries[key]["strict_same_record_record_ops"] += 1
    summaries[key]["strict_merge_gain"] += len(group) - 1
    summaries[key][f"phase::{first['phase']}::conservative"] += len(group)
    summaries[key][f"phase::{first['phase']}::strict"] += 1
    record_types[key][first["record_type"]] += 1
    writer.write({
        "anchor": key[0], "workload": key[1], "evaluation_horizon_append_opportunities": key[2], "organization_label": key[3],
        "phase": first["phase"], "logical_checkpoint": first["logical_checkpoint"], "layer": first["layer"], "kv_head": first["kv_head"],
        "source": first["source"], "record_type": first["record_type"], "record_identity": list(first["record_identity"]), "access_kind": first["access_kind"],
        "primitive_sequence": primitives, "conservative_record_op_count": len(group), "strict_same_record_merged_op_count": 1, "strict_merge_applied": merged,
        "span_id": first["span_id"], "birth_opportunity": first["birth_opportunity"], "within_head_sequence_start": first["within_head_sequence_start"],
    })


def main() -> None:
    args = parse_args()
    a4682, a46821 = validate_inputs(args)
    if args.preflight_only:
        print("A4.6.8.2.2.0 preflight passed: A4.6.8.2.0/A4.6.8.2.1 contracts, guards, and finalized trace hash validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    trace_path = args.output_dir / "a468220_record_access_trace.jsonl.gz"
    writer = Writer(trace_path)
    primitive_totals: Counter[str] = Counter()
    payload_totals: Counter[str] = Counter()
    summaries: dict[tuple[str, str, int, str], Counter[str]] = defaultdict(Counter)
    record_types: dict[tuple[str, str, int, str], Counter[str]] = defaultdict(Counter)
    pending: dict[str, Any] | None = None
    raw_record_count = 0
    try:
        with gzip.open(args.a4682_trace, "rt", encoding="utf-8") as handle:
            for line in handle:
                event = json.loads(line)
                if event.get("schema_version") != A4682_TRACE_SCHEMA:
                    raise ValueError("unexpected A4.6.8.2.0 trace schema")
                raw_record_count += 1
                primitive = str(event["primitive"])
                if primitive in PAYLOAD:
                    payload_totals[primitive] += 1
                    continue
                primitive_totals[primitive] += 1
                current = primitive_to_record(event)
                if pending is None:
                    pending = current
                elif merge_compatible(pending, current):
                    emit_group(group=[pending, current], writer=writer, summaries=summaries, record_types=record_types)
                    pending = None
                else:
                    emit_group(group=[pending], writer=writer, summaries=summaries, record_types=record_types)
                    pending = current
        if pending is not None:
            emit_group(group=[pending], writer=writer, summaries=summaries, record_types=record_types)
    finally:
        writer.close()
    if raw_record_count != int(a4682["access_epoch_trace"]["record_count"]):
        raise AssertionError("raw A4.6.8.2.0 trace record count mismatch")
    if set(primitive_totals) != set(PRIMITIVE_CONTRACT):
        raise AssertionError("primitive contract does not exactly cover non-payload trace primitives")
    expected_primitives = {key: int(value) for key, value in a46821["primitive_totals_from_a4682_trace"].items() if key not in PAYLOAD}
    if dict(sorted(primitive_totals.items())) != expected_primitives or dict(sorted(payload_totals.items())) != a46821["explicitly_excluded_payload_reference_totals"]:
        raise AssertionError("recordization primitive totals disagree with A4.6.8.2.1")
    conservative = sum(primitive_totals.values())
    strict = sum(summary["strict_same_record_record_ops"] for summary in summaries.values())
    gain = sum(summary["strict_merge_gain"] for summary in summaries.values())
    if conservative != sum(summary["conservative_record_ops"] for summary in summaries.values()) or strict + gain != conservative:
        raise AssertionError("primitive-to-record count accounting mismatch")
    expected_contexts = {(row["anchor"], row["workload"], row["evaluation_horizon_append_opportunities"], row["organization_label"]) for row in a46821["sensitivity_rows"]}
    if set(summaries) != expected_contexts:
        raise AssertionError("recordization context coverage disagrees with A4.6.8.2.1")
    context_rows = []
    for key in sorted(summaries):
        summary = summaries[key]
        context_rows.append({
            "anchor": key[0], "workload": key[1], "evaluation_horizon_append_opportunities": key[2], "organization_label": key[3],
            "conservative_record_ops": summary["conservative_record_ops"], "strict_same_record_record_ops": summary["strict_same_record_record_ops"], "strict_merge_gain": summary["strict_merge_gain"],
            "strict_merge_fraction_of_conservative": summary["strict_merge_gain"] / summary["conservative_record_ops"] if summary["conservative_record_ops"] else 0.0,
            "phase_curves": {phase: {"conservative_record_ops": summary[f"phase::{phase}::conservative"], "strict_same_record_record_ops": summary[f"phase::{phase}::strict"]} for phase in PHASES},
            "strict_merged_record_ops_by_type": {record_type: record_types[key][record_type] for record_type in RECORD_TYPES},
        })
    config = {
        "minimal_record_types": list(RECORD_TYPES), "conservative_curve": "one logical metadata primitive maps to one declared logical record operation", "strict_same_record_merge_curve": "only adjacent span_partial_dequeue then span_head_remaining_update on the same checkpoint, same span descriptor, source, birth, and sequence may merge", "boundary": "Record identity is logical and has no field width, byte size, physical address, payload movement, HBM/DMA traffic, bank, port, cycle, timing, latency, throughput, energy, area, capacity, hardware parameter, architecture specification, or RTL implication.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "no-model functional recordization over a trace-derived logical event stream; conservative/strict record-operation curves are neither physical accesses nor hardware cost",
        "input_artifacts": {"a4682_report_sha256": sha256_file(args.a4682_report), "a4682_trace_sha256": sha256_file(args.a4682_trace), "a46821_report_sha256": sha256_file(args.a46821_report)},
        "record_access_trace": {"schema_version": TRACE_SCHEMA, "relative_path": trace_path.name, "sha256": sha256_file(trace_path), "record_count": writer.count},
        "primitive_to_record_contract": {primitive: {"record_type": record_type, "access_kind": access_kind} for primitive, (record_type, access_kind) in PRIMITIVE_CONTRACT.items()},
        "primitive_totals": dict(sorted(primitive_totals.items())), "excluded_payload_reference_totals": dict(sorted(payload_totals.items())),
        "record_operation_curves": {"conservative_record_ops": conservative, "strict_same_record_record_ops": strict, "strict_merge_gain": gain, "strict_merge_fraction_of_conservative": gain / conservative if conservative else 0.0},
        "context_rows": context_rows,
        "semantic_guards": {"a4682_and_a46821_hash_bound_contracts_validated": True, "a46821_primitive_totals_and_context_coverage_matched": True, "fixed_fifo_oldest_source_ownership_and_grants_not_rescheduled": True, "every_nonpayload_primitive_maps_to_exactly_one_declared_record_type": True, "conservative_record_op_count_equals_nonpayload_primitive_count": True, "strict_merge_only_same_checkpoint_same_span_same_source_birth_and_sequence_adjacent_pair": True, "strict_merge_never_crosses_birth_source_or_order_boundary": True, "conservative_and_strict_curves_explainable_and_count_conserved": True, "payload_reference_events_excluded_not_inferred_as_payload_movement": True, "minimal_record_type_set_only": True, "no_model_runtime_profiler_or_hardware_parameter_loaded": True, "no_physical_layout_width_byte_bank_port_cycle_or_cost_inferred": True, "no_drop_fallback_migration_backing_or_protection_action": True},
    }
    path = args.output_dir / "a468220_metadata_recordization_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.8.2.2.0 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} record_ops={writer.count}")


if __name__ == "__main__":
    main()
