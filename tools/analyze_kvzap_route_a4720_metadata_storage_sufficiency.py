#!/usr/bin/env python3
"""A4.7.2.0 Route-A metadata storage sufficiency closure.

This is the last semantic closure before physical contention DSE.  It maps the
four fixed semantic record classes onto declared *modeled storage objects* and
checks width/namespace sufficiency.  A modeled storage object is not a chosen
physical entry, allocator, SRAM access, or hardware transaction.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a4682_access_epoch_trace import SCHEMA as A4682_SCHEMA, TRACE_SCHEMA as A4682_TRACE_SCHEMA
from tools.analyze_kvzap_route_a468220_metadata_recordization import SCHEMA as A468220_SCHEMA, TRACE_SCHEMA as A468220_TRACE_SCHEMA
from tools.analyze_kvzap_route_a470_metadata_access_concurrency import SCHEMA as A470_SCHEMA
from tools.analyze_kvzap_route_a471_metadata_transaction_contract import SCHEMA as A471_SCHEMA, TRANSACTION_TRACE_SCHEMA
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4720-metadata-storage-sufficiency-1.0"
RECORD_TYPES = ("frontier_control", "span_descriptor", "ownership_link", "selection_control")
SCOPES = ("per_head", "per_layer", "global")
NAMESPACE_POLICIES = (
    ("no_reuse_trace_namespace", 0),
    ("reuse_after_terminal_commit", 0),
    ("reuse_after_terminal_commit", 2),
)
WIDTH_SLACK_BITS = (0, 2, 4)
RESERVED_ENCODINGS = 1

# Direct frontier keys avoid adding a new semantic read to A4.7.1.  A future
# indirect-key alternative is an explicit access-lowering study, not part of
# this final sufficiency closure.
LAYOUTS = {
    "separated_direct_v1": {
        "storage_object_classes": {
            "frontier_control": ("frontier_control",), "span_descriptor": ("span_descriptor",),
            "ownership_link": ("ownership_link",), "selection_control": ("selection_control",),
        },
    },
    "span_owner_colocated_direct_v1": {
        "storage_object_classes": {
            "frontier_control": ("frontier_control",), "span_owner": ("span_descriptor", "ownership_link"),
            "selection_control": ("selection_control",),
        },
    },
    "control_colocated_direct_v1": {
        "storage_object_classes": {
            "head_control": ("frontier_control", "selection_control"), "span_descriptor": ("span_descriptor",),
            "ownership_link": ("ownership_link",),
        },
    },
    "both_colocated_direct_v1": {
        "storage_object_classes": {
            "head_control": ("frontier_control", "selection_control"), "span_owner": ("span_descriptor", "ownership_link"),
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.7.2.0 no-model metadata storage sufficiency closure: modeled fields/objects only, never a selected physical entry, bank, port, timing, or hardware operation.")
    parser.add_argument("--a4682-report", type=Path, required=True)
    parser.add_argument("--a4682-trace", type=Path, required=True)
    parser.add_argument("--a468220-report", type=Path, required=True)
    parser.add_argument("--a468220-trace", type=Path, required=True)
    parser.add_argument("--a470-report", type=Path, required=True)
    parser.add_argument("--a471-report", type=Path, required=True)
    parser.add_argument("--a471-trace", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate hash-bound predecessor reports/traces and guards without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def context_key(row: dict[str, Any]) -> tuple[str, str, int, str]:
    return (str(row["anchor"]), str(row["workload"]), int(row["evaluation_horizon_append_opportunities"]), str(row["organization_label"]))


def ceil_log2_namespace(required: int, reserved: int, slack: int) -> int:
    if required < 1 or reserved < 1 or slack < 0:
        raise ValueError("invalid namespace-width parameters")
    return (required + reserved - 1).bit_length() + slack


def distribution(values: Iterable[int | float]) -> dict[str, int | float | None]:
    items = sorted(values)
    def p(fraction: float) -> int | float | None:
        return items[int((len(items) - 1) * fraction)] if items else None
    return {"count": len(items), "min": min(items) if items else None, "p50": p(.50), "p95": p(.95), "p99": p(.99), "max": max(items) if items else None, "sum": sum(items)}


def scope_key(scope: str, *, layer: int, head: int) -> tuple[int, ...]:
    if scope == "per_head": return (layer, head)
    if scope == "per_layer": return (layer,)
    if scope == "global": return ()
    raise ValueError(f"unknown scope {scope}")


@dataclass
class Envelope:
    max_layer: int = -1
    max_head: int = -1
    max_birth: int = -1
    max_sequence: int = -1
    max_remaining: int = -1
    max_checkpoint: int = -1
    observed_heads: set[tuple[int, int]] = field(default_factory=set)
    distinct: dict[str, dict[tuple[int, ...], set[int]]] = field(default_factory=lambda: {scope: defaultdict(set) for scope in SCOPES})
    active: dict[str, dict[tuple[int, ...], set[int]]] = field(default_factory=lambda: {scope: defaultdict(set) for scope in SCOPES})
    peak_per_namespace: dict[str, dict[tuple[int, ...], int]] = field(default_factory=lambda: {scope: defaultdict(int) for scope in SCOPES})
    peak_live_total: dict[str, int] = field(default_factory=lambda: {scope: 0 for scope in SCOPES})
    active_total: dict[str, int] = field(default_factory=lambda: {scope: 0 for scope in SCOPES})
    right_censored_active_total: dict[str, int] = field(default_factory=dict)
    tail_extension_count: int = 0

    def observe(self, row: dict[str, Any]) -> None:
        layer, head = int(row["layer"]), int(row["kv_head"])
        self.max_layer = max(self.max_layer, layer); self.max_head = max(self.max_head, head)
        self.max_checkpoint = max(self.max_checkpoint, int(row["logical_checkpoint"]))
        self.observed_heads.add((layer, head))
        for name, target in (("birth_opportunity", "max_birth"), ("within_head_sequence_start", "max_sequence"), ("span_remaining_count", "max_remaining")):
            value = row.get(name)
            if value is not None: setattr(self, target, max(getattr(self, target), int(value)))
        primitive = str(row["primitive"])
        if primitive == "tail_extension": self.tail_extension_count += 1
        if primitive not in {"span_create", "span_release"}: return
        span_id = int(row["span_id"])
        for scope in SCOPES:
            key = scope_key(scope, layer=layer, head=head); active = self.active[scope][key]
            if primitive == "span_create":
                if span_id in active: raise AssertionError("span created twice while active")
                active.add(span_id); self.distinct[scope][key].add(span_id); self.active_total[scope] += 1
                self.peak_per_namespace[scope][key] = max(self.peak_per_namespace[scope][key], len(active))
                self.peak_live_total[scope] = max(self.peak_live_total[scope], self.active_total[scope])
            else:
                if span_id not in active: raise AssertionError("span released while not active")
                active.remove(span_id); self.active_total[scope] -= 1

    def finish(self) -> None:
        # A4.6.8.2.0 deliberately retains right-censored spans at fixed
        # horizons.  They remain live namespace/footprint state, not an error.
        self.right_censored_active_total = dict(self.active_total)

    def namespace_requirements(self, scope: str) -> dict[str, int]:
        return {
            "trace_distinct_namespace": max((len(items) for items in self.distinct[scope].values()), default=1),
            "reuse_peak_live_namespace": max(self.peak_per_namespace[scope].values(), default=1),
            "peak_live_total_descriptors": self.peak_live_total[scope],
            "right_censored_active_total_descriptors": self.right_censored_active_total[scope],
        }


def scan_a4682_trace(path: Path) -> dict[tuple[str, str, int, str], Envelope]:
    envelopes: dict[tuple[str, str, int, str], Envelope] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("schema_version") != A4682_TRACE_SCHEMA: raise ValueError("unexpected A4.6.8.2.0 trace schema")
            key = context_key(row); envelopes.setdefault(key, Envelope()).observe(row)
    for envelope in envelopes.values(): envelope.finish()
    return envelopes


def normalized_object_key(layout: str, record_type: str, record_identity: list[Any], *, layer: int, head: int) -> tuple[str, tuple[Any, ...]]:
    classes = LAYOUTS[layout]["storage_object_classes"]
    object_class = next(name for name, members in classes.items() if record_type in members)
    if object_class == "span_owner": return object_class, (int(record_identity[-1]),)
    if object_class == "head_control": return object_class, (layer, head)
    return object_class, tuple(record_identity)


def scope_tags(scope: str, envelope: Envelope) -> tuple[int, int]:
    layer_bits = ceil_log2_namespace(envelope.max_layer + 1, 1, 0) if scope == "global" else 0
    head_bits = ceil_log2_namespace(envelope.max_head + 1, 1, 0) if scope in {"per_layer", "global"} else 0
    return layer_bits, head_bits


def field_widths(envelope: Envelope, scope: str, policy: str, generation_bits: int, slack: int) -> dict[str, int]:
    requirements = envelope.namespace_requirements(scope)
    required = requirements["trace_distinct_namespace"] if policy == "no_reuse_trace_namespace" else requirements["reuse_peak_live_namespace"]
    slot_bits = ceil_log2_namespace(required, RESERVED_ENCODINGS, slack)
    layer_bits, head_bits = scope_tags(scope, envelope)
    def value_bits(value: int) -> int: return ceil_log2_namespace(max(1, value + 1), 1, slack)
    return {
        "valid_bit": 1, "source_bit": 1, "scope_layer_tag_bits": layer_bits, "scope_head_tag_bits": head_bits,
        "span_slot_bits": slot_bits, "span_generation_bits": generation_bits,
        "birth_bits": value_bits(envelope.max_birth), "sequence_bits": value_bits(envelope.max_sequence),
        "remaining_count_bits": value_bits(envelope.max_remaining), "selection_epoch_bits": value_bits(envelope.max_checkpoint),
    }


def semantic_record_bits(widths: dict[str, int]) -> dict[str, int]:
    tag = widths["scope_layer_tag_bits"] + widths["scope_head_tag_bits"]
    handle = widths["span_slot_bits"] + widths["span_generation_bits"]
    return {
        "frontier_control": widths["valid_bit"] + widths["source_bit"] + handle + widths["birth_bits"] + widths["sequence_bits"] + tag,
        "span_descriptor": widths["valid_bit"] + widths["source_bit"] + widths["birth_bits"] + widths["sequence_bits"] + widths["remaining_count_bits"] + handle + tag,
        "ownership_link": widths["valid_bit"] + widths["source_bit"] + handle + handle + tag,
        "selection_control": widths["valid_bit"] + widths["source_bit"] + widths["selection_epoch_bits"] + tag,
    }


def modeled_object_bits(layout: str, bits: dict[str, int]) -> dict[str, int]:
    output = {}
    for object_class, members in LAYOUTS[layout]["storage_object_classes"].items():
        # A co-located object retains the full bit accounting of each semantic
        # record.  A4.7.2.0 grants no implicit shared-header compression.
        if object_class == "head_control":
            output[object_class] = 2 * bits["frontier_control"] + bits["selection_control"]
        else:
            output[object_class] = sum(bits[item] for item in members)
    return output


def static_object_counts(layout: str, envelope: Envelope, scope: str) -> dict[str, int]:
    live = envelope.namespace_requirements(scope)["peak_live_total_descriptors"]
    heads = len(envelope.observed_heads)
    counts: dict[str, int] = {}
    for object_class, members in LAYOUTS[layout]["storage_object_classes"].items():
        if object_class == "span_owner": counts[object_class] = live
        elif object_class == "span_descriptor" or object_class == "ownership_link": counts[object_class] = live
        elif object_class == "head_control": counts[object_class] = heads
        elif object_class == "frontier_control": counts[object_class] = 2 * heads
        elif object_class == "selection_control": counts[object_class] = heads
        else: raise AssertionError("unexpected modeled storage object class")
    return counts


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    a4682 = read_completed(args.a4682_report, A4682_SCHEMA, "A4.6.8.2.0")
    a468220 = read_completed(args.a468220_report, A468220_SCHEMA, "A4.6.8.2.2.0")
    a470 = read_completed(args.a470_report, A470_SCHEMA, "A4.7.0 _02")
    a471 = read_completed(args.a471_report, A471_SCHEMA, "A4.7.1")
    hashes = {"a4682_trace": sha256_file(args.a4682_trace), "a468220_trace": sha256_file(args.a468220_trace), "a471_trace": sha256_file(args.a471_trace)}
    if a4682.get("access_epoch_trace", {}).get("schema_version") != A4682_TRACE_SCHEMA or a4682["access_epoch_trace"].get("sha256") != hashes["a4682_trace"]: raise ValueError("A4.6.8.2.0 trace binding mismatch")
    if a468220.get("record_access_trace", {}).get("schema_version") != A468220_TRACE_SCHEMA or a468220["record_access_trace"].get("sha256") != hashes["a468220_trace"]: raise ValueError("A4.6.8.2.2.0 trace binding mismatch")
    if a468220.get("input_artifacts", {}).get("a4682_report_sha256") != sha256_file(args.a4682_report) or a468220["input_artifacts"].get("a4682_trace_sha256") != hashes["a4682_trace"]: raise ValueError("A4.6.8.2.2.0 does not bind A4.6.8.2.0 inputs")
    if a470.get("input_artifacts", {}).get("a468220_report_sha256") != sha256_file(args.a468220_report) or a470["input_artifacts"].get("a468220_trace_sha256") != hashes["a468220_trace"]: raise ValueError("A4.7.0 does not bind A4.6.8.2.2.0 inputs")
    if a471.get("input_artifacts", {}).get("a468220_report_sha256") != sha256_file(args.a468220_report) or a471["input_artifacts"].get("a468220_trace_sha256") != hashes["a468220_trace"] or a471["input_artifacts"].get("a470_report_sha256") != sha256_file(args.a470_report): raise ValueError("A4.7.1 input hash chain mismatch")
    if a471.get("transaction_trace", {}).get("schema_version") != TRANSACTION_TRACE_SCHEMA or a471["transaction_trace"].get("sha256") != hashes["a471_trace"]: raise ValueError("A4.7.1 transaction trace binding mismatch")
    required = ("a468220_and_a470_hash_bound_contracts_validated", "every_dependency_node_maps_to_exactly_one_transaction_group", "every_group_has_read_write_rmw_release_sets_and_one_commit_boundary", "post_commit_span_owner_source_queue_and_oldest_replay_consistent", "tail_extension_defined_but_zero_observed_not_synthesized", "semantic_atomicity_explicitly_not_hardware_atomicity")
    if not all(a471.get("semantic_guards", {}).get(name) is True for name in required): raise ValueError("A4.7.1 semantic guards incomplete")
    return a4682, a468220, a470, a471


def scan_transaction_mappings(path: Path) -> dict[tuple[str, str, int, str], dict[str, Any]]:
    results: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("schema_version") != TRANSACTION_TRACE_SCHEMA: raise ValueError("unexpected A4.7.1 transaction trace schema")
            key = context_key(row)
            if key not in results:
                results[key] = {layout: {"semantic_record_count": 0, "group_count": 0, "phase_fanout": defaultdict(list), "transaction_boundaries": set(), "semantic_types": Counter()} for layout in LAYOUTS}
            sets = (row["read_set"], row["write_set"], row["rmw_set"], row["release_set"])
            semantic_refs = {(item["record_type"], tuple(item["record_identity"])) for items in sets for item in items}
            if not semantic_refs or any(record_type not in RECORD_TYPES for record_type, _ in semantic_refs): raise AssertionError("transaction has invalid semantic record set")
            if not row.get("semantic_atomicity_only") or not row.get("commit_linearization_boundary"): raise AssertionError("transaction lacks semantic commit declaration")
            for layout in LAYOUTS:
                objects = set()
                for record_type, identity in semantic_refs:
                    objects.add(normalized_object_key(layout, record_type, list(identity), layer=int(row["layer"]), head=int(row["kv_head"])))
                summary = results[key][layout]
                summary["semantic_record_count"] += len(semantic_refs); summary["group_count"] += 1
                summary["phase_fanout"][str(row["phase"])].append(len(objects)); summary["transaction_boundaries"].add(str(row["commit_linearization_boundary"]))
                summary["semantic_types"].update(record_type for record_type, _ in semantic_refs)
    return results


def main() -> None:
    args = parse_args(); a4682, a468220, a470, a471 = validate_inputs(args)
    if args.preflight_only:
        print("A4.7.2.0 preflight passed: A4.6.8.2.0/A4.6.8.2.2.0/A4.7.0 _02/A4.7.1 hash-bound contracts and guards validated; no output created."); return
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    envelopes = scan_a4682_trace(args.a4682_trace)
    mappings = scan_transaction_mappings(args.a471_trace)
    expected_contexts = {(row["anchor"], row["workload"], row["evaluation_horizon_append_opportunities"], row["organization_label"]) for row in a471["context_rows"]}
    if set(envelopes) != expected_contexts or set(mappings) != expected_contexts: raise AssertionError("predecessor context coverage mismatch")
    layout_mapping_rows = []
    observed_types_all: set[str] = set()
    for key in sorted(expected_contexts):
        for layout, summary in mappings[key].items():
            observed_types_all.update(summary["semantic_types"])
            layout_mapping_rows.append({"anchor": key[0], "workload": key[1], "evaluation_horizon_append_opportunities": key[2], "organization_label": key[3], "layout": layout, "semantic_record_count": summary["semantic_record_count"], "transaction_group_count": summary["group_count"], "transaction_boundaries_preserved": sorted(summary["transaction_boundaries"]), "phase_storage_object_fanout": {phase: distribution(summary["phase_fanout"][phase]) for phase in ("activation", "steady_state_append", "steady_state_dequeue")}, "semantic_record_types_observed": sorted(summary["semantic_types"]), "physical_entry_not_selected": True})
    if observed_types_all != set(RECORD_TYPES): raise AssertionError("transaction trace does not cover all fixed semantic record types")
    width_rows = []
    for key in sorted(expected_contexts):
        envelope = envelopes[key]
        if envelope.tail_extension_count != 0: raise AssertionError("A4.7.2.0 must not synthesize or accept tail extension events")
        for layout in LAYOUTS:
            for scope in SCOPES:
                namespace = envelope.namespace_requirements(scope)
                for policy, generation_bits in NAMESPACE_POLICIES:
                    for slack in WIDTH_SLACK_BITS:
                        widths = field_widths(envelope, scope, policy, generation_bits, slack)
                        semantic_bits = semantic_record_bits(widths); object_bits = modeled_object_bits(layout, semantic_bits); object_counts = static_object_counts(layout, envelope, scope)
                        peak_bits = sum(object_counts[name] * object_bits[name] for name in object_counts)
                        required = namespace["trace_distinct_namespace"] if policy == "no_reuse_trace_namespace" else namespace["reuse_peak_live_namespace"]
                        width_rows.append({"anchor": key[0], "workload": key[1], "evaluation_horizon_append_opportunities": key[2], "organization_label": key[3], "layout": layout, "storage_scope": scope, "namespace_policy": policy, "generation_bits": generation_bits, "reserved_invalid_encodings": RESERVED_ENCODINGS, "width_slack_bits": slack, "namespace_requirements": namespace, "field_widths_bits": widths, "semantic_record_widths_bits": semantic_bits, "modeled_storage_object_widths_bits": object_bits, "modeled_peak_storage_object_counts": object_counts, "modeled_peak_metadata_bits": peak_bits, "namespace_width_sufficient": (1 << widths["span_slot_bits"]) >= required + RESERVED_ENCODINGS, "semantic_record_count_unchanged": True, "physical_entry_not_selected": True})
    expected_width_rows = len(expected_contexts) * len(LAYOUTS) * len(SCOPES) * len(NAMESPACE_POLICIES) * len(WIDTH_SLACK_BITS)
    if len(width_rows) != expected_width_rows: raise AssertionError("unexpected A4.7.2.0 width coverage")
    config = {"semantic_record_types": list(RECORD_TYPES), "layouts": LAYOUTS, "storage_scopes": list(SCOPES), "namespace_policies": [{"name": name, "generation_bits": generation} for name, generation in NAMESPACE_POLICIES], "reserved_invalid_encodings": RESERVED_ENCODINGS, "width_slack_bits": list(WIDTH_SLACK_BITS), "field_width_rule": "ceil_log2(required_namespace + reserved_invalid_encodings) + declared slack; reuse policy and generation bits are explicit", "frontier_key_placement": "direct only; indirect placement would alter access lowering and is excluded from A4.7.2.0", "boundary": "Semantic records remain distinct under co-location. Modeled storage objects and metadata bits are not physical entries, allocated capacity, SRAM accesses, hardware atomics, banks, ports, cycles, bandwidth, latency, throughput, HBM traffic, energy, area, hardware selection, architecture specification, or RTL."}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "trace-derived namespace/field envelopes plus functional semantic-record-to-modeled-storage-object closure; modeled metadata bits are not a physical implementation result", "input_artifacts": {"a4682_report_sha256": sha256_file(args.a4682_report), "a4682_trace_sha256": sha256_file(args.a4682_trace), "a468220_report_sha256": sha256_file(args.a468220_report), "a468220_trace_sha256": sha256_file(args.a468220_trace), "a470_report_sha256": sha256_file(args.a470_report), "a471_report_sha256": sha256_file(args.a471_report), "a471_trace_sha256": sha256_file(args.a471_trace)}, "layout_mapping_rows": layout_mapping_rows, "width_sufficiency_rows": width_rows, "semantic_guards": {"complete_hash_bound_predecessor_chain_validated": True, "four_semantic_record_types_fixed_and_all_retained": True, "a471_transaction_sets_and_commit_boundaries_not_changed": True, "every_semantic_record_maps_to_declared_modeled_storage_object": True, "semantic_record_storage_object_and_physical_entry_concepts_separated": True, "namespace_scope_reuse_reserved_and_generation_assumptions_explicit": True, "no_silent_field_or_namespace_overflow": True, "tail_extension_remains_zero_observed_not_synthesized": True, "no_new_record_type_or_transaction_semantics": True, "no_bank_mapping_service_scheduler_or_contention_model": True, "no_payload_movement_or_hardware_cost_inferred": True, "no_model_runtime_profiler_or_hardware_parameter_loaded": True, "no_drop_fallback_migration_backing_or_protection_action": True}}
    args.output_dir.mkdir(parents=True); path = args.output_dir / "a4720_metadata_storage_sufficiency_report.json"; path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.7.2.0 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} layouts={len(layout_mapping_rows)} width_rows={len(width_rows)}")


if __name__ == "__main__": main()
