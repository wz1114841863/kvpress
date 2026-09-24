#!/usr/bin/env python3
"""A4.7.1 semantic metadata-transaction contract for fixed Route-A traces.

An atomic group here is a functional linearization boundary: no other logical
operation may observe the group's partial state.  It is explicitly not one
SRAM atomic operation, one hardware transaction, or one cycle.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a468220_metadata_recordization import SCHEMA as A468220_SCHEMA, TRACE_SCHEMA as RECORD_TRACE_SCHEMA
from tools.analyze_kvzap_route_a468221_record_organization_sensitivity import curve_weight
from tools.analyze_kvzap_route_a470_metadata_access_concurrency import EDGE_TYPES, SCHEMA as A470_SCHEMA, dependencies
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a471-metadata-transaction-contract-1.0"
TRANSACTION_TRACE_SCHEMA = "kvzap-route-a471-metadata-transaction-record-1.0"
PHASES = ("activation", "steady_state_append", "steady_state_dequeue")
CURVES = ("conservative", "strict_same_record")

# This closed catalog is declared before trace replay.  A transaction group is
# only a semantic visibility boundary; its sets are logical record identities.
TRANSACTION_CONTRACT = {
    "admission_create": {
        "primitive_pattern": ("span_create", "ownership_link"),
        "commit_boundary": "after_span_and_ownership_link_are_jointly_visible",
    },
    "dequeue_nonterminal": {
        "primitive_pattern": ("source_head_metadata_read", "[oldest_source_compare]", "span_partial_dequeue", "span_head_remaining_update", "source_head_update"),
        "commit_boundary": "after_selection_and_nonterminal_span_frontier_updates_are_jointly_visible",
    },
    "dequeue_terminal": {
        "primitive_pattern": ("source_head_metadata_read", "[oldest_source_compare]", "span_partial_dequeue", "span_head_remaining_update", "span_release", "ownership_unlink", "source_head_update"),
        "commit_boundary": "after_selection_span_release_ownership_unlink_and_frontier_update_are_jointly_visible",
    },
    "tail_extension_reserved_zero_observed": {
        "primitive_pattern": ("tail_extension",),
        "commit_boundary": "after_same_source_same_birth_sequence_contiguous_span_extension_is_visible",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.7.1 no-model semantic metadata-transaction contract over fixed Route-A records; atomic groups are not hardware operations.")
    parser.add_argument("--a468220-report", type=Path, required=True)
    parser.add_argument("--a468220-trace", type=Path, required=True)
    parser.add_argument("--a470-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate hash-bound inputs and guards without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def context_key(op: dict[str, Any]) -> tuple[str, str, int, str]:
    return (str(op["anchor"]), str(op["workload"]), int(op["evaluation_horizon_append_opportunities"]), str(op["organization_label"]))


def same_head_checkpoint(items: Iterable[dict[str, Any]]) -> bool:
    rows = list(items)
    if not rows:
        return False
    first = rows[0]
    return all(
        context_key(row) == context_key(first)
        and str(row["phase"]) == str(first["phase"])
        and int(row["logical_checkpoint"]) == int(first["logical_checkpoint"])
        and int(row["layer"]) == int(first["layer"])
        and int(row["kv_head"]) == int(first["kv_head"])
        for row in rows
    )


def primitive_sequence(op: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(item) for item in op["primitive_sequence"])


def record_ref(op: dict[str, Any]) -> dict[str, Any]:
    return {"record_type": str(op["record_type"]), "record_identity": list(op["record_identity"])}


def unique_refs(ops: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    seen = set()
    for op in ops:
        item = record_ref(op)
        key = (item["record_type"], tuple(item["record_identity"]))
        if key not in seen:
            output.append(item); seen.add(key)
    return output


def group_record_sets(members: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for name, kinds in (("read_set", {"read"}), ("write_set", {"write"}), ("rmw_set", {"rmw"}), ("release_set", {"release"})):
        result[name] = unique_refs(op for op in members if str(op["access_kind"]) in kinds)
    result["touched_records"] = unique_refs(members)
    return result


def make_group(transaction_type: str, members: list[dict[str, Any]], group_index: int) -> dict[str, Any]:
    if transaction_type not in TRANSACTION_CONTRACT or not same_head_checkpoint(members):
        raise AssertionError("invalid semantic transaction group")
    first = members[0]
    sets = group_record_sets(members)
    return {
        "transaction_group_index": group_index,
        "transaction_type": transaction_type,
        "phase": str(first["phase"]), "logical_checkpoint": int(first["logical_checkpoint"]),
        "layer": int(first["layer"]), "kv_head": int(first["kv_head"]),
        "member_record_node_indices": [int(item["_node_index"]) for item in members],
        "member_primitive_sequences": [list(primitive_sequence(item)) for item in members],
        "member_record_node_count": len(members),
        "semantic_atomicity_only": True,
        "commit_linearization_boundary": TRANSACTION_CONTRACT[transaction_type]["commit_boundary"],
        **sets,
        "touched_record_count": len(sets["touched_records"]),
    }


def build_groups(ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Partition every fixed record node into one closed semantic transaction."""
    indexed = [{**op, "_node_index": index} for index, op in enumerate(ops)]
    groups: list[dict[str, Any]] = []
    i = 0
    while i < len(indexed):
        current = indexed[i]
        sequence = primitive_sequence(current)
        if sequence == ("span_create",):
            members = indexed[i:i + 2]
            if len(members) != 2 or primitive_sequence(members[1]) != ("ownership_link",) or not same_head_checkpoint(members):
                raise AssertionError("span create must have an adjacent ownership-link commit partner")
            if (members[0]["source"], members[0]["span_id"], members[0]["birth_opportunity"], members[0]["within_head_sequence_start"]) != (members[1]["source"], members[1]["span_id"], members[1]["birth_opportunity"], members[1]["within_head_sequence_start"]):
                raise AssertionError("admission create/link identity mismatch")
            groups.append(make_group("admission_create", members, len(groups))); i += 2; continue
        if sequence != ("source_head_metadata_read",):
            raise AssertionError(f"unrecognized transaction start: {sequence}")
        members = []
        while i < len(indexed) and primitive_sequence(indexed[i]) == ("source_head_metadata_read",):
            members.append(indexed[i]); i += 1
        if len(members) not in (1, 2) or not same_head_checkpoint(members):
            raise AssertionError("oldest selection must have one or two same-head frontier reads")
        if i < len(indexed) and primitive_sequence(indexed[i]) == ("oldest_source_compare",):
            members.append(indexed[i]); i += 1
            if len(members) != 3 or not same_head_checkpoint(members):
                raise AssertionError("source compare requires exactly two same-head frontier reads")
        elif len(members) != 1:
            raise AssertionError("two-source selection missing oldest-source comparison")
        if i >= len(indexed) or primitive_sequence(indexed[i]) != ("span_partial_dequeue", "span_head_remaining_update"):
            raise AssertionError("selection must commit to a strict same-span partial dequeue record")
        members.append(indexed[i]); i += 1
        terminal = i < len(indexed) and primitive_sequence(indexed[i]) == ("span_release",)
        if terminal:
            members.extend(indexed[i:i + 2]); i += 2
            if len(members) < 2 or primitive_sequence(members[-1]) != ("ownership_unlink",):
                raise AssertionError("span release requires adjacent ownership unlink")
        if i >= len(indexed) or primitive_sequence(indexed[i]) != ("source_head_update",):
            raise AssertionError("dequeue commit requires frontier update")
        members.append(indexed[i]); i += 1
        if not same_head_checkpoint(members):
            raise AssertionError("dequeue transaction crossed head/checkpoint boundary")
        partial = members[-2 if not terminal else -4]
        span_id, source = partial["span_id"], partial["source"]
        mutation_members = [item for item in members if primitive_sequence(item) != ("source_head_metadata_read",) and primitive_sequence(item) != ("oldest_source_compare",)]
        if any(item.get("span_id") != span_id or item.get("source") != source for item in mutation_members):
            raise AssertionError("dequeue transaction source/span mismatch")
        groups.append(make_group("dequeue_terminal" if terminal else "dequeue_nonterminal", members, len(groups)))
    if sum(group["member_record_node_count"] for group in groups) != len(indexed):
        raise AssertionError("record nodes do not partition into transaction groups")
    return groups


