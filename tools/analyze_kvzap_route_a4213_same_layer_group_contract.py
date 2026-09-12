"""A4.2.13 same-layer KV-head-group dispatch contract; no timing model."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4213-same-layer-group-contract-1.0"
A428 = "kvzap-route-a428-matched-horizon-workload-stability-1.0"
A4212 = "kvzap-route-a4212-dispatch-epoch-evidence-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.2.13 same-layer KV-head-group dispatch accounting; no model execution, timing, or hardware measurement.")
    parser.add_argument("--a428-report", type=Path, required=True)
    parser.add_argument("--a4212-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, schema: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != schema or value.get("status") != "complete":
        raise ValueError(f"invalid completed input: {path}")
    return value


def read_gzip(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def signature(event: dict[str, Any]) -> tuple[Any, ...]:
    return (
        tuple((row["source"], row["outcome"], int(row["record_count"]), row["first_position"], row["last_position"]) for row in event["source_decisions"]),
        int(event["packed_page_count"]), int(event["packed_full_page_count"]), int(event["packed_tail_tokens"]),
    )


def analyze(events: list[dict[str, Any]], epochs: list[dict[str, Any]]) -> dict[str, Any]:
    if len(events) != len(epochs):
        raise ValueError("event and dispatch-epoch row counts differ")
    groups: dict[tuple[int, int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for expected, (event, epoch) in enumerate(zip(events, epochs, strict=True)):
        if int(event["logical_event_sequence"]) != expected or int(epoch["logical_event_sequence"]) != expected:
            raise ValueError("logical event sequence is not contiguous")
        if (int(event["layer"]), int(event["kv_head"]), int(event["query_head"])) != (int(epoch["layer"]), int(epoch["kv_head"]), int(epoch["query_head"])):
            raise ValueError("dispatch epoch and event identity disagree")
        groups[(int(epoch["forward_epoch"]), int(epoch["layer_dispatch_epoch"]), int(event["layer"]), int(event["kv_head"]))].append(event)

    source_independent = Counter()
    source_grouped = Counter()
    source_partials = Counter()
    query_event_count = 0
    group_query_count_histogram = Counter()
    for key, rows in groups.items():
        query_heads = [int(row["query_head"]) for row in rows]
        if len(query_heads) != len(set(query_heads)):
            raise ValueError(f"duplicate query head in group {key}")
        if len({signature(row) for row in rows}) != 1:
            raise ValueError(f"same KV head-group source snapshot differs: {key}")
        group_query_count_histogram[len(rows)] += 1
        query_event_count += len(rows)
        active = {row["source"] for row in rows[0]["source_decisions"] if row["outcome"] == "partial"}
        for source in active:
            source_grouped[source] += 1
            source_independent[source] += len(rows)
            source_partials[source] += len(rows)
    independent_total = sum(source_independent.values())
    grouped_total = sum(source_grouped.values())
    return {
        "query_head_attention_events": query_event_count,
        "kv_head_group_dispatch_epochs": len(groups),
        "query_heads_per_kv_head_group_histogram": {str(k): v for k, v in sorted(group_query_count_histogram.items())},
        "per_source": {
            source: {
                "partial_attention_evaluations_unchanged": source_partials[source],
                "independent_source_dispatch_control_units": source_independent[source],
                "shared_kv_head_group_source_dispatch_control_units": source_grouped[source],
                "dispatch_control_units_elided": source_independent[source] - source_grouped[source],
            }
            for source in ("hot", "pending", "packed")
        },
        "independent_source_dispatch_control_units_total": independent_total,
        "shared_kv_head_group_source_dispatch_control_units_total": grouped_total,
        "dispatch_control_units_elided_total": independent_total - grouped_total,
        "partial_softmax_state_instances_unchanged": query_event_count,
        "online_merge_instances_unchanged": query_event_count,
        "partial_softmax_state_reuse_allowed": False,
        "online_merge_reuse_allowed": False,
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a428, a4212 = load(args.a428_report, A428), load(args.a4212_report, A4212)
    if not a4212.get("observational_guards", {}).get("same_kv_head_group_source_snapshot_consistency_verified"):
        raise ValueError("A4.2.12 same-KV-head snapshot guard is absent")
    per_workload: dict[str, Any] = {}
    for workload, a428_row in a428["per_workload"].items():
        a4212_row = a4212["per_workload"].get(workload)
        if a4212_row is None:
            raise ValueError(f"A4.2.12 workload missing: {workload}")
        event_path = args.a428_report.parent / workload / "ordered_events" / "a424_ordered_logical_attention_events.jsonl.gz"
        epoch_path = args.a4212_report.parent / a4212_row["dispatch_epoch_artifact"]["path"]
        if sha256(event_path) != a428_row["logical_event_sha256"] or sha256(event_path) != a4212_row["ordered_event_sha256"]:
            raise ValueError(f"ordered-event hash binding failed: {workload}")
        if sha256(epoch_path) != a4212_row["dispatch_epoch_artifact"]["sha256"]:
            raise ValueError(f"dispatch-epoch hash binding failed: {workload}")
        per_workload[workload] = {
            "ordered_event_sha256": sha256(event_path), "dispatch_epoch_sha256": sha256(epoch_path),
            "summary": analyze(read_gzip(event_path), read_gzip(epoch_path)),
        }
    config = {"a428_report": str(args.a428_report), "a428_sha256": sha256(args.a428_report), "a4212_report": str(args.a4212_report), "a4212_sha256": sha256(args.a4212_report)}
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "per_workload": per_workload,
        "functional_contract": {
            "shareable": "Same-(forward epoch, layer dispatch epoch, KV head) active-source/page-descriptor dispatch control only.",
            "not_shareable": "Each query head retains its own source partial-softmax state and one online merge because its query is distinct.",
        },
        "observational_guards": {"a428_and_a4212_hashes_verified": True, "same_kv_head_group_snapshot_consistency_revalidated": True, "no_mask_or_attention_semantics_modified": True, "no_hardware_parameter_selected": True},
        "boundaries": ["Dispatch-control units are logical accounting labels, not bytes, operations, cycles, latency, throughput, HBM traffic, energy, area, or hardware measurements.", "The no-reuse partial-softmax/merge rule is a functional Attention semantic contract for distinct query heads, not a measured scheduler limitation."],
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a4213_same_layer_group_contract_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.13 completed: {path}")


if __name__ == "__main__":
    main()
