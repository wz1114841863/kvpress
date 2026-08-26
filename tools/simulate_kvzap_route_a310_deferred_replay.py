"""Offline Route-A3.10 branch-dependent deferred-admission FIFO replay.

The A3.9 ``continue_admission`` ledger is valid only when an attention-path
fallback does not change the admission state.  This tool instead replays the
schema-1.5 retained-position stream and evolves a separate per-head FIFO and
append-only cold-page state for each declared delayed-admission policy.

It deliberately emits state/accounting inputs, not an attention implementation
or a byte/cycle result.  A later memory-system model may consume the ledger.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a3_hybrid_activation import verify_lifecycle_freeze
from tools.validate_kvzap_admission_shadow import validate as validate_shadow
from tools.validate_kvzap_decode_lifecycle_trace import validate as validate_lifecycle


HEAD_COLUMNS = (
    "request_id", "deferred_decode_steps", "admission_flush_token_budget", "model_call", "decode_step", "layer", "kv_head", "attention_path", "decided_tokens_current_call", "pending_tokens_before", "admitted_tokens", "admitted_position_sum", "pending_tokens_after", "pending_oldest_position_after", "cold_logical_tokens_after", "cold_allocated_slots_after", "cold_page_count_after", "tail_valid_count_after", "new_page_allocations",
)
LAYER_COLUMNS = (
    "request_id", "deferred_decode_steps", "admission_flush_token_budget", "model_call", "decode_step", "layer", "attention_path", "cache_tokens_after", "decided_tokens_current_call", "pending_dense_tokens_before", "admitted_tokens", "pending_dense_tokens_after", "packed_cold_logical_tokens_after", "packed_cold_allocated_slots_after", "packed_cold_page_count_after", "new_page_allocations", "admission_source_gather_bytes", "admission_packed_kv_bytes", "admission_position_metadata_bytes", "fallback_full_kv", "interpretation",
)
SUMMARY_COLUMNS = (
    "request_id", "deferred_decode_steps", "admission_flush_token_budget", "decode_steps", "full_kv_fallback_call_count", "first_hybrid_decode_step", "decided_tokens", "packed_tokens", "pending_tokens_at_end", "position_conservation_ok", "packed_cold_allocated_slots", "packed_cold_page_count", "tail_waste_slots", "interpretation",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.10 exact deferred-admission FIFO replay; never loads a model.")
    parser.add_argument("--lifecycle-dir", type=Path, required=True, help="Validated frozen A2 lifecycle directory.")
    parser.add_argument("--shadow-dir", type=Path, required=True, help="Schema-1.5 shadow with deferred-replay positions.")
    parser.add_argument("--a2-freeze", type=Path, default=Path("analysis/route_a2_lifecycle_freeze.json"))
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument("--page-tokens", type=int, default=64, help="Must match the source shadow page size.")
    parser.add_argument("--deferred-decode-steps-points", nargs="+", type=int, default=[0, 1, 2, 4, 8], help="Initial decode calls that use Full-KV and perform no admission service.")
    parser.add_argument("--admission-flush-token-budget-points", nargs="+", type=int, default=[256, 512, 1024], help="Per-layer, post-attention FIFO service budget after activation.")
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def load_inputs(lifecycle_dir: Path, shadow_dir: Path, *, page_tokens: int) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    validate_lifecycle(lifecycle_dir)
    validate_shadow(shadow_dir)
    lifecycle_manifest = json.loads((lifecycle_dir / "lifecycle_manifest.json").read_text(encoding="utf-8"))
    shadow_manifest = json.loads((shadow_dir / "admission_shadow_manifest.json").read_text(encoding="utf-8"))
    if shadow_manifest.get("schema_version") != "kvzap-route-a35-admission-shadow-1.5":
        raise ValueError("A3.10 replay requires schema-1.5 position-preserving shadow evidence")
    if shadow_manifest.get("submission_mode") != "per_layer_batch_v2" or not shadow_manifest.get("record_deferred_replay_positions"):
        raise ValueError("A3.10 replay requires per_layer_batch_v2 with recorded deferred-replay positions")
    if shadow_manifest.get("request_id") != lifecycle_manifest.get("request_id"):
        raise ValueError("shadow request_id disagrees with lifecycle")
    config = shadow_manifest.get("config", {})
    if int(config.get("page_tokens", -1)) != page_tokens or int(config.get("kv_bytes_per_layer_head_token", -1)) != int(lifecycle_manifest["kv_bytes_per_layer_head_token"]):
        raise ValueError("page/cache-byte configuration disagrees with source trace")
    positions = read_csv(shadow_dir / "admission_shadow_v3_deferred_replay_positions.csv")
    lifecycle = read_csv(lifecycle_dir / "lifecycle_events.csv")
    return lifecycle, positions, lifecycle_manifest, shadow_manifest


def append_positions_by_call(rows: list[dict[str, str]]) -> dict[int, dict[tuple[int, int], list[int]]]:
    """Return exact retained decision positions by call/head, validating order."""
    result: dict[int, dict[tuple[int, int], list[int]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        result[int(row["model_call"])][(int(row["layer"]), int(row["kv_head"]))].append(int(row["position"]))
    for call in result.values():
        for values in call.values():
            if values != sorted(values) or len(values) != len(set(values)):
                raise ValueError("source position stream is not unique and ascending within a call/head")
    return result


def service_oldest_first(queues: dict[int, deque[int]], *, budget: int) -> dict[int, list[int]]:
    """Serve a layer's head FIFOs in exact global oldest-position order."""
    served: dict[int, list[int]] = defaultdict(list)
    while budget:
        candidates = [(queue[0], head) for head, queue in queues.items() if queue]
        if not candidates:
            break
        _position, head = min(candidates)
        served[head].append(queues[head].popleft())
        budget -= 1
    return served