class SemanticReplay:
    """Minimal transactional state used only to prove group visibility boundaries."""
    def __init__(self) -> None:
        self.spans: dict[int, tuple[str, int, int, int, int]] = {}
        self.owners: dict[int, tuple[str, int, int]] = {}
        self.queues: dict[tuple[int, int, str], deque[int]] = defaultdict(deque)

    def _assert_consistent(self) -> None:
        if set(self.spans) != set(self.owners):
            raise AssertionError("committed metadata has span/ownership inconsistency")
        for (layer, head, source), queue in self.queues.items():
            if any(span_id not in self.spans or self.spans[span_id][0] != source for span_id in queue):
                raise AssertionError("committed source queue references absent or foreign span")

    def commit(self, group: dict[str, Any], members: list[dict[str, Any]]) -> None:
        first = members[0]
        typ = group["transaction_type"]
        if typ == "admission_create":
            span_id = int(first["span_id"]); key = (int(first["layer"]), int(first["kv_head"]), str(first["source"]))
            if span_id in self.spans:
                raise AssertionError("duplicate committed span")
            self.spans[span_id] = (str(first["source"]), int(first["birth_opportunity"]), int(first["within_head_sequence_start"]), key[0], key[1])
            self.owners[span_id] = key; self.queues[key].append(span_id)
        else:
            partial = next(item for item in members if "span_partial_dequeue" in primitive_sequence(item))
            span_id = int(partial["span_id"]); key = (int(partial["layer"]), int(partial["kv_head"]), str(partial["source"]))
            if span_id not in self.spans or not self.queues[key] or self.queues[key][0] != span_id:
                raise AssertionError("dequeue does not target source-front span")
            read_sources = {str(item["source"]) for item in members if primitive_sequence(item) == ("source_head_metadata_read",)}
            active_sources = {source for source in ("private", "shared") if self.queues[(key[0], key[1], source)]}
            if read_sources != active_sources:
                raise AssertionError("dequeue read-set does not match committed active source fronts")
            candidates = [self.spans[queue[0]] for source in ("private", "shared") if (queue := self.queues[(key[0], key[1], source)])]
            if candidates and min(candidates, key=lambda item: (item[1], item[2]))[1:3] != self.spans[span_id][1:3]:
                raise AssertionError("dequeue group violates canonical oldest span order")
            if typ == "dequeue_terminal":
                self.queues[key].popleft(); del self.spans[span_id]; del self.owners[span_id]
        self._assert_consistent()


