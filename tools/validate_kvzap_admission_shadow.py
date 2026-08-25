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
    manifest_path, tasks_path, final_path = (shadow_dir / "admission_shadow_manifest.json", shadow_dir / "admission_shadow_tasks.csv", shadow_dir / "admission_shadow_final_state.csv")
    if not all(path.is_file() for path in (manifest_path, tasks_path, final_path)):
        raise FileNotFoundError("A3.5 requires manifest, task, and final-state CSVs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a35-admission-shadow-1.0":
        raise ValueError("Unsupported A3.5 schema")
    if not all(manifest.get("trace_equivalence", {}).get(key) for key in ("answers_identical", "lifecycle_digests_identical", "shadow_semantic_digests_identical")):
        raise ValueError("A3.5 equivalence guard failed")
    lifecycle_path = shadow_dir / "lifecycle_events.csv"
    if not lifecycle_path.is_file():
        raise FileNotFoundError("A3.5 requires its recorded lifecycle_events.csv")
    tasks, final = list(csv.DictReader(tasks_path.open())), list(csv.DictReader(final_path.open()))
    lifecycle = {(row["model_call"], row["layer"], row["kv_head"]): row for row in csv.DictReader(lifecycle_path.open())}
    totals: dict[tuple[int, int], int] = defaultdict(int)
    for row in tasks:
        observed = lifecycle.get((row["model_call"], row["layer"], row["kv_head"]))
        if observed is None or int(row["admitted_tokens"]) != int(observed["cold_admitted_tokens"]) or int(row["dropped_tokens"]) != int(observed["cold_dropped_tokens"]):
            raise ValueError("shadow task disposition disagrees with recorded read-only lifecycle")
        if int(row["admitted_tokens"]) + int(row["dropped_tokens"]) != int(row["matured_tokens"]):
            raise ValueError("shadow task maturity disposition disagrees")
        if int(row["packed_kv_bytes"]) != int(row["admitted_tokens"]) * int(manifest["config"]["kv_bytes_per_layer_head_token"]):
            raise ValueError("shadow packed bytes disagree with declared K/V bytes/token")
        totals[(int(row["layer"]), int(row["kv_head"]))] += int(row["admitted_tokens"])
    for row in final:
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