def append_pages(*, prior_tokens: int, prior_slots: int, prior_pages: int, count: int, page_tokens: int) -> tuple[int, int, int, int]:
    """Append count records and return logical tokens, slots, pages, allocations."""
    if count == 0:
        return prior_tokens, prior_slots, prior_pages, 0
    new_tokens = prior_tokens + count
    pages = (new_tokens + page_tokens - 1) // page_tokens
    slots = pages * page_tokens
    return new_tokens, slots, pages, pages - prior_pages


def replay_variant(*, lifecycle: list[dict[str, str]], positions: dict[int, dict[tuple[int, int], list[int]]], request_id: str, kv_bytes: int, page_tokens: int, deferred_steps: int, budget: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    by_call: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in lifecycle:
        by_call[int(row["model_call"])].append(row)
    decode_calls = [call for call in sorted(by_call) if by_call[call][0]["phase"] == "decode"]
    if not decode_calls:
        raise ValueError("source lifecycle has no decode calls")
    queues: dict[tuple[int, int], deque[int]] = defaultdict(deque)
    packed: dict[tuple[int, int], tuple[int, int, int]] = {}
    head_rows: list[dict[str, Any]] = []
    layer_rows: list[dict[str, Any]] = []
    # Context/prompt decisions are already mature before decode begins.  A true
    # deferred branch must retain them in the FIFO, not silently erase them or
    # inherit the source shadow's already-packed state.
    first_decode_call = decode_calls[0]
    decided_total = packed_total = 0
    for call in sorted(value for value in by_call if value < first_decode_call):
        for key, values in positions.get(call, {}).items():
            queues[key].extend(values)
            decided_total += len(values)
    fallback_calls = 0
    first_hybrid: int | None = None
    for decode_step, call in enumerate(decode_calls, start=1):
        rows = by_call[call]
        # A deferred fallback intentionally does not enqueue/service until after
        # its Full-KV attention call.  Maturity decisions are then appended, but
        # service is disabled for the declared initial horizon.
        active = decode_step > deferred_steps
        attention_path = "hybrid_candidate" if active else "full_kv_fallback"
        fallback_calls += not active
        if active and first_hybrid is None:
            first_hybrid = decode_step
        rows_by_layer: dict[int, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            rows_by_layer[int(row["layer"])].append(row)
        for layer, layer_events in sorted(rows_by_layer.items()):
            heads = sorted(int(item["kv_head"]) for item in layer_events)
            pending_before = {head: len(queues[(layer, head)]) for head in heads}
            current = {head: positions.get(call, {}).get((layer, head), []) for head in heads}
            for head in heads:
                queues[(layer, head)].extend(current[head])
            decided = sum(len(items) for items in current.values())
            decided_total += decided
            per_layer_queues = {head: queues[(layer, head)] for head in heads}
            served = service_oldest_first(per_layer_queues, budget=budget) if active else {}
            cache_tokens = {int(item["cache_tokens_after"]) for item in layer_events}
            if len(cache_tokens) != 1:
                raise ValueError("layer/head lifecycle cache length disagrees")
            pending_after_total = packed_after = slots_after = pages_after = allocations = 0
            for head in heads:
                key = (layer, head)
                old_logical, old_slots, old_pages = packed.get(key, (0, 0, 0))
                admitted = served.get(head, [])
                logical, slots, pages, new_pages = append_pages(prior_tokens=old_logical, prior_slots=old_slots, prior_pages=old_pages, count=len(admitted), page_tokens=page_tokens)
                packed[key] = (logical, slots, pages)
                packed_total += len(admitted)
                pending_after = len(queues[key])
                pending_after_total += pending_after
                packed_after += logical
                slots_after += slots
                pages_after += pages
                allocations += new_pages
                head_rows.append({"request_id": request_id, "deferred_decode_steps": deferred_steps, "admission_flush_token_budget": budget, "model_call": call, "decode_step": decode_step, "layer": layer, "kv_head": head, "attention_path": attention_path, "decided_tokens_current_call": len(current[head]), "pending_tokens_before": pending_before[head], "admitted_tokens": len(admitted), "admitted_position_sum": sum(admitted), "pending_tokens_after": pending_after, "pending_oldest_position_after": queues[key][0] if queues[key] else "", "cold_logical_tokens_after": logical, "cold_allocated_slots_after": slots, "cold_page_count_after": pages, "tail_valid_count_after": logical % page_tokens or (page_tokens if logical else 0), "new_page_allocations": new_pages})
            admitted_total = sum(len(items) for items in served.values())
            layer_rows.append({"request_id": request_id, "deferred_decode_steps": deferred_steps, "admission_flush_token_budget": budget, "model_call": call, "decode_step": decode_step, "layer": layer, "attention_path": attention_path, "cache_tokens_after": cache_tokens.pop(), "decided_tokens_current_call": decided, "pending_dense_tokens_before": sum(pending_before.values()), "admitted_tokens": admitted_total, "pending_dense_tokens_after": pending_after_total, "packed_cold_logical_tokens_after": packed_after, "packed_cold_allocated_slots_after": slots_after, "packed_cold_page_count_after": pages_after, "new_page_allocations": allocations, "admission_source_gather_bytes": admitted_total * kv_bytes, "admission_packed_kv_bytes": admitted_total * kv_bytes, "admission_position_metadata_bytes": admitted_total * 8, "fallback_full_kv": not active, "interpretation": "Exact oldest-first FIFO/page replay state; byte fields are declared admission accounting inputs, not measured traffic."})
    pending_end = sum(len(queue) for queue in queues.values())
    slots_end = sum(value[1] for value in packed.values())
    pages_end = sum(value[2] for value in packed.values())
    summary = {"request_id": request_id, "deferred_decode_steps": deferred_steps, "admission_flush_token_budget": budget, "decode_steps": len(decode_calls), "full_kv_fallback_call_count": fallback_calls, "first_hybrid_decode_step": first_hybrid if first_hybrid is not None else "not_activated", "decided_tokens": decided_total, "packed_tokens": packed_total, "pending_tokens_at_end": pending_end, "position_conservation_ok": decided_total == packed_total + pending_end, "packed_cold_allocated_slots": slots_end, "packed_cold_page_count": pages_end, "tail_waste_slots": slots_end - packed_total, "interpretation": "Branch-dependent exact FIFO/page replay only; not sparse-attention execution, HBM traffic, latency, throughput, or generation equivalence."}
    return head_rows, layer_rows, summary


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if args.page_tokens <= 0 or not args.deferred_decode_steps_points or not args.admission_flush_token_budget_points or min(args.deferred_decode_steps_points) < 0 or min(args.admission_flush_token_budget_points) <= 0:
        raise ValueError("invalid replay sweep point")
    if len(set(args.deferred_decode_steps_points)) != len(args.deferred_decode_steps_points) or len(set(args.admission_flush_token_budget_points)) != len(args.admission_flush_token_budget_points):
        raise ValueError("replay sweep points must be unique")
    lifecycle, position_rows, lifecycle_manifest, shadow_manifest = load_inputs(args.lifecycle_dir, args.shadow_dir, page_tokens=args.page_tokens)
    verify_lifecycle_freeze(args.a2_freeze, args.lifecycle_dir)
    positions = append_positions_by_call(position_rows)
    heads: list[dict[str, Any]] = []
    layers: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for deferred in args.deferred_decode_steps_points:
        for budget in args.admission_flush_token_budget_points:
            head_rows, layer_rows, summary = replay_variant(lifecycle=lifecycle, positions=positions, request_id=lifecycle_manifest["request_id"], kv_bytes=int(lifecycle_manifest["kv_bytes_per_layer_head_token"]), page_tokens=args.page_tokens, deferred_steps=deferred, budget=budget)
            if not summary["position_conservation_ok"]:
                raise AssertionError("deferred replay violated position conservation")
            heads.extend(head_rows)
            layers.extend(layer_rows)
            summaries.append(summary)
    provenance = {"a2_freeze_sha256": sha256(args.a2_freeze), "lifecycle_manifest_sha256": sha256(args.lifecycle_dir / "lifecycle_manifest.json"), "lifecycle_events_sha256": sha256(args.lifecycle_dir / "lifecycle_events.csv"), "shadow_manifest_sha256": sha256(args.shadow_dir / "admission_shadow_manifest.json"), "position_stream_sha256": sha256(args.shadow_dir / "admission_shadow_v3_deferred_replay_positions.csv")}
    return heads, layers, summaries, {"provenance": provenance, "lifecycle_manifest": lifecycle_manifest, "shadow_manifest": shadow_manifest}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    heads, layers, summaries, meta = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "deferred_replay_head_progress.csv", heads, HEAD_COLUMNS)
    write_csv(args.output_dir / "deferred_replay_layer_state.csv", layers, LAYER_COLUMNS)
    write_csv(args.output_dir / "deferred_replay_summary.csv", summaries, SUMMARY_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a310-deferred-replay-1.0", "git_commit": get_git_commit(), "lifecycle_dir": str(args.lifecycle_dir), "shadow_dir": str(args.shadow_dir), "source_artifact_sha256": meta["provenance"], "assumptions": {"page_tokens": args.page_tokens, "deferred_decode_steps_points": args.deferred_decode_steps_points, "admission_flush_token_budget_points": args.admission_flush_token_budget_points, "state_timing": "Attention observes the pre-call branch state. Current-call retained decisions are enqueued post-attention; only activated calls perform oldest-first service."}, "output_contract": {"deferred_replay_layer_state.csv": "Per-call/layer branch state and declared admission byte inputs for a later byte/cycle model.", "deferred_replay_head_progress.csv": "Per-call/layer/head FIFO and append-only page evolution audit."}, "boundaries": ["The Full-KV fallback changes both service and future FIFO/page state, unlike A3.9 continue_admission.", "This replays retained decision positions exactly but does not execute sparse attention or establish policy-on generation equivalence.", "No field is a DRAM/HBM counter, allocator measurement, latency/throughput result, or edge-hardware calibration."]}
    (args.output_dir / "deferred_replay_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.10 replayed {len(summaries)} deferred variants, {len(layers)} layer states, and {len(heads)} head states: {args.output_dir}")


if __name__ == "__main__":
    main()