def negative_controls() -> dict[str, Any]:
    """Deliberately expose partial multi-record updates; both must be invalid."""
    admission_pending_without_owner = {"spans": {7}, "owners": set()}
    terminal_owner_without_span = {"spans": set(), "owners": {7}, "frontier": {7}}
    failures = {
        "split_admission_create_after_span_write": "pending_span_without_ownership_link" if admission_pending_without_owner["spans"] != admission_pending_without_owner["owners"] else None,
        "split_terminal_release_after_span_release": "ownership_or_frontier_references_released_span" if terminal_owner_without_span["spans"] != terminal_owner_without_span["owners"] or terminal_owner_without_span["frontier"] - terminal_owner_without_span["spans"] else None,
    }
    if not all(failures.values()):
        raise AssertionError("negative control did not expose semantic inconsistency")
    return {"status": "rejected_as_semantically_observable_partial_state", "failures": failures}


def path_indices(ops: list[dict[str, Any]], curve: str, phase: str) -> list[int]:
    """Mirror A4.7.0 deterministic maximum-work path, retaining node ids."""
    nodes, _ = dependencies(ops, curve)
    selected = {node["index"] for node in nodes if node["phase"] == phase}
    work: dict[int, int] = {}; count: dict[int, int] = {}; predecessor: dict[int, int | None] = {}
    for node in nodes:
        index = node["index"]
        if index not in selected:
            continue
        options = [(0, 0, None)] + [(work[parent], count[parent], parent) for _, parent in node["edges"] if parent in selected]
        parent_work, parent_count, parent = max(options, key=lambda item: (item[0], item[1], -(item[2] if item[2] is not None else -1)))
        work[index] = int(node["weight"]) + parent_work; count[index] = 1 + parent_count; predecessor[index] = parent
    if not work:
        return []
    cursor = max(work, key=lambda index: (work[index], count[index], -index)); output = []
    while cursor is not None:
        output.append(cursor); cursor = predecessor[cursor]
    return list(reversed(output))


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    items = sorted(values)
    def pct(fraction: float) -> float | int | None:
        return items[int((len(items) - 1) * fraction)] if items else None
    return {"count": len(items), "min": min(items) if items else None, "p50": pct(.50), "p95": pct(.95), "p99": pct(.99), "max": max(items) if items else None, "sum": sum(items)}


