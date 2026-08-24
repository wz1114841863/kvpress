"""Offline validator for Route-A2 read-only lifecycle collector outputs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate one Route-A2 lifecycle directory without loading a model.")
    parser.add_argument("trace_dir", type=Path)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def validate(trace_dir: Path) -> dict[str, int]:
    manifest_path, events_path, final_path = (trace_dir / "lifecycle_manifest.json", trace_dir / "lifecycle_events.csv", trace_dir / "lifecycle_final_state.csv")
    if not all(path.is_file() for path in (manifest_path, events_path, final_path)):
        raise FileNotFoundError("Route-A2 trace requires lifecycle_manifest.json, lifecycle_events.csv, and lifecycle_final_state.csv")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a2-readonly-lifecycle-1.0":
        raise ValueError("Unsupported Route-A2 schema")
    equivalence = manifest.get("trace_equivalence", {})
    guards = manifest.get("observational_guards", {})
    if not equivalence.get("answers_identical") or not equivalence.get("lifecycle_digests_identical"):
        raise ValueError("Trace equivalence gate did not pass")
    if any(guards.get(key) for key in ("dms_press_used", "masked_key_indices_created", "fake_key_attention_used", "model_cache_mutated_by_collector")):
        raise ValueError("Read-only observational guard failed")
    page = int(manifest["page_tokens"])
    kv_bytes = int(manifest["kv_bytes_per_layer_head_token"])
    metadata = int(manifest["metadata_bytes_per_cold_page"])
    window = int(manifest["sliding_window"])
    events = read_csv(events_path)
    if not events:
        raise ValueError("Lifecycle event file is empty")
    grouped: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    for row in events:
        grouped[(int(row["layer"]), int(row["kv_head"]))].append(row)
    latest = {}
    for key, rows in grouped.items():
        rows.sort(key=lambda row: int(row["model_call"]))
        next_position = hot = cold = pages = 0
        for row in rows:
            start, q_len = int(row["score_start"]), int(row["q_len"])
            if start != next_position or int(row["cache_tokens_after"]) != start + q_len:
                raise ValueError(f"{key}: non-contiguous score/cache positions")
            if int(row["hot_tokens_before"]) != hot:
                raise ValueError(f"{key}: hot_tokens_before mismatch")
            matured = max(0, hot + q_len - window)
            if int(row["matured_tokens"]) != matured:
                raise ValueError(f"{key}: matured-token count mismatch")
            admitted, dropped = int(row["cold_admitted_tokens"]), int(row["cold_dropped_tokens"])
            if admitted + dropped != matured:
                raise ValueError(f"{key}: mature token did not resolve to exactly drop or admit")
            allocations = int(row["cold_page_allocations"])
            cold += admitted
            pages += allocations
            if int(row["cold_logical_tokens"]) != cold or int(row["cold_page_count"]) != pages or int(row["cold_allocated_slots"]) != pages * page:
                raise ValueError(f"{key}: packed cold state mismatch")
            if int(row["hot_to_cold_read_bytes"]) != matured * kv_bytes or int(row["cold_write_bytes"]) != admitted * kv_bytes or int(row["metadata_update_bytes"]) != allocations * metadata:
                raise ValueError(f"{key}: declared byte accounting mismatch")
            tail = int(row["tail_valid_count"])
            if not (0 <= tail <= page) or (pages == 0 and tail != 0) or (pages and tail != ((cold - 1) % page) + 1):
                raise ValueError(f"{key}: tail page state mismatch")
            next_position += q_len
            hot = min(window, hot + q_len)
        latest[key] = rows[-1]
    finals = {(int(row["layer"]), int(row["kv_head"])): row for row in read_csv(final_path)}
    if set(finals) != set(latest):
        raise ValueError("Final-state L/H coverage differs from event coverage")
    for key, row in latest.items():
        final = finals[key]
        for field in ("cold_logical_tokens", "cold_allocated_slots", "cold_page_count", "tail_valid_count"):
            if row[field] != final[field]:
                raise ValueError(f"{key}: final-state {field} differs from final event")
    observation = manifest.get("decode_lifecycle_observation")
    if observation is not None:
        phase_summary: dict[str, dict[str, int]] = {}
        first_layer = min(layer for layer, _ in grouped)
        first_layer_calls: set[tuple[str, int]] = set()
        for row in events:
            phase = row["phase"]
            actual = phase_summary.setdefault(phase, {"model_call_count": 0, "query_tokens": 0, "matured_layer_head_slots": 0, "cold_admitted_tokens": 0, "cold_dropped_tokens": 0, "cold_page_allocations": 0, "cold_page_seals": 0, "hot_to_cold_read_bytes": 0, "cold_write_bytes": 0, "metadata_update_bytes": 0})
            # One serialized row exists for each KV head.  Request-level call
            # and query-token fields must therefore use each (phase, call)
            # pair once, while the remaining counters intentionally sum L/H.
            call_key = (phase, int(row["model_call"]))
            if int(row["layer"]) == first_layer and call_key not in first_layer_calls:
                first_layer_calls.add(call_key)
                actual["model_call_count"] += 1
                actual["query_tokens"] += int(row["q_len"])
            for source, target in (("matured_tokens", "matured_layer_head_slots"), ("cold_admitted_tokens", "cold_admitted_tokens"), ("cold_dropped_tokens", "cold_dropped_tokens"), ("cold_page_allocations", "cold_page_allocations"), ("cold_page_seals", "cold_page_seals"), ("hot_to_cold_read_bytes", "hot_to_cold_read_bytes"), ("cold_write_bytes", "cold_write_bytes"), ("metadata_update_bytes", "metadata_update_bytes")):
                actual[target] += int(row[source])
        if observation.get("phase_summary") != phase_summary:
            raise ValueError("Manifest phase summary disagrees with lifecycle events")
        decode_calls = int(observation["decode_model_call_count"])
        if decode_calls != phase_summary.get("decode", {}).get("model_call_count", 0):
            raise ValueError("Observed decode model-call count disagrees with lifecycle events")
        if int(observation["pipeline_generated_token_ids_observed"]) != 1 + decode_calls:
            raise ValueError("Observed generated-token-id count disagrees with decode model-call count")
        if int(observation["answer_retokenized_token_count"]) < 0:
            raise ValueError("Retokenized answer count must be non-negative")
        if not equivalence.get("lifecycle_summaries_identical"):
            raise ValueError("Recorded and silent lifecycle summaries differ")
    return {"layers": len({layer for layer, _ in grouped}), "layer_heads": len(grouped), "events": len(events)}


def main() -> None:
    result = validate(parse_args().trace_dir)
    print(f"Route-A2 lifecycle trace valid: {result['layers']} layers, {result['layer_heads']} layer-heads, {result['events']} events")


if __name__ == "__main__":
    main()
