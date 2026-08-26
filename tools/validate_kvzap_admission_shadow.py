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


def validate_hybrid_head_progress(progress: list[dict[str, str]], lifecycle_rows: list[dict[str, str]], tasks: list[dict[str, str]]) -> None:
    """Validate deferred FIFO conservation for schema-1.4 per-head progress.

    A current call may pack positions decided in earlier calls.  Therefore
    `packed_admitted_tokens <= decided_admitted_tokens` is invalid: the real
    invariant is pending_after = pending_before + decided - packed.
    """
    lifecycle = {(row["model_call"], row["layer"], row["kv_head"]): row for row in lifecycle_rows}
    state: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"pending": 0, "packed": 0})
    by_batch: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    for row in sorted(progress, key=lambda item: (int(item["layer"]), int(item["kv_head"]), int(item["model_call"]))):
        identity = (row["model_call"], row["layer"], row["kv_head"])
        if identity in seen or lifecycle.get(identity) is None:
            raise ValueError("hybrid-head progress has duplicate or unknown lifecycle identity")
        seen.add(identity)
        observed = lifecycle[identity]
        if int(row["decided_admitted_tokens"]) != int(observed["cold_admitted_tokens"]):
            raise ValueError("hybrid-head progress decision disagrees with lifecycle")
        head = (row["layer"], row["kv_head"])
        previous = state[head]
        decided, packed = int(row["decided_admitted_tokens"]), int(row["packed_admitted_tokens"])
        if int(row["pending_tokens_before"]) != previous["pending"] or packed > previous["pending"] + decided or int(row["pending_tokens_after"]) != previous["pending"] + decided - packed:
            raise ValueError("hybrid-head progress violates deferred FIFO conservation")
        previous["pending"] += decided - packed
        previous["packed"] += packed
        if int(row["cold_logical_tokens_after"]) != previous["packed"] or int(row["cold_allocated_slots_after"]) < previous["packed"] or int(row["cold_page_count_after"]) < 0:
            raise ValueError("hybrid-head progress packed-page state disagrees with FIFO totals")
        by_batch[(row["model_call"], row["layer"])].append(row)
    if len(seen) != len(lifecycle):
        raise ValueError("hybrid-head progress does not cover every lifecycle row")
    for task in tasks:
        matching = by_batch[(task["model_call"], task["layer"])]
        if len(matching) != int(task["member_head_count"]) or sum(int(row["packed_admitted_tokens"]) for row in matching) != int(task["packed_admitted_tokens"]) or sum(int(row["pending_tokens_after"]) for row in matching) != int(task["pending_tokens_after"]):
            raise ValueError("hybrid-head progress disagrees with its V2 layer batch")


def validate_deferred_replay_positions(rows: list[dict[str, str]], progress: list[dict[str, str]]) -> None:
    """Validate exact retained-decision multiplicity needed for A3.10 replay."""
    expected = {(row["model_call"], row["layer"], row["kv_head"]): int(row["decided_admitted_tokens"]) for row in progress}
    observed: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for row in rows:
        key = (row["model_call"], row["layer"], row["kv_head"])
        if key not in expected:
            raise ValueError("deferred-replay positions reference an unknown head-progress row")
        observed[key].append(int(row["position"]))
    if set(observed) != {key for key, value in expected.items() if value}:
        raise ValueError("deferred-replay positions do not cover every nonempty retained decision")
    for key, count in expected.items():
        positions = observed.get(key, [])
        if len(positions) != count or len(set(positions)) != len(positions) or positions != sorted(positions):
            raise ValueError("deferred-replay positions disagree with retained decision count/order")


def validate(shadow_dir: Path) -> dict[str, int]:
    manifest_path, final_path = shadow_dir / "admission_shadow_manifest.json", shadow_dir / "admission_shadow_final_state.csv"
    if not all(path.is_file() for path in (manifest_path, final_path)):
        raise FileNotFoundError("A3.5 requires manifest and final-state CSVs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") not in {"kvzap-route-a35-admission-shadow-1.0", "kvzap-route-a35-admission-shadow-1.1", "kvzap-route-a35-admission-shadow-1.2", "kvzap-route-a35-admission-shadow-1.3", "kvzap-route-a35-admission-shadow-1.4", "kvzap-route-a35-admission-shadow-1.5"}:
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
    if manifest.get("schema_version") in {"kvzap-route-a35-admission-shadow-1.4", "kvzap-route-a35-admission-shadow-1.5"}:
        progress_path = shadow_dir / "admission_shadow_v2_head_progress.csv"
        if not progress_path.is_file():
            raise FileNotFoundError("A3.6 hybrid-head progress CSV is missing")
        progress = list(csv.DictReader(progress_path.open()))
        validate_hybrid_head_progress(progress, lifecycle_rows, tasks)
        if manifest.get("schema_version") == "kvzap-route-a35-admission-shadow-1.5":
            positions_path = shadow_dir / "admission_shadow_v3_deferred_replay_positions.csv"
            if not positions_path.is_file():
                raise FileNotFoundError("A3.10 deferred-replay position CSV is missing")
            validate_deferred_replay_positions(list(csv.DictReader(positions_path.open())), progress)
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