class Writer:
    def __init__(self, path: Path) -> None:
        self.raw = path.open("wb"); self.gz = gzip.GzipFile(filename="", mode="wb", fileobj=self.raw, mtime=0)
        self.text = io.TextIOWrapper(self.gz, encoding="utf-8", newline="\n"); self.count = 0
    def write(self, payload: dict[str, Any]) -> None:
        self.text.write(json.dumps({"schema_version": TRANSACTION_TRACE_SCHEMA, **payload}, sort_keys=True, separators=(",", ":")) + "\n"); self.count += 1
    def close(self) -> None:
        self.text.close(); self.raw.close()


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    a468220 = read_completed(args.a468220_report, A468220_SCHEMA, "A4.6.8.2.2.0")
    a470 = read_completed(args.a470_report, A470_SCHEMA, "A4.7.0 _02")
    trace_sha = sha256_file(args.a468220_trace)
    if a468220.get("record_access_trace", {}).get("schema_version") != RECORD_TRACE_SCHEMA or a468220["record_access_trace"].get("sha256") != trace_sha:
        raise ValueError("A4.6.8.2.2.0 record trace hash/schema mismatch")
    if a470.get("input_artifacts", {}).get("a468220_report_sha256") != sha256_file(args.a468220_report) or a470["input_artifacts"].get("a468220_trace_sha256") != trace_sha:
        raise ValueError("A4.7.0 _02 does not hash-bind supplied record inputs")
    guards = ("a468220_and_a468221_hash_bound_contracts_validated", "fixed_record_trace_fifo_grants_source_and_order_not_rescheduled", "only_four_preregistered_dependency_edge_types_emitted", "critical_path_node_edge_lengths_and_checkpoint_low_tail_ratios_reported", "no_payload_movement_or_physical_cost_inferred")
    if not all(a470.get("semantic_guards", {}).get(name) is True for name in guards):
        raise ValueError("A4.7.0 _02 semantic guards incomplete")
    return a468220, a470


