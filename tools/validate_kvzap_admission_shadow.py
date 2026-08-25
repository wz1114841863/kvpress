"""Validate Route-A3.5 shadow output without loading a model."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Route-A3.5 admission-shadow artifacts without model execution.")
    parser.add_argument("shadow_dir", type=Path)
    return parser.parse_args()


def validate(shadow_dir: Path) -> dict[str, int]:
    manifest_path, final_path = shadow_dir / "admission_shadow_manifest.json", shadow_dir / "admission_shadow_final_state.csv"
    if not all(path.is_file() for path in (manifest_path, final_path)):
        raise FileNotFoundError("A3.5 requires manifest and final-state CSVs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") not in {"kvzap-route-a35-admission-shadow-1.0", "kvzap-route-a35-admission-shadow-1.1", "kvzap-route-a35-admission-shadow-1.2", "kvzap-route-a35-admission-shadow-1.3"}:
        raise ValueError("Unsupported A3.5 schema")
    if not all(manifest.get("trace_equivalence", {}).get(key) for key in ("answers_identical", "lifecycle_digests_identical", "shadow_semantic_digests_identical")):
        raise ValueError("A3.5 equivalence guard failed")
    lifecycle_path = shadow_dir / "lifecycle_events.csv"
    if not lifecycle_path.is_file():
        raise FileNotFoundError("A3.5 requires its recorded lifecycle_events.csv")
    batch_mode = manifest.get("submission_mode", "per_head")
    v2_mode = batch_mode.endswith("_v2")
    tasks_path = shadow_dir / ("admission_shadow_v2_tasks.csv" if v2_mode else "admission_shadow_batch_tasks.csv" if batch_mode == "per_layer_batch" else "admission_shadow_tasks.csv")
    if not tasks_path.is_file():
        raise FileNotFoundError("A3.5 task CSV for declared submission mode is missing")
    tasks, final = list(csv.DictReader(tasks_path.open())), list(csv.DictReader(final_path.open()))
    lifecycle_rows = list(csv.DictReader(lifecycle_path.open()))
    lifecycle = {(row["model_call"], row["layer"], row["kv_head"]): row for row in lifecycle_rows}
    lifecycle_batches: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in lifecycle_rows:
        lifecycle_batches[(row["model_call"], row["layer"])].append(row)
    totals: dict[tuple[int, int], int] = defaultdict(int)
    for row in tasks:
        if v2_mode:
            if batch_mode == "per_layer_batch_v2":
                matching = lifecycle_batches[(row["model_call"], row["layer"])]
                if len(matching) != int(row["member_head_count"]) or int(row["decided_admitted_tokens"]) != sum(int(item["cold_admitted_tokens"]) for item in matching):
                    raise ValueError("A3.5b-V2 batch decisions disagree with lifecycle")
                for item in matching:
                    totals[(int(item["layer"]), int(item["kv_head"]))] += 0
            else:
                observed = lifecycle.get((row["model_call"], row["layer"], row["kv_head"]))
                if observed is None or int(row["decided_admitted_tokens"]) != int(observed["cold_admitted_tokens"]):
                    raise ValueError("A3.5b-V2 head decisions disagree with lifecycle")
            continue
        if batch_mode == "per_layer_batch":
            matching = lifecycle_batches[(row["model_call"], row["layer"])]
            if len(matching) != int(row["member_head_count"]) or int(row["admitted_tokens"]) != sum(int(item["cold_admitted_tokens"]) for item in matching) or int(row["dropped_tokens"]) != sum(int(item["cold_dropped_tokens"]) for item in matching):
                raise ValueError("batched shadow disposition disagrees with recorded read-only lifecycle")
            for item in matching:
                totals[(int(item["layer"]), int(item["kv_head"]))] += int(item["cold_admitted_tokens"])
            continue
        observed = lifecycle.get((row["model_call"], row["layer"], row["kv_head"]))
        if observed is None or int(row["admitted_tokens"]) != int(observed["cold_admitted_tokens"]) or int(row["dropped_tokens"]) != int(observed["cold_dropped_tokens"]):
            raise ValueError("shadow task disposition disagrees with recorded read-only lifecycle")
        if int(row["admitted_tokens"]) + int(row["dropped_tokens"]) != int(row["matured_tokens"]):
            raise ValueError("shadow task maturity disposition disagrees")
        if int(row["packed_kv_bytes"]) != int(row["admitted_tokens"]) * int(manifest["config"]["kv_bytes_per_layer_head_token"]):
            raise ValueError("shadow packed bytes disagree with declared K/V bytes/token")
        totals[(int(row["layer"]), int(row["kv_head"]))] += int(row["admitted_tokens"])
    if v2_mode:
        packed_total = sum(int(row["packed_admitted_tokens"]) for row in tasks)
        if packed_total != sum(int(row["cold_logical_tokens"]) for row in final):
            raise ValueError("A3.5b-V2 final state disagrees with packed admissions")
    for row in final:
        if v2_mode:
            if int(row["cold_allocated_slots"]) < int(row["cold_logical_tokens"]):
                raise ValueError("shadow physical slots are smaller than logical tokens")
            continue
        identity = (int(row["layer"]), int(row["kv_head"]))
        if totals[identity] != int(row["cold_logical_tokens"]):
            raise ValueError("shadow final logical tokens disagree with task admissions")
        if int(row["cold_allocated_slots"]) < int(row["cold_logical_tokens"]):
            raise ValueError("shadow physical slots are smaller than logical tokens")
    return {"tasks": len(tasks), "layer_heads": len(final)}


def main() -> None:
    result = validate(parse_args().shadow_dir)
    print(f"Route-A3.5 admission shadow valid: {result['tasks']} tasks, {result['layer_heads']} layer-head final states")


if __name__ == "__main__":
    main()
