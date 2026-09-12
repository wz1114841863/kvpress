"""A4.2.12 reconstructs Route-A semantic dispatch epochs from A428 events.

The accepted event stream is deliberately timestamp-free.  This tool therefore
does not manufacture ready times: it records the observed Python invocation
order and constructs only the dependency-preserving, layer-scoped arrival
epochs that a later *modeled* scheduler may use.
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

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4212-dispatch-epoch-evidence-1.0"
A428_SCHEMA = "kvzap-route-a428-matched-horizon-workload-stability-1.0"
EPOCH_SCHEMA = "kvzap-route-a4212-dispatch-epochs-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.2.12 trace-derived dispatch-order reconstruction; no timing or hardware measurement."
    )
    parser.add_argument("--a428-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_complete(path: Path, schema: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != schema or data.get("status") != "complete":
        raise ValueError(f"invalid completed input: {path}")
    return data


def read_events(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def write_epochs(path: Path, rows: list[dict[str, Any]]) -> str:
    # Stable gzip headers keep SHA-256 reproducible across hosts and reruns.
    with path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
        with io.TextIOWrapper(compressed, encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    return sha256(path)


def source_signature(event: dict[str, Any]) -> tuple[tuple[str, str, int, int | None, int | None], ...]:
    return tuple(
        (str(row["source"]), str(row["outcome"]), int(row["record_count"]), row["first_position"], row["last_position"])
        for row in event["source_decisions"]
    )


def reconstruct(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not events:
        raise ValueError("event stream is empty")
    epoch_rows: list[dict[str, Any]] = []
    forward_epoch = 0
    dispatch_epoch = -1
    prior_layer: int | None = None
    prior_segment: tuple[int, int, str, int | None] | None = None
    segments: dict[int, list[dict[str, Any]]] = defaultdict(list)
    forward_layers: dict[int, list[int]] = defaultdict(list)

    for expected, event in enumerate(events):
        if int(event.get("logical_event_sequence", -1)) != expected:
            raise ValueError("logical event sequence is not contiguous")
        layer = int(event["layer"])
        if prior_layer is not None and layer < prior_layer:
            forward_epoch += 1
            prior_segment = None
        segment = (forward_epoch, layer, str(event["phase"]), event.get("cache_position"))
        if segment != prior_segment:
            dispatch_epoch += 1
            prior_segment = segment
        row = {
            "logical_event_sequence": expected,
            "forward_epoch": forward_epoch,
            "layer_dispatch_epoch": dispatch_epoch,
            "source_ready_epoch": dispatch_epoch,
            "layer": layer,
            "kv_head": int(event["kv_head"]),
            "query_head": int(event["query_head"]),
            "phase": event["phase"],
            "cache_position": event.get("cache_position"),
        }
        epoch_rows.append(row)
        segments[dispatch_epoch].append(event)
        forward_layers[forward_epoch].append(layer)
        prior_layer = layer

    same_group_pairs = same_layer_cross_group_pairs = 0
    segment_sizes = Counter()
    for dispatch, rows in segments.items():
        first = rows[0]
        if any((int(row["layer"]), row["phase"], row.get("cache_position")) != (int(first["layer"]), first["phase"], first.get("cache_position")) for row in rows):
            raise ValueError(f"dispatch epoch {dispatch} mixes layer/phase/cache-position")
        by_head: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_head[int(row["kv_head"])].append(row)
        for head_rows in by_head.values():
            if len({int(row["query_head"]) for row in head_rows}) != len(head_rows):
                raise ValueError("same KV head has duplicated query-head event")
            if len({source_signature(row) for row in head_rows}) != 1:
                raise ValueError("same KV-head-group does not share one source snapshot")
            same_group_pairs += len(head_rows) * (len(head_rows) - 1) // 2
        total_pairs = len(rows) * (len(rows) - 1) // 2
        same_layer_cross_group_pairs += total_pairs - sum(len(head_rows) * (len(head_rows) - 1) // 2 for head_rows in by_head.values())
        segment_sizes[len(rows)] += 1

    cross_layer_edges = 0
    for layers in forward_layers.values():
        if any(left > right for left, right in zip(layers, layers[1:])):
            raise ValueError("layer order regressed inside one reconstructed forward epoch")
        cross_layer_edges += sum(left < right for left, right in zip(layers, layers[1:]))
    summary = {
        "event_count": len(events),
        "forward_epoch_count": len(forward_layers),
        "layer_dispatch_epoch_count": len(segments),
        "dispatch_epoch_event_count_histogram": {str(key): value for key, value in sorted(segment_sizes.items())},
        "same_layer_same_kv_head_group_semantic_pair_count": same_group_pairs,
        "same_layer_cross_kv_head_group_semantic_pair_count": same_layer_cross_group_pairs,
        "cross_layer_observed_order_edge_count": cross_layer_edges,
        "observed_reference_dispatch_is_serial": True,
        "same_layer_semantic_overlap_is_dependency_eligibility_only": True,
        "cross_layer_semantic_overlap_allowed": False,
    }
    return epoch_rows, summary


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a428 = load_complete(args.a428_report, A428_SCHEMA)
    if not a428.get("observational_guards", {}).get("shared_actual_policy_decode_calls"):
        raise ValueError("A428 matched actual policy decode-call guard is absent")
    per_workload: dict[str, Any] = {}
    args.output_dir.mkdir(parents=True)
    for workload, source in a428["per_workload"].items():
        event_path = args.a428_report.parent / workload / "ordered_events" / "a424_ordered_logical_attention_events.jsonl.gz"
        if sha256(event_path) != source["logical_event_sha256"]:
            raise ValueError(f"event hash mismatch: {workload}")
        rows, summary = reconstruct(read_events(event_path))
        output_path = args.output_dir / f"{workload}_dispatch_epochs.jsonl.gz"
        per_workload[workload] = {
            "ordered_event_path": str(event_path),
            "ordered_event_sha256": sha256(event_path),
            "dispatch_epoch_artifact": {"schema_version": EPOCH_SCHEMA, "path": output_path.name, "sha256": write_epochs(output_path, rows), "row_count": len(rows)},
            "summary": summary,
        }
    config = {"a428_report": str(args.a428_report), "a428_report_sha256": sha256(args.a428_report)}
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config), "per_workload": per_workload,
        "observational_guards": {
            "a428_hashes_verified": True, "contiguous_logical_sequence_verified": True,
            "reconstructed_forward_epoch_layer_order_verified": True,
            "same_kv_head_group_source_snapshot_consistency_verified": True,
            "no_timestamps_or_hardware_parameters_recorded": True,
        },
        "boundaries": [
            "The event order is trace-derived from the semantically guarded A428 Route-A reference. It records Python-reference invocation order, not source completion, arrival, timing, queue/FIFO occupancy, cycles, latency, throughput, HBM, or hardware behavior.",
            "source_ready_epoch is a dependency-preserving constructed arrival label: same-layer events share an immutable source snapshot after append, while cross-layer events remain ordered. It is not an observed concurrent execution interval or a hardware dispatch timestamp.",
        ],
    }
    path = args.output_dir / "a4212_dispatch_epoch_evidence_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.12 completed: {path}")


if __name__ == "__main__":
    main()