def write_context(*, context: tuple[str, str, int, str], ops: list[dict[str, Any]], writer: Writer) -> dict[str, Any]:
    groups = build_groups(ops); node_to_group = {}
    replay = SemanticReplay(); by_index = {index: op for index, op in enumerate(ops)}
    type_counts: Counter[str] = Counter(); phase_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        members = [by_index[index] for index in group["member_record_node_indices"]]
        replay.commit(group, members)
        for node in group["member_record_node_indices"]:
            if node in node_to_group: raise AssertionError("node belongs to more than one transaction group")
            node_to_group[node] = group
        type_counts[group["transaction_type"]] += 1; phase_groups[group["phase"]].append(group)
        writer.write({"anchor": context[0], "workload": context[1], "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3], **group})
    if len(node_to_group) != len(ops):
        raise AssertionError("not every dependency node has a transaction group")
    phase_rows = {}
    for phase in PHASES:
        current = phase_groups[phase]
        phase_rows[phase] = {
            "transaction_group_count": len(current),
            "dependency_node_count": sum(group["member_record_node_count"] for group in current),
            "transaction_group_nodes": distribution(group["member_record_node_count"] for group in current),
            "touched_records_per_transaction_group": distribution(group["touched_record_count"] for group in current),
            "transaction_type_counts": {name: sum(group["transaction_type"] == name for group in current) for name in TRANSACTION_CONTRACT},
            "semantic_atomicity_only": True,
        }
    path_rows = []
    for curve in CURVES:
        for phase in PHASES:
            path = path_indices(ops, curve, phase); path_groups = [node_to_group[index] for index in path]
            unique_groups = {group["transaction_group_index"]: group for group in path_groups}
            touched_instances = sum(group["touched_record_count"] for group in unique_groups.values())
            path_rows.append({
                "record_curve": curve, "phase": phase, "dependency_node_count": len(path), "transaction_group_count": len(unique_groups),
                "unique_touched_record_count": len({(item["record_type"], tuple(item["record_identity"])) for group in unique_groups.values() for item in group["touched_records"]}),
                "touched_record_instances": touched_instances,
                "transaction_groups_per_dependency_node": len(unique_groups) / len(path) if path else 0.0,
                "touched_record_instances_per_dependency_node": touched_instances / len(path) if path else 0.0,
                "touched_records_per_transaction_group": distribution(group["touched_record_count"] for group in unique_groups.values()),
                "transaction_type_counts": {name: sum(group["transaction_type"] == name for group in unique_groups.values()) for name in TRANSACTION_CONTRACT},
                "all_path_nodes_mapped_once": len(path_groups) == len(path),
            })
    return {"anchor": context[0], "workload": context[1], "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3], "transaction_type_counts": {name: type_counts[name] for name in TRANSACTION_CONTRACT}, "phase_rows": phase_rows, "critical_path_expansion_rows": path_rows}


def main() -> None:
    args = parse_args(); a468220, a470 = validate_inputs(args)
    if args.preflight_only:
        print("A4.7.1 preflight passed: A4.6.8.2.2.0/A4.7.0 _02 hash-bound contracts and guards validated; no output created."); return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True); trace_path = args.output_dir / "a471_metadata_transaction_trace.jsonl.gz"; writer = Writer(trace_path)
    current = None; ops: list[dict[str, Any]] = []; seen = set(); rows = []; record_count = 0
    try:
        with gzip.open(args.a468220_trace, "rt", encoding="utf-8") as handle:
            for line in handle:
                op = json.loads(line)
                if op.get("schema_version") != RECORD_TRACE_SCHEMA: raise ValueError("unexpected record trace schema")
                key = context_key(op)
                if current is None: current = key
                if key != current:
                    if current in seen: raise AssertionError("context reappeared after closure")
                    seen.add(current); rows.append(write_context(context=current, ops=ops, writer=writer)); current, ops = key, []
                ops.append(op); record_count += 1
        if current is not None:
            if current in seen: raise AssertionError("final context reappeared after closure")
            rows.append(write_context(context=current, ops=ops, writer=writer))
    finally:
        writer.close()
    if record_count != int(a468220["record_access_trace"]["record_count"]): raise AssertionError("record trace count mismatch")
    expected_contexts = {(row["anchor"], row["workload"], row["evaluation_horizon_append_opportunities"], row["organization_label"]) for row in a470["dependency_rows"]}
    if {tuple(row[key] for key in ("anchor", "workload", "evaluation_horizon_append_opportunities", "organization_label")) for row in rows} != expected_contexts:
        raise AssertionError("transaction contexts do not match A4.7.0 _02")
    path_rows = [item for row in rows for item in row["critical_path_expansion_rows"]]
    if not all(item["all_path_nodes_mapped_once"] for item in path_rows): raise AssertionError("critical path node mapping incomplete")
    negative = negative_controls()
    config = {"transaction_contract": TRANSACTION_CONTRACT, "expansion_definition": "fixed A4.7.0 dependency node to semantic transaction group to unique logical record identities; not a hardware access expansion", "semantic_atomicity_boundary": "a group hides all internal partial states until its declared commit/linearization boundary", "tail_extension_observed_count": 0, "boundary": "No semantic transaction group, set, record, or expansion factor is a hardware atomic operation, SRAM access, cycle, port, bank, byte, payload movement, HBM/DMA transaction, timing, latency, throughput, energy, area, capacity, architecture specification, or RTL result."}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "trace-derived logical record inputs with functional semantic-transaction replay; semantic atomicity is not hardware atomicity", "input_artifacts": {"a468220_report_sha256": sha256_file(args.a468220_report), "a468220_trace_sha256": sha256_file(args.a468220_trace), "a470_report_sha256": sha256_file(args.a470_report)}, "transaction_trace": {"schema_version": TRANSACTION_TRACE_SCHEMA, "relative_path": trace_path.name, "sha256": sha256_file(trace_path), "transaction_group_count": writer.count}, "context_rows": rows, "negative_controls": negative, "semantic_guards": {"a468220_and_a470_hash_bound_contracts_validated": True, "fixed_fifo_grants_source_ownership_and_record_order_not_rescheduled": True, "every_dependency_node_maps_to_exactly_one_transaction_group": True, "every_group_has_read_write_rmw_release_sets_and_one_commit_boundary": True, "post_commit_span_owner_source_queue_and_oldest_replay_consistent": True, "critical_path_node_group_touched_record_expansion_reported": True, "tail_extension_defined_but_zero_observed_not_synthesized": True, "split_multi_record_negative_controls_expose_observable_inconsistency": True, "semantic_atomicity_explicitly_not_hardware_atomicity": True, "no_payload_movement_or_physical_cost_inferred": True, "no_model_runtime_profiler_or_hardware_parameter_loaded": True, "no_drop_fallback_migration_backing_or_protection_action": True}}
    path = args.output_dir / "a471_metadata_transaction_contract_report.json"; path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.7.1 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} groups={writer.count} record_nodes={record_count}")


if __name__ == "__main__":
    main()
