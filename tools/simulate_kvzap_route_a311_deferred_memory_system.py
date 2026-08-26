"""Offline A3.11 byte/cycle DSE over A3.10 branch-dependent FIFO replay.

This is the first memory-system consumer that does not reuse A3.9's
``continue_admission`` state.  It applies A3.7's declared bank/burst/staging
model to the exact pre-call FIFO/page state emitted by A3.10.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a37_memory_system import layer_cost
from tools.simulate_kvzap_route_a3_hybrid_activation import verify_lifecycle_freeze
from tools.simulate_kvzap_route_a3_traffic import sha256, validate_a1


LAYER_COLUMNS = (
    "request_id", "deferred_decode_steps", "admission_flush_token_budget", "model_call", "decode_step", "layer", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "initial_full_kv_fallback", "staging_full_kv_fallback", "pending_dense_tokens", "pending_burst_count", "max_bank_burst_count", "packed_cold_allocated_slots", "packed_cold_page_count", "admission_bytes", "full_layer_bytes", "candidate_attention_bytes", "candidate_total_bytes", "full_layer_cycle_proxy", "candidate_attention_cycle_proxy", "candidate_total_cycle_proxy", "interpretation",
)
STEP_COLUMNS = (
    "request_id", "deferred_decode_steps", "admission_flush_token_budget", "model_call", "decode_step", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "full_total_bytes", "candidate_total_bytes", "net_bytes_saved", "full_total_cycle_proxy", "candidate_total_cycle_proxy", "net_cycle_proxy_saved", "initial_full_kv_layer_count", "staging_full_kv_layer_count", "max_bank_burst_count", "interpretation",
)
SUMMARY_COLUMNS = (
    "request_id", "deferred_decode_steps", "admission_flush_token_budget", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "decode_steps", "full_kv_cumulative_bytes", "candidate_cumulative_bytes", "net_bytes_saved_fraction", "full_kv_cumulative_cycle_proxy", "candidate_cumulative_cycle_proxy", "net_cycle_proxy_saved_fraction", "initial_full_kv_call_count", "staging_full_kv_call_count", "staging_full_kv_layer_count", "max_bank_burst_count", "interpretation",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.11 deferred branch memory-system DSE; never loads a model.")
    parser.add_argument("--lifecycle-dir", type=Path, required=True, help="Validated frozen A2 lifecycle directory.")
    parser.add_argument("--deferred-replay-dir", type=Path, required=True, help="Completed A3.10 exact deferred replay directory.")
    parser.add_argument("--a1-dir", type=Path, required=True, help="Completed A1 scheduler DSE; policy provenance only.")
    parser.add_argument("--a2-freeze", type=Path, default=Path("analysis/route_a2_lifecycle_freeze.json"))
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--bandwidth-bytes-per-cycle", type=float, default=2048.0)
    parser.add_argument("--throughput-ops-per-cycle", type=float, default=4096.0)
    parser.add_argument("--attention-ops-per-kv-token", type=float, default=512.0)
    parser.add_argument("--pe-count", type=int, default=4)
    parser.add_argument("--scheduler", choices=("static_head", "length_aware_head"), default="length_aware_head")
    parser.add_argument("--head-dispatch-cycles", type=float, default=4.0)
    parser.add_argument("--metadata-lookup-bytes-per-page", type=int, default=16)
    parser.add_argument("--metadata-lookup-cycles-per-page", type=float, default=1.0)
    parser.add_argument("--pending-position-bytes-per-token", type=int, default=8)
    parser.add_argument("--merge-state-bytes-per-head", type=int, default=64)
    parser.add_argument("--merge-cycles-per-head", type=float, default=4.0)
    parser.add_argument("--bank-count-points", nargs="+", type=int, default=[8, 16])
    parser.add_argument("--burst-bytes-points", nargs="+", type=int, default=[64, 128, 256])
    parser.add_argument("--bank-bytes-per-cycle-points", nargs="+", type=float, default=[32.0, 64.0])
    parser.add_argument("--pending-layouts", nargs="+", choices=("round_robin_token", "head_affine"), default=["round_robin_token"])
    parser.add_argument("--staging-capacity-tokens-per-layer-points", nargs="+", type=int, default=[8192, 16384, 32768])
    parser.add_argument("--deferred-decode-steps-points", nargs="+", type=int, help="Optional subset of A3.10 deferred-horizon variants to evaluate.")
    parser.add_argument("--admission-flush-token-budget-points", nargs="+", type=int, help="Optional subset of A3.10 service-budget variants to evaluate.")
    return parser.parse_args(argv)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def branch_total(cost: dict[str, Any], *, initial_fallback: bool, admission_bytes: int, admission_bandwidth: float) -> tuple[str, float, float, int]:
    """Apply branch semantics: initial fallback disables service; later one does not."""
    if initial_fallback:
        return "initial_full_kv", float(cost["full_bytes"]), float(cost["full_cycles"]), 0
    path = "staging_full_kv" if cost["fallback"] else "hybrid"
    return path, float(cost["hybrid_bytes"]) + admission_bytes, float(cost["hybrid_cycles"]) + admission_bytes / admission_bandwidth, admission_bytes


def validate_args(args: argparse.Namespace) -> None:
    scalars = [args.page_tokens, args.bandwidth_bytes_per_cycle, args.throughput_ops_per_cycle, args.attention_ops_per_cycle if hasattr(args, "attention_ops_per_cycle") else args.attention_ops_per_kv_token, args.pe_count, args.metadata_lookup_bytes_per_page, args.pending_position_bytes_per_token, args.merge_state_bytes_per_head]
    if min(scalars) <= 0 or args.metadata_lookup_cycles_per_page < 0 or args.merge_cycles_per_head < 0 or args.head_dispatch_cycles < 0:
        raise ValueError("invalid memory-system assumptions")
    for values in (args.bank_count_points, args.burst_bytes_points, args.bank_bytes_per_cycle_points, args.staging_capacity_tokens_per_layer_points):
        if not values or min(values) <= 0 or len(set(values)) != len(values):
            raise ValueError("hardware sweep points must be positive and unique")
    if not args.pending_layouts or len(set(args.pending_layouts)) != len(args.pending_layouts):
        raise ValueError("pending layouts must be non-empty and unique")
    for values, allow_zero in ((args.deferred_decode_steps_points, True), (args.admission_flush_token_budget_points, False)):
        if values is not None and (not values or len(set(values)) != len(values) or min(values) < (0 if allow_zero else 1)):
            raise ValueError("requested A3.10 variant subset is invalid")


def load_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    manifest_path = args.deferred_replay_dir / "deferred_replay_manifest.json"
    layer_path = args.deferred_replay_dir / "deferred_replay_layer_state.csv"
    head_path = args.deferred_replay_dir / "deferred_replay_head_progress.csv"
    if not all(path.is_file() for path in (manifest_path, layer_path, head_path)):
        raise FileNotFoundError("A3.10 manifest, layer-state, and head-progress files are required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a310-deferred-replay-1.0":
        raise ValueError("unsupported deferred replay schema")
    if Path(manifest.get("lifecycle_dir", "")) != args.lifecycle_dir:
        raise ValueError("A3.10 replay is not bound to the supplied lifecycle directory")
    expected = manifest.get("source_artifact_sha256", {})
    for key, path in {
        "lifecycle_manifest_sha256": args.lifecycle_dir / "lifecycle_manifest.json",
        "lifecycle_events_sha256": args.lifecycle_dir / "lifecycle_events.csv",
    }.items():
        if expected.get(key) != sha256(path):
            raise ValueError(f"A3.10 provenance mismatch for {path}")
    verify_lifecycle_freeze(args.a2_freeze, args.lifecycle_dir)
    validate_a1(args.a1_dir)
    lifecycle_manifest = json.loads((args.lifecycle_dir / "lifecycle_manifest.json").read_text(encoding="utf-8"))
    if int(lifecycle_manifest["page_tokens"]) != args.page_tokens:
        raise ValueError("--page-tokens must match lifecycle/replay page size")
    return manifest, lifecycle_manifest, read_csv(layer_path), read_csv(head_path)


def grouped(rows: list[dict[str, str]], *, keys: tuple[str, ...]) -> dict[tuple[Any, ...], list[dict[str, str]]]:
    result: dict[tuple[Any, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        result[tuple(int(row[key]) for key in keys)].append(row)
    return result


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    manifest, lifecycle, layer_rows, head_rows = load_inputs(args)
    layer_by = grouped(layer_rows, keys=("deferred_decode_steps", "admission_flush_token_budget", "model_call", "layer"))
    head_by = grouped(head_rows, keys=("deferred_decode_steps", "admission_flush_token_budget", "model_call", "layer"))
    # Avoid rescanning every recorded layer state for every decode call and
    # hardware point: the full LongGov sweep has tens of thousands of rows.
    layers_by_variant_call: dict[tuple[int, int, int], list[tuple[tuple[Any, ...], list[dict[str, str]]]]] = defaultdict(list)
    for key, rows in layer_by.items():
        layers_by_variant_call[key[:3]].append((key, rows))
    for rows in layers_by_variant_call.values():
        rows.sort(key=lambda item: item[0][3])
    variants = sorted({key[:2] for key in layer_by})
    if args.deferred_decode_steps_points is not None:
        variants = [item for item in variants if item[0] in args.deferred_decode_steps_points]
    if args.admission_flush_token_budget_points is not None:
        variants = [item for item in variants if item[1] in args.admission_flush_token_budget_points]
    if not variants:
        raise ValueError("requested A3.11 variant subset is absent from --deferred-replay-dir")
    kv_bytes, window = int(lifecycle["kv_bytes_per_layer_head_token"]), int(lifecycle["sliding_window"])
    output_layers: list[dict[str, Any]] = []
    output_steps: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for banks in args.bank_count_points:
        for burst in args.burst_bytes_points:
            for bank_rate in args.bank_bytes_per_cycle_points:
                for layout in args.pending_layouts:
                    for capacity in args.staging_capacity_tokens_per_layer_points:
                        for deferred, budget in variants:
                            calls = sorted(key[2] for key in layers_by_variant_call if key[:2] == (deferred, budget))
                            state: dict[tuple[int, int], tuple[int, int, int, int]] = {}
                            totals = {"full_bytes": 0.0, "candidate_bytes": 0.0, "full_cycles": 0.0, "candidate_cycles": 0.0}
                            initial_calls: set[int] = set()
                            staging_calls: set[int] = set()
                            staging_layers = max_bursts = 0
                            for step, call in enumerate(calls, start=1):
                                step_full_b = step_candidate_b = step_full_c = step_candidate_c = 0.0
                                initial_layers = staging_this_step = burst_this_step = 0
                                for key, layer_row in layers_by_variant_call[(deferred, budget, call)]:
                                    if len(layer_row) != 1:
                                        raise ValueError("A3.10 layer state is not unique")
                                    layer_row = layer_row[0]
                                    heads = head_by.get(key, [])
                                    if not heads:
                                        raise ValueError("A3.10 layer state has no matching head rows")
                                    layer = int(layer_row["layer"])
                                    pending = {int(row["kv_head"]): int(row["pending_tokens_before"]) for row in heads}
                                    packed = {head: state.get((layer, head), (0, 0, 0, 0))[:3] for head in pending}
                                    cost = layer_cost(cache_tokens=int(layer_row["cache_tokens_after"]), pending_by_head=pending, packed_by_head=packed, kv_bytes=kv_bytes, window=window, bank_count=banks, burst_bytes=burst, bank_bytes_per_cycle=bank_rate, layout=layout, capacity=capacity, bandwidth=args.bandwidth_bytes_per_cycle, throughput=args.throughput_ops_per_cycle, ops_per_token=args.attention_ops_per_kv_token, metadata_bytes=args.metadata_lookup_bytes_per_page, metadata_cycles=args.metadata_lookup_cycles_per_page, position_bytes=args.pending_position_bytes_per_token, merge_bytes=args.merge_state_bytes_per_head, merge_cycles=args.merge_cycles_per_head, pe_count=args.pe_count, scheduler=args.scheduler, head_dispatch_cycles=args.head_dispatch_cycles)
                                    initial = layer_row["fallback_full_kv"] == "True"
                                    admission = int(layer_row["admission_source_gather_bytes"]) + int(layer_row["admission_packed_kv_bytes"]) + int(layer_row["admission_position_metadata_bytes"]) + int(layer_row["new_page_allocations"]) * int(lifecycle["metadata_bytes_per_cold_page"])
                                    path, candidate_b, candidate_c, charged_admission = branch_total(cost, initial_fallback=initial, admission_bytes=admission, admission_bandwidth=args.bandwidth_bytes_per_cycle)
                                    step_full_b += cost["full_bytes"]; step_candidate_b += candidate_b
                                    step_full_c += cost["full_cycles"]; step_candidate_c += candidate_c
                                    initial_layers += int(initial); staging_this_step += int(path == "staging_full_kv")
                                    burst_this_step = max(burst_this_step, int(cost["max_bank_bursts"]))
                                    output_layers.append({"request_id": lifecycle["request_id"], "deferred_decode_steps": deferred, "admission_flush_token_budget": budget, "model_call": call, "decode_step": step, "layer": layer, "bank_count": banks, "burst_bytes": burst, "bank_bytes_per_cycle": bank_rate, "pending_layout": layout, "staging_capacity_tokens_per_layer": capacity, "initial_full_kv_fallback": initial, "staging_full_kv_fallback": path == "staging_full_kv", "pending_dense_tokens": cost["pending"], "pending_burst_count": cost["bursts"], "max_bank_burst_count": cost["max_bank_bursts"], "packed_cold_allocated_slots": sum(value[0] for value in packed.values()), "packed_cold_page_count": sum(value[1] for value in packed.values()), "admission_bytes": charged_admission, "full_layer_bytes": cost["full_bytes"], "candidate_attention_bytes": cost["full_bytes"] if path != "hybrid" else cost["hybrid_bytes"], "candidate_total_bytes": candidate_b, "full_layer_cycle_proxy": cost["full_cycles"], "candidate_attention_cycle_proxy": cost["full_cycles"] if path != "hybrid" else cost["hybrid_cycles"], "candidate_total_cycle_proxy": candidate_c, "interpretation": "Declared branch-consistent bank/burst/staging model; not measured memory traffic or latency."})
                                    for row in heads:
                                        head = int(row["kv_head"])
                                        state[(layer, head)] = (int(row["cold_allocated_slots_after"]), int(row["cold_page_count_after"]), int(row["cold_logical_tokens_after"]), int(row["pending_tokens_after"]))
                                totals["full_bytes"] += step_full_b; totals["candidate_bytes"] += step_candidate_b
                                totals["full_cycles"] += step_full_c; totals["candidate_cycles"] += step_candidate_c
                                if initial_layers: initial_calls.add(call)
                                if staging_this_step: staging_calls.add(call)
                                staging_layers += staging_this_step; max_bursts = max(max_bursts, burst_this_step)
                                output_steps.append({"request_id": lifecycle["request_id"], "deferred_decode_steps": deferred, "admission_flush_token_budget": budget, "model_call": call, "decode_step": step, "bank_count": banks, "burst_bytes": burst, "bank_bytes_per_cycle": bank_rate, "pending_layout": layout, "staging_capacity_tokens_per_layer": capacity, "full_total_bytes": step_full_b, "candidate_total_bytes": step_candidate_b, "net_bytes_saved": step_full_b - step_candidate_b, "full_total_cycle_proxy": step_full_c, "candidate_total_cycle_proxy": step_candidate_c, "net_cycle_proxy_saved": step_full_c - step_candidate_c, "initial_full_kv_layer_count": initial_layers, "staging_full_kv_layer_count": staging_this_step, "max_bank_burst_count": burst_this_step, "interpretation": "Declared branch-consistent bank/burst/staging model; not measured memory traffic or latency."})
                            summaries.append({"request_id": lifecycle["request_id"], "deferred_decode_steps": deferred, "admission_flush_token_budget": budget, "bank_count": banks, "burst_bytes": burst, "bank_bytes_per_cycle": bank_rate, "pending_layout": layout, "staging_capacity_tokens_per_layer": capacity, "decode_steps": len(calls), "full_kv_cumulative_bytes": totals["full_bytes"], "candidate_cumulative_bytes": totals["candidate_bytes"], "net_bytes_saved_fraction": (totals["full_bytes"] - totals["candidate_bytes"]) / totals["full_bytes"], "full_kv_cumulative_cycle_proxy": totals["full_cycles"], "candidate_cumulative_cycle_proxy": totals["candidate_cycles"], "net_cycle_proxy_saved_fraction": (totals["full_cycles"] - totals["candidate_cycles"]) / totals["full_cycles"], "initial_full_kv_call_count": len(initial_calls), "staging_full_kv_call_count": len(staging_calls), "staging_full_kv_layer_count": staging_layers, "max_bank_burst_count": max_bursts, "interpretation": "Modeled deferred-admission branch only; not sparse-attention execution, HBM traffic, allocator measurement, latency, throughput, or generation equivalence."})
    provenance = {"a2_freeze_sha256": sha256(args.a2_freeze), "deferred_replay_manifest_sha256": sha256(args.deferred_replay_dir / "deferred_replay_manifest.json"), "deferred_replay_layer_state_sha256": sha256(args.deferred_replay_dir / "deferred_replay_layer_state.csv"), "deferred_replay_head_progress_sha256": sha256(args.deferred_replay_dir / "deferred_replay_head_progress.csv")}
    return output_layers, output_steps, summaries, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    validate_args(args)
    layers, steps, summaries, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "deferred_memory_system_layer_results.csv", layers, LAYER_COLUMNS)
    write_csv(args.output_dir / "deferred_memory_system_step_results.csv", steps, STEP_COLUMNS)
    write_csv(args.output_dir / "deferred_memory_system_summary.csv", summaries, SUMMARY_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a311-deferred-memory-system-dse-1.0", "git_commit": get_git_commit(), "lifecycle_dir": str(args.lifecycle_dir), "deferred_replay_dir": str(args.deferred_replay_dir), "a1_dir": str(args.a1_dir), "source_artifact_sha256": provenance, "assumptions": vars(args), "state_timing": "A3.10's pre-call FIFO/page state supplies attention cost. Initial fallback performs no service; after activation, post-attention service is charged even if staging forces that call's attention read to Full KV.", "boundaries": ["This is a declared byte/cycle model, not a DRAM/HBM counter, allocator measurement, latency/throughput result, sparse-attention execution, or policy-on generation result.", "A3.10 position order determines FIFO/page state; pending bank placement remains A3.7's declared layout proxy."]}
    manifest["assumptions"].update({"lifecycle_dir": str(args.lifecycle_dir), "deferred_replay_dir": str(args.deferred_replay_dir), "a1_dir": str(args.a1_dir), "a2_freeze": str(args.a2_freeze)})
    (args.output_dir / "deferred_memory_system_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"Route-A3.11 modeled {len(summaries)} summaries, {len(steps)} steps, and {len(layers)} layer rows: {args.output_dir}")


if __name__ == "__main__":
    main()
