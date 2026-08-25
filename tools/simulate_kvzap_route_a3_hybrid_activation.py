"""Offline Route-A3.6 hybrid dense+packed cold-KV activation DSE.

Consumes a validated A2 lifecycle plus an A3.6 (schema 1.4) read-only shadow.
It models a candidate backend only: Full KV generation remains authoritative in
the source trace.  No output is an HBM counter, latency measurement, or
policy-on generation-equivalence result.
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
from tools.simulate_kvzap_route_a3_traffic import attention_cycles, layer_cycles, read_csv, sha256, task_cycles, validate_a1
from tools.validate_kvzap_admission_shadow import validate as validate_shadow
from tools.validate_kvzap_decode_lifecycle_trace import validate as validate_lifecycle


STEP_COLUMNS = (
    "request_id", "page_tokens", "bandwidth_bytes_per_cycle", "pe_count", "scheduler", "baseline", "model_call", "decode_step", "state_source_model_call", "cache_tokens_after", "packed_cold_logical_tokens", "packed_cold_allocated_slots", "packed_cold_page_count", "pending_dense_tokens", "hybrid_merge_head_count", "full_read_bytes", "attention_read_bytes", "pending_position_bytes", "packed_metadata_lookup_bytes", "hybrid_merge_bytes", "admission_bytes", "step_total_bytes", "cumulative_total_bytes", "cumulative_full_kv_bytes", "cumulative_net_bytes_saved", "attention_cycle_proxy", "admission_cycle_proxy", "step_total_cycle_proxy", "cumulative_total_cycle_proxy",
)
SUMMARY_COLUMNS = (
    "request_id", "page_tokens", "bandwidth_bytes_per_cycle", "pe_count", "scheduler", "baseline", "decode_steps", "activation_decode_step", "full_kv_cumulative_bytes", "baseline_cumulative_bytes", "net_bytes_saved", "net_bytes_saved_fraction", "break_even_decode_step", "full_kv_cumulative_cycle_proxy", "baseline_cumulative_cycle_proxy", "net_cycle_proxy_saved", "net_cycle_proxy_saved_fraction", "interpretation",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.6 hybrid dense-pending plus packed-cold activation DSE; never loads a model.")
    parser.add_argument("--lifecycle-dir", type=Path, required=True, help="Validated frozen A2 lifecycle directory.")
    parser.add_argument("--shadow-dir", type=Path, required=True, help="Schema-1.4 budgeted A3.6 shadow directory with per-head FIFO progress.")
    parser.add_argument("--a1-dir", type=Path, required=True, help="Completed A1 scheduler DSE, retained as scheduler-policy provenance.")
    parser.add_argument("--a2-freeze", type=Path, default=Path("analysis/route_a2_lifecycle_freeze.json"), help="Frozen A2 lifecycle boundary used to verify the source directory hashes.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--bandwidth-bytes-per-cycle", nargs="+", type=float, default=[512.0, 1024.0, 2048.0])
    parser.add_argument("--throughput-ops-per-cycle", type=float, default=4096.0)
    parser.add_argument("--attention-ops-per-kv-token", type=float, default=512.0)
    parser.add_argument("--pe-counts", nargs="+", type=int, default=[4])
    parser.add_argument("--schedulers", nargs="+", choices=("static_head", "length_aware_head"), default=["length_aware_head"])
    parser.add_argument("--metadata-lookup-bytes-per-page", type=int, default=16)
    parser.add_argument("--metadata-lookup-cycles-per-page", type=float, default=1.0)
    parser.add_argument("--head-dispatch-cycles", type=float, default=4.0)
    parser.add_argument("--pending-position-bytes-per-token", type=int, default=8, help="Declared dense-pending position/index read bytes per retained token.")
    parser.add_argument("--hybrid-merge-state-bytes-per-head", type=int, default=16, help="Declared partial-softmax merge state traffic for a head with both pending and packed cold KV.")
    parser.add_argument("--hybrid-merge-cycles-per-head", type=float, default=1.0, help="Declared merge-cycle proxy per head with both pending and packed cold KV.")
    return parser.parse_args(argv)


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def verify_lifecycle_freeze(freeze_path: Path, lifecycle_dir: Path) -> dict[str, Any]:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("schema_version") != "kvzap-route-a2-lifecycle-freeze-1.0":
        raise ValueError("unsupported A2 lifecycle freeze schema")
    expected = freeze.get("artifact_sha256", {}).get(lifecycle_dir.name)
    if not expected:
        raise ValueError("A2 freeze has no hash record for the lifecycle directory")
    for name, digest in expected.items():
        path = lifecycle_dir / name
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(f"A2 lifecycle freeze hash mismatch: {path}")
    return freeze


def load_inputs(lifecycle_dir: Path, shadow_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    validate_lifecycle(lifecycle_dir)
    validate_shadow(shadow_dir)
    lifecycle_manifest = json.loads((lifecycle_dir / "lifecycle_manifest.json").read_text(encoding="utf-8"))
    shadow_manifest = json.loads((shadow_dir / "admission_shadow_manifest.json").read_text(encoding="utf-8"))
    if shadow_manifest.get("schema_version") != "kvzap-route-a35-admission-shadow-1.4" or shadow_manifest.get("submission_mode") != "per_layer_batch_v2":
        raise ValueError("hybrid activation DSE requires schema-1.4 per_layer_batch_v2 shadow evidence")
    if shadow_manifest.get("request_id") != lifecycle_manifest.get("request_id"):
        raise ValueError("shadow request_id disagrees with A2 lifecycle")
    config = shadow_manifest.get("config", {})
    if int(config.get("kv_bytes_per_layer_head_token", -1)) != int(lifecycle_manifest["kv_bytes_per_layer_head_token"]) or int(config.get("page_tokens", -1)) <= 0:
        raise ValueError("shadow cache-byte/page configuration disagrees with A2 lifecycle")
    progress = read_csv(shadow_dir / "admission_shadow_v2_head_progress.csv")
    lifecycle = read_csv(lifecycle_dir / "lifecycle_events.csv")
    if len(progress) != len(lifecycle):
        raise ValueError("hybrid-head progress row count disagrees with lifecycle")
    return lifecycle, progress, lifecycle_manifest, shadow_manifest


def post_call_states(progress: list[dict[str, str]]) -> dict[int, dict[tuple[int, int], dict[str, int]]]:
    """Return the exact packed/pending state available before each model call."""
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in progress:
        grouped[int(row["model_call"])].append(row)
    state: dict[tuple[int, int], dict[str, int]] = {}
    before: dict[int, dict[tuple[int, int], dict[str, int]]] = {}
    for call in sorted(grouped):
        before[call] = {key: value.copy() for key, value in state.items()}
        for row in grouped[call]:
            key = (int(row["layer"]), int(row["kv_head"]))
            state[key] = {
                "packed_logical": int(row["cold_logical_tokens_after"]),
                "packed_slots": int(row["cold_allocated_slots_after"]),
                "packed_pages": int(row["cold_page_count_after"]),
                "pending": int(row["pending_tokens_after"]),
            }
    return before


def admission_bytes(progress_rows: list[dict[str, str]], *, metadata_bytes: int) -> int:
    return sum(int(row["source_gather_bytes"]) + int(row["packed_kv_bytes"]) + int(row["position_metadata_bytes"]) + int(row["new_page_allocations"]) * metadata_bytes for row in progress_rows)


def hybrid_attention(rows: list[dict[str, str]], state: dict[tuple[int, int], dict[str, int]], *, window: int, kv_bytes: int, page_tokens: int, bandwidth: float, throughput: float, ops_per_token: float, metadata_bytes: int, metadata_cycles: float, pending_position_bytes: int, merge_bytes: int, merge_cycles: float, pe_count: int, scheduler: str, head_dispatch_cycles: float) -> tuple[int, int, int, int, int, float, int, int, int, int]:
    """Return token-granular hybrid traffic and declared layer/head cycle proxy."""
    by_layer: dict[int, list[tuple[int, float]]] = defaultdict(list)
    read_bytes = index_bytes = metadata_read = merge_read = pending_total = 0
    packed_logical = packed_slots = packed_pages = merge_heads = 0
    for row in rows:
        layer, head = int(row["layer"]), int(row["kv_head"])
        item = state.get((layer, head), {"packed_logical": 0, "packed_slots": 0, "packed_pages": 0, "pending": 0})
        hot, pending = min(window, int(row["cache_tokens_after"])), item["pending"]
        slots, pages = hot + item["packed_slots"] + pending, item["packed_pages"]
        packed_logical += item["packed_logical"]
        packed_slots += item["packed_slots"]
        packed_pages += pages
        pending_total += pending
        head_read = slots * kv_bytes + pages * metadata_bytes + pending * pending_position_bytes
        both = item["packed_logical"] > 0 and pending > 0
        if both:
            head_read += merge_bytes
            merge_heads += 1
        read_bytes += slots * kv_bytes
        metadata_read += pages * metadata_bytes
        index_bytes += pending * pending_position_bytes
        merge_read += merge_bytes if both else 0
        cycles = task_cycles(slots, pages, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=metadata_bytes, metadata_lookup_cycles=metadata_cycles) + (pending * pending_position_bytes + (merge_bytes if both else 0)) / bandwidth + (merge_cycles if both else 0.0)
        by_layer[layer].append((head, cycles))
    proxy = sum(layer_cycles(tasks, pe_count=pe_count, policy=scheduler, head_dispatch_cycles=head_dispatch_cycles) for _layer, tasks in sorted(by_layer.items()))
    return read_bytes, index_bytes, metadata_read, merge_read, pending_total, proxy, packed_logical, packed_slots, packed_pages, merge_heads


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    lifecycle, progress, manifest, shadow_manifest = load_inputs(args.lifecycle_dir, args.shadow_dir)
    freeze = verify_lifecycle_freeze(args.a2_freeze, args.lifecycle_dir)
    validate_a1(args.a1_dir)
    kv_bytes, window = int(manifest["kv_bytes_per_layer_head_token"]), int(manifest["sliding_window"])
    if int(shadow_manifest["config"]["page_tokens"]) != args.page_tokens:
        raise ValueError("--page-tokens must match the schema-1.4 shadow page size")
    states = post_call_states(progress)
    progress_by_call: dict[int, list[dict[str, str]]] = defaultdict(list)
    lifecycle_by_call: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in progress:
        progress_by_call[int(row["model_call"])].append(row)
    for row in lifecycle:
        lifecycle_by_call[int(row["model_call"])].append(row)
    decode_calls = [call for call in sorted(lifecycle_by_call) if lifecycle_by_call[call][0]["phase"] == "decode"]
    if not decode_calls:
        raise ValueError("hybrid DSE requires observed decode calls")
    variants = ("full_kv", "hybrid_dense_pending_packed", "wait_for_queue_drain")
    all_steps: list[dict[str, Any]] = []
    all_summaries: list[dict[str, Any]] = []
    for bandwidth in args.bandwidth_bytes_per_cycle:
        for pe_count in args.pe_counts:
            for scheduler in args.schedulers:
                cumulative_bytes = {name: 0.0 for name in variants}
                cumulative_cycles = {name: 0.0 for name in variants}
                break_even: dict[str, int | None] = {name: None for name in variants if name != "full_kv"}
                activation: int | str = "not_activated"
                for step, call in enumerate(decode_calls, start=1):
                    rows, state = lifecycle_by_call[call], states.get(call, {})
                    full_read = sum(int(row["cache_tokens_after"]) * kv_bytes for row in rows)
                    admission = admission_bytes(progress_by_call[call], metadata_bytes=int(shadow_manifest["config"]["metadata_bytes_per_cold_page"]))
                    packed_pending = sum(item["pending"] for item in state.values())
                    drained = bool(state) and packed_pending == 0
                    if drained and activation == "not_activated":
                        activation = step
                    for baseline in variants:
                        if baseline == "full_kv":
                            read, pending_index, metadata_read, merge_read, pending, cycles = full_read, 0, 0, 0, 0, attention_cycles(rows, kind="full", page_tokens=args.page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=args.throughput_ops_per_cycle, ops_per_token=args.attention_ops_per_kv_token, metadata_lookup_bytes=0, metadata_lookup_cycles=0.0, pe_count=pe_count, policy=scheduler, head_dispatch_cycles=args.head_dispatch_cycles)
                            packed_logical = packed_slots = packed_pages = merge_heads = 0
                            charged_admission = 0
                        elif baseline == "wait_for_queue_drain" and not drained:
                            read, pending_index, metadata_read, merge_read, pending, cycles = full_read, 0, 0, 0, packed_pending, attention_cycles(rows, kind="full", page_tokens=args.page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=args.throughput_ops_per_cycle, ops_per_token=args.attention_ops_per_kv_token, metadata_lookup_bytes=0, metadata_lookup_cycles=0.0, pe_count=pe_count, policy=scheduler, head_dispatch_cycles=args.head_dispatch_cycles)
                            packed_logical = packed_slots = packed_pages = merge_heads = 0
                            charged_admission = admission
                        else:
                            read, pending_index, metadata_read, merge_read, pending, cycles, packed_logical, packed_slots, packed_pages, merge_heads = hybrid_attention(rows, state, window=window, kv_bytes=kv_bytes, page_tokens=args.page_tokens, bandwidth=bandwidth, throughput=args.throughput_ops_per_cycle, ops_per_token=args.attention_ops_per_kv_token, metadata_bytes=args.metadata_lookup_bytes_per_page, metadata_cycles=args.metadata_lookup_cycles_per_page, pending_position_bytes=args.pending_position_bytes_per_token if baseline == "hybrid_dense_pending_packed" else 0, merge_bytes=args.hybrid_merge_state_bytes_per_head if baseline == "hybrid_dense_pending_packed" else 0, merge_cycles=args.hybrid_merge_cycles_per_head if baseline == "hybrid_dense_pending_packed" else 0.0, pe_count=pe_count, scheduler=scheduler, head_dispatch_cycles=args.head_dispatch_cycles)
                            charged_admission = admission
                        total_bytes = read + pending_index + metadata_read + merge_read + charged_admission
                        admission_cycles = charged_admission / bandwidth
                        total_cycles = cycles + admission_cycles
                        cumulative_bytes[baseline] += total_bytes
                        cumulative_cycles[baseline] += total_cycles
                        if baseline != "full_kv" and break_even[baseline] is None and cumulative_bytes[baseline] < cumulative_bytes["full_kv"]:
                            break_even[baseline] = step
                        all_steps.append({"request_id": manifest["request_id"], "page_tokens": args.page_tokens, "bandwidth_bytes_per_cycle": bandwidth, "pe_count": pe_count, "scheduler": scheduler, "baseline": baseline, "model_call": call, "decode_step": step, "state_source_model_call": call - 1, "cache_tokens_after": int(rows[0]["cache_tokens_after"]), "packed_cold_logical_tokens": packed_logical, "packed_cold_allocated_slots": packed_slots, "packed_cold_page_count": packed_pages, "pending_dense_tokens": pending, "hybrid_merge_head_count": merge_heads, "full_read_bytes": full_read, "attention_read_bytes": read, "pending_position_bytes": pending_index, "packed_metadata_lookup_bytes": metadata_read, "hybrid_merge_bytes": merge_read, "admission_bytes": charged_admission, "step_total_bytes": total_bytes, "cumulative_total_bytes": cumulative_bytes[baseline], "cumulative_full_kv_bytes": cumulative_bytes["full_kv"], "cumulative_net_bytes_saved": cumulative_bytes["full_kv"] - cumulative_bytes[baseline], "attention_cycle_proxy": cycles, "admission_cycle_proxy": admission_cycles, "step_total_cycle_proxy": total_cycles, "cumulative_total_cycle_proxy": cumulative_cycles[baseline]})
                for baseline in variants:
                    full_b, full_c = cumulative_bytes["full_kv"], cumulative_cycles["full_kv"]
                    all_summaries.append({"request_id": manifest["request_id"], "page_tokens": args.page_tokens, "bandwidth_bytes_per_cycle": bandwidth, "pe_count": pe_count, "scheduler": scheduler, "baseline": baseline, "decode_steps": len(decode_calls), "activation_decode_step": "not_applicable" if baseline == "full_kv" else 1 if baseline == "hybrid_dense_pending_packed" else activation, "full_kv_cumulative_bytes": full_b, "baseline_cumulative_bytes": cumulative_bytes[baseline], "net_bytes_saved": full_b - cumulative_bytes[baseline], "net_bytes_saved_fraction": (full_b - cumulative_bytes[baseline]) / full_b, "break_even_decode_step": "not_reached" if break_even.get(baseline) is None else break_even[baseline], "full_kv_cumulative_cycle_proxy": full_c, "baseline_cumulative_cycle_proxy": cumulative_cycles[baseline], "net_cycle_proxy_saved": full_c - cumulative_cycles[baseline], "net_cycle_proxy_saved_fraction": (full_c - cumulative_cycles[baseline]) / full_c, "interpretation": "Hybrid reads exact schema-1.4 per-head packed/pending counts but uses declared index/metadata/merge byte and cycle costs. Admission is conservatively charged sequentially. It is a candidate-backend model, not sparse-attention generation, HBM, allocator, or latency evidence."})
    provenance = {"a2_freeze_sha256": sha256(args.a2_freeze), "a2_freeze_status": freeze.get("freeze_status"), "lifecycle_manifest_sha256": sha256(args.lifecycle_dir / "lifecycle_manifest.json"), "lifecycle_events_sha256": sha256(args.lifecycle_dir / "lifecycle_events.csv"), "shadow_manifest_sha256": sha256(args.shadow_dir / "admission_shadow_manifest.json"), "hybrid_head_progress_sha256": sha256(args.shadow_dir / "admission_shadow_v2_head_progress.csv")}
    return all_steps, all_summaries, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    numeric = [args.page_tokens, *args.bandwidth_bytes_per_cycle, *args.pe_counts, args.throughput_ops_per_cycle, args.attention_ops_per_kv_token, args.metadata_lookup_bytes_per_page, args.pending_position_bytes_per_token, args.hybrid_merge_state_bytes_per_head]
    if min(numeric) <= 0 or args.metadata_lookup_cycles_per_page < 0 or args.head_dispatch_cycles < 0 or args.hybrid_merge_cycles_per_head < 0 or len(set(args.bandwidth_bytes_per_cycle)) != len(args.bandwidth_bytes_per_cycle) or len(set(args.pe_counts)) != len(args.pe_counts) or len(set(args.schedulers)) != len(args.schedulers):
        raise ValueError("invalid or duplicate hybrid DSE assumptions")
    steps, summaries, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "hybrid_activation_step_results.csv", steps, STEP_COLUMNS)
    write_csv(args.output_dir / "hybrid_activation_summary.csv", summaries, SUMMARY_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a36-hybrid-activation-dse-1.0", "git_commit": get_git_commit(), "lifecycle_dir": str(args.lifecycle_dir), "shadow_dir": str(args.shadow_dir), "a1_dir": str(args.a1_dir), "source_artifact_sha256": provenance, "assumptions": {"page_tokens": args.page_tokens, "bandwidth_bytes_per_cycle": args.bandwidth_bytes_per_cycle, "pe_counts": args.pe_counts, "schedulers": args.schedulers, "throughput_ops_per_cycle": args.throughput_ops_per_cycle, "attention_ops_per_kv_token": args.attention_ops_per_kv_token, "metadata_lookup_bytes_per_page": args.metadata_lookup_bytes_per_page, "metadata_lookup_cycles_per_page": args.metadata_lookup_cycles_per_page, "head_dispatch_cycles": args.head_dispatch_cycles, "pending_position_bytes_per_token": args.pending_position_bytes_per_token, "hybrid_merge_state_bytes_per_head": args.hybrid_merge_state_bytes_per_head, "hybrid_merge_cycles_per_head": args.hybrid_merge_cycles_per_head}, "state_timing": "For decode model call c, packed/pending state is taken after all shadow admissions from calls strictly before c; current-call admissions are charged after that attention proxy.", "baselines": {"full_kv": "Dense Full-KV read without admission charge.", "hybrid_dense_pending_packed": "Candidate sparse attention: pending retained cold KV is token-gathered from dense staging while admitted cold KV is read from exact shadow packed pages.", "wait_for_queue_drain": "Full KV until the pre-call shadow FIFO is empty, then the same packed-page proxy without hybrid merge/index costs."}, "boundaries": ["The source generation used Full KV; no policy-on sparse attention was executed.", "Admission, metadata, index, merge, bandwidth, and cycles are explicit model accounting, not HBM/DRAM counters, allocator measurements, or latency/throughput results.", "Sequential admission-cycle charging is a conservative proxy and does not establish actual overlap."]}
    (args.output_dir / "hybrid_activation_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.6 modeled {len(summaries)} summaries and {len(steps)} step rows: {args.output_dir}")


if __name__ == "__main__":
    main()
