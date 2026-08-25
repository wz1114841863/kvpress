"""Offline Route-A3.7 bank/burst/staging sensitivity model.

This refines the A3.6 ``pending_gather_bytes_per_token`` axis into a declared
layout model.  It does *not* observe a memory controller, HBM traffic, sparse
attention, or policy-on generation.  Full-KV generation in the source traces
remains authoritative.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a3_hybrid_activation import (
    admission_bytes,
    load_inputs,
    post_call_states,
    verify_lifecycle_freeze,
)
from tools.simulate_kvzap_route_a3_traffic import layer_cycles, sha256, validate_a1


LAYER_COLUMNS = (
    "request_id", "model_call", "decode_step", "layer", "baseline", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "pending_dense_tokens", "pending_burst_count", "pending_burst_bytes", "active_bank_count", "max_bank_burst_count", "bank_service_cycle_proxy", "fallback_full_kv", "full_layer_bytes", "hybrid_layer_bytes", "full_layer_cycle_proxy", "hybrid_layer_cycle_proxy", "admission_bytes", "hybrid_total_bytes", "hybrid_total_cycle_proxy",
)
STEP_COLUMNS = (
    "request_id", "model_call", "decode_step", "baseline", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "full_total_bytes", "baseline_total_bytes", "net_bytes_saved", "full_total_cycle_proxy", "baseline_total_cycle_proxy", "net_cycle_proxy_saved", "fallback_dense_layer_count", "max_bank_burst_count", "total_pending_burst_bytes", "interpretation",
)
SUMMARY_COLUMNS = (
    "request_id", "baseline", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "decode_steps", "full_kv_cumulative_bytes", "baseline_cumulative_bytes", "net_bytes_saved", "net_bytes_saved_fraction", "full_kv_cumulative_cycle_proxy", "baseline_cumulative_cycle_proxy", "net_cycle_proxy_saved", "net_cycle_proxy_saved_fraction", "fallback_call_count", "max_bank_burst_count", "interpretation",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.7 bank/burst/staging DSE; never loads a model.")
    parser.add_argument("--lifecycle-dir", type=Path, required=True)
    parser.add_argument("--shadow-dir", type=Path, required=True)
    parser.add_argument("--a1-dir", type=Path, required=True)
    parser.add_argument("--a2-freeze", type=Path, default=Path("analysis/route_a2_lifecycle_freeze.json"))
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--bandwidth-bytes-per-cycle", type=float, default=2048.0, help="Declared aggregate attention-read bandwidth proxy.")
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
    return parser.parse_args(argv)


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def pending_bank_profile(*, pending_by_head: dict[int, int], kv_bytes: int, bank_count: int, burst_bytes: int, layout: str) -> tuple[int, int, int, int, int]:
    """Return pending tokens, bursts, physical burst bytes, active banks, max bursts.

    Positions are not saved in schema-1.4.  This is therefore a deterministic
    declared layout proxy: token records are contiguous within each head FIFO.
    ``round_robin_token`` stripes token records; ``head_affine`` puts a head's
    records on one bank and is deliberately a pessimistic mapping reference.
    """
    loads = [0] * bank_count
    pending = bursts = 0
    for head, count in sorted(pending_by_head.items()):
        pending += count
        head_bursts = math.ceil(count * kv_bytes / burst_bytes)
        bursts += head_bursts
        for index in range(head_bursts):
            bank = index % bank_count if layout == "round_robin_token" else head % bank_count
            loads[bank] += 1
    return pending, bursts, bursts * burst_bytes, sum(value > 0 for value in loads), max(loads, default=0)


def layer_cost(*, cache_tokens: int, pending_by_head: dict[int, int], packed_by_head: dict[int, tuple[int, int, int]], kv_bytes: int, window: int, bank_count: int, burst_bytes: int, bank_bytes_per_cycle: float, layout: str, capacity: int, bandwidth: float, throughput: float, ops_per_token: float, metadata_bytes: int, metadata_cycles: float, position_bytes: int, merge_bytes: int, merge_cycles: float, pe_count: int, scheduler: str, head_dispatch_cycles: float) -> dict[str, Any]:
    pending, bursts, burst_total, active, max_bursts = pending_bank_profile(pending_by_head=pending_by_head, kv_bytes=kv_bytes, bank_count=bank_count, burst_bytes=burst_bytes, layout=layout)
    fallback = pending > capacity
    full_bytes = cache_tokens * len(pending_by_head) * kv_bytes
    full_tasks = [(head, max(cache_tokens * kv_bytes / bandwidth, cache_tokens * ops_per_token / throughput)) for head in pending_by_head]
    full_cycle = layer_cycles(full_tasks, pe_count=pe_count, policy=scheduler, head_dispatch_cycles=head_dispatch_cycles)
    if fallback:
        return {"pending": pending, "bursts": bursts, "burst_bytes": burst_total, "active_banks": active, "max_bank_bursts": max_bursts, "bank_cycles": max_bursts * burst_bytes / bank_bytes_per_cycle, "fallback": True, "full_bytes": full_bytes, "hybrid_bytes": full_bytes, "full_cycles": full_cycle, "hybrid_cycles": full_cycle}
    packed_slots = sum(item[0] for item in packed_by_head.values())
    packed_pages = sum(item[1] for item in packed_by_head.values())
    hot_slots = min(window, cache_tokens) * len(pending_by_head)
    merge_heads = sum(pending_by_head[head] > 0 and packed_by_head[head][2] > 0 for head in pending_by_head)
    hybrid_bytes = (hot_slots + packed_slots) * kv_bytes + burst_total + packed_pages * metadata_bytes + pending * position_bytes + merge_heads * merge_bytes
    bank_cycles = max_bursts * burst_bytes / bank_bytes_per_cycle
    tasks: list[tuple[int, float]] = []
    for head, count in pending_by_head.items():
        packed_slots_for_head, pages, logical = packed_by_head[head]
        head_bursts = math.ceil(count * kv_bytes / burst_bytes)
        head_bytes = (min(window, cache_tokens) + packed_slots_for_head) * kv_bytes + head_bursts * burst_bytes + pages * metadata_bytes + count * position_bytes + (merge_bytes if count and logical else 0)
        tasks.append((head, max(head_bytes / bandwidth + pages * metadata_cycles + (merge_cycles if count and logical else 0.0), (min(window, cache_tokens) + packed_slots_for_head + count) * ops_per_token / throughput)))
    scheduled_cycles = layer_cycles(tasks, pe_count=pe_count, policy=scheduler, head_dispatch_cycles=head_dispatch_cycles)
    return {"pending": pending, "bursts": bursts, "burst_bytes": burst_total, "active_banks": active, "max_bank_bursts": max_bursts, "bank_cycles": bank_cycles, "fallback": False, "full_bytes": full_bytes, "hybrid_bytes": hybrid_bytes, "full_cycles": full_cycle, "hybrid_cycles": max(scheduled_cycles, bank_cycles)}


def validate_args(args: argparse.Namespace) -> None:
    scalars = [args.page_tokens, args.bandwidth_bytes_per_cycle, args.throughput_ops_per_cycle, args.attention_ops_per_kv_token, args.pe_count, args.metadata_lookup_bytes_per_page, args.pending_position_bytes_per_token, args.merge_state_bytes_per_head]
    if min(scalars) <= 0 or args.metadata_lookup_cycles_per_page < 0 or args.head_dispatch_cycles < 0 or args.merge_cycles_per_head < 0:
        raise ValueError("invalid memory-system assumptions")
    for values in (args.bank_count_points, args.burst_bytes_points, args.bank_bytes_per_cycle_points, args.staging_capacity_tokens_per_layer_points):
        if not values or len(set(values)) != len(values) or min(values) <= 0:
            raise ValueError("bank/burst/staging sweep points must be positive and unique")
    if not args.pending_layouts or len(set(args.pending_layouts)) != len(args.pending_layouts):
        raise ValueError("pending layouts must be non-empty and unique")


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    lifecycle, progress, manifest, shadow_manifest = load_inputs(args.lifecycle_dir, args.shadow_dir)
    freeze = verify_lifecycle_freeze(args.a2_freeze, args.lifecycle_dir)
    validate_a1(args.a1_dir)
    if int(shadow_manifest["config"]["page_tokens"]) != args.page_tokens:
        raise ValueError("--page-tokens must match schema-1.4 shadow page size")
    kv_bytes, window = int(manifest["kv_bytes_per_layer_head_token"]), int(manifest["sliding_window"])
    states, lifecycle_by_call, progress_by_call = post_call_states(progress), defaultdict(list), defaultdict(list)
    for row in lifecycle:
        lifecycle_by_call[int(row["model_call"])].append(row)
    for row in progress:
        progress_by_call[int(row["model_call"])].append(row)
    calls = [call for call in sorted(lifecycle_by_call) if lifecycle_by_call[call][0]["phase"] == "decode"]
    if not calls:
        raise ValueError("memory-system DSE requires observed decode calls")
    layer_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for banks in args.bank_count_points:
        for burst in args.burst_bytes_points:
            for bank_rate in args.bank_bytes_per_cycle_points:
                for layout in args.pending_layouts:
                    for capacity in args.staging_capacity_tokens_per_layer_points:
                        totals = {name: {"bytes": 0.0, "cycles": 0.0} for name in ("full_kv", "hybrid_memory_system")}
                        fallback_calls = 0
                        max_bank_bursts = 0
                        for step, call in enumerate(calls, 1):
                            by_layer: dict[int, list[dict[str, str]]] = defaultdict(list)
                            for row in lifecycle_by_call[call]:
                                by_layer[int(row["layer"])].append(row)
                            state = states.get(call, {})
                            admission_by_layer: dict[int, int] = defaultdict(int)
                            metadata = int(shadow_manifest["config"]["metadata_bytes_per_cold_page"])
                            for row in progress_by_call[call]:
                                admission_by_layer[int(row["layer"])] += int(row["source_gather_bytes"]) + int(row["packed_kv_bytes"]) + int(row["position_metadata_bytes"]) + int(row["new_page_allocations"]) * metadata
                            full_step = hybrid_step = full_cycle = hybrid_cycle = 0.0
                            fallback_count = step_max_bursts = burst_total = 0
                            for layer, rows in sorted(by_layer.items()):
                                pending = {int(row["kv_head"]): state.get((layer, int(row["kv_head"])), {"pending": 0})["pending"] for row in rows}
                                packed = {head: (item["packed_slots"], item["packed_pages"], item["packed_logical"]) for (entry_layer, head), item in state.items() if entry_layer == layer}
                                for head in pending:
                                    packed.setdefault(head, (0, 0, 0))
                                cost = layer_cost(cache_tokens=int(rows[0]["cache_tokens_after"]), pending_by_head=pending, packed_by_head=packed, kv_bytes=kv_bytes, window=window, bank_count=banks, burst_bytes=burst, bank_bytes_per_cycle=bank_rate, layout=layout, capacity=capacity, bandwidth=args.bandwidth_bytes_per_cycle, throughput=args.throughput_ops_per_cycle, ops_per_token=args.attention_ops_per_kv_token, metadata_bytes=args.metadata_lookup_bytes_per_page, metadata_cycles=args.metadata_lookup_cycles_per_page, position_bytes=args.pending_position_bytes_per_token, merge_bytes=args.merge_state_bytes_per_head, merge_cycles=args.merge_cycles_per_head, pe_count=args.pe_count, scheduler=args.scheduler, head_dispatch_cycles=args.head_dispatch_cycles)
                                admission = admission_by_layer[layer]
                                full_step += cost["full_bytes"]
                                hybrid_step += cost["hybrid_bytes"] + admission
                                full_cycle += cost["full_cycles"]
                                hybrid_cycle += cost["hybrid_cycles"] + admission / args.bandwidth_bytes_per_cycle
                                fallback_count += int(cost["fallback"])
                                step_max_bursts = max(step_max_bursts, cost["max_bank_bursts"])
                                burst_total += cost["burst_bytes"]
                                for baseline in ("full_kv", "hybrid_memory_system"):
                                    layer_rows.append({"request_id": manifest["request_id"], "model_call": call, "decode_step": step, "layer": layer, "baseline": baseline, "bank_count": banks, "burst_bytes": burst, "bank_bytes_per_cycle": bank_rate, "pending_layout": layout, "staging_capacity_tokens_per_layer": capacity, "pending_dense_tokens": cost["pending"], "pending_burst_count": cost["bursts"], "pending_burst_bytes": cost["burst_bytes"], "active_bank_count": cost["active_banks"], "max_bank_burst_count": cost["max_bank_bursts"], "bank_service_cycle_proxy": cost["bank_cycles"], "fallback_full_kv": cost["fallback"], "full_layer_bytes": cost["full_bytes"], "hybrid_layer_bytes": cost["hybrid_bytes"], "full_layer_cycle_proxy": cost["full_cycles"], "hybrid_layer_cycle_proxy": cost["hybrid_cycles"], "admission_bytes": 0 if baseline == "full_kv" else admission, "hybrid_total_bytes": cost["full_bytes"] if baseline == "full_kv" else cost["hybrid_bytes"] + admission, "hybrid_total_cycle_proxy": cost["full_cycles"] if baseline == "full_kv" else cost["hybrid_cycles"] + admission / args.bandwidth_bytes_per_cycle})
                            if fallback_count:
                                fallback_calls += 1
                            max_bank_bursts = max(max_bank_bursts, step_max_bursts)
                            totals["full_kv"]["bytes"] += full_step
                            totals["full_kv"]["cycles"] += full_cycle
                            totals["hybrid_memory_system"]["bytes"] += hybrid_step
                            totals["hybrid_memory_system"]["cycles"] += hybrid_cycle
                            for baseline, values in (("full_kv", (full_step, full_cycle)), ("hybrid_memory_system", (hybrid_step, hybrid_cycle))):
                                step_rows.append({"request_id": manifest["request_id"], "model_call": call, "decode_step": step, "baseline": baseline, "bank_count": banks, "burst_bytes": burst, "bank_bytes_per_cycle": bank_rate, "pending_layout": layout, "staging_capacity_tokens_per_layer": capacity, "full_total_bytes": full_step, "baseline_total_bytes": values[0], "net_bytes_saved": full_step - values[0], "full_total_cycle_proxy": full_cycle, "baseline_total_cycle_proxy": values[1], "net_cycle_proxy_saved": full_cycle - values[1], "fallback_dense_layer_count": fallback_count, "max_bank_burst_count": step_max_bursts, "total_pending_burst_bytes": burst_total, "interpretation": "Declared bank/burst/staging accounting; not measured memory traffic or latency."})
                        for baseline in totals:
                            full = totals["full_kv"]
                            value = totals[baseline]
                            summaries.append({"request_id": manifest["request_id"], "baseline": baseline, "bank_count": banks, "burst_bytes": burst, "bank_bytes_per_cycle": bank_rate, "pending_layout": layout, "staging_capacity_tokens_per_layer": capacity, "decode_steps": len(calls), "full_kv_cumulative_bytes": full["bytes"], "baseline_cumulative_bytes": value["bytes"], "net_bytes_saved": full["bytes"] - value["bytes"], "net_bytes_saved_fraction": (full["bytes"] - value["bytes"]) / full["bytes"], "full_kv_cumulative_cycle_proxy": full["cycles"], "baseline_cumulative_cycle_proxy": value["cycles"], "net_cycle_proxy_saved": full["cycles"] - value["cycles"], "net_cycle_proxy_saved_fraction": (full["cycles"] - value["cycles"]) / full["cycles"], "fallback_call_count": fallback_calls, "max_bank_burst_count": max_bank_bursts, "interpretation": "Candidate memory-system model only; does not establish DRAM/HBM behavior, latency, throughput, or sparse-attention equivalence."})
    provenance = {"a2_freeze_sha256": sha256(args.a2_freeze), "a2_freeze_status": freeze.get("freeze_status"), "lifecycle_manifest_sha256": sha256(args.lifecycle_dir / "lifecycle_manifest.json"), "lifecycle_events_sha256": sha256(args.lifecycle_dir / "lifecycle_events.csv"), "shadow_manifest_sha256": sha256(args.shadow_dir / "admission_shadow_manifest.json"), "hybrid_head_progress_sha256": sha256(args.shadow_dir / "admission_shadow_v2_head_progress.csv")}
    return layer_rows, step_rows, summaries, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    validate_args(args)
    layers, steps, summaries, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "memory_system_layer_results.csv", layers, LAYER_COLUMNS)
    write_csv(args.output_dir / "memory_system_step_results.csv", steps, STEP_COLUMNS)
    write_csv(args.output_dir / "memory_system_summary.csv", summaries, SUMMARY_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a37-memory-system-dse-1.0", "git_commit": get_git_commit(), "lifecycle_dir": str(args.lifecycle_dir), "shadow_dir": str(args.shadow_dir), "a1_dir": str(args.a1_dir), "source_artifact_sha256": provenance, "assumptions": vars(args), "state_timing": "State before decode call c is from schema-1.4 shadow calls strictly before c; current-call admission is charged after the attention proxy.", "boundaries": ["Pending positions are unavailable in schema-1.4; bank placement is a deterministic contiguous-FIFO layout proxy.", "This is not a DRAM/HBM counter, allocator measurement, latency/throughput result, sparse-attention execution, or policy-on generation result."]}
    manifest["assumptions"]["lifecycle_dir"] = str(args.lifecycle_dir)
    manifest["assumptions"]["shadow_dir"] = str(args.shadow_dir)
    manifest["assumptions"]["a1_dir"] = str(args.a1_dir)
    manifest["assumptions"]["a2_freeze"] = str(args.a2_freeze)
    (args.output_dir / "memory_system_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"Route-A3.7 modeled {len(summaries)} summaries, {len(steps)} steps, and {len(layers)} layer rows: {args.output_dir}")


if __name__ == "__main__":
    main()
