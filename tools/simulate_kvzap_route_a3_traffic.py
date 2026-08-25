"""Route-A3 explicit byte/cycle DSE over validated A2 lifecycle traces.

This is a model-free accounting simulation.  It never loads a model and does
not measure HBM, allocator memory, latency, or throughput.  It reports the
four fixed Route-A baselines and optional explicitly labelled horizon-gated
policy variants.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.validate_kvzap_decode_lifecycle_trace import read_csv, validate
from tools.analyze_kvzap_trace import get_git_commit


BASELINES = ("full_kv", "ideal_packed_kvzap", "packed_static_head", "packed_length_aware_head")
HORIZON_BASELINES = ("packed_oracle_static_head", "packed_oracle_length_aware_head")
DEFERRED_BASELINES = ("packed_deferred_static_head", "packed_deferred_length_aware_head")
WORKLOAD_SUITES = {
    "conservative_three": (
        (
            "retrieval_qasper",
            Path("analysis/experiments/route_a2_longbench_retrieval_01"),
            Path("analysis/experiments/route_a2_longbench_retrieval_01_pages"),
        ),
        (
            "reasoning_2wikimqa",
            Path("analysis/experiments/route_a2_longbench_reasoning_01"),
            Path("analysis/experiments/route_a2_longbench_reasoning_01_pages"),
        ),
        (
            "longhorizon_gov_report_row109",
            Path("analysis/experiments/route_a2_longhorizon_gov_report_01"),
            Path("analysis/experiments/route_a2_longhorizon_gov_report_01_pages"),
        ),
    ),
}
STEP_COLUMNS = (
    "workload", "request_id", "page_tokens", "bandwidth_bytes_per_cycle", "pe_count", "head_dispatch_cycles", "scheduler_queue_bytes_per_head", "baseline", "policy_kind", "policy_threshold_decode_steps", "policy_activation_decode_step", "model_call", "decode_step",
    "cache_tokens_after", "full_read_bytes", "ideal_packed_read_bytes", "physical_packed_read_bytes",
    "metadata_lookup_bytes", "upfront_admission_bytes", "decode_admission_bytes", "scheduler_queue_bytes",
    "step_total_bytes", "cumulative_total_bytes", "cumulative_full_kv_bytes", "cumulative_net_bytes_saved",
    "attention_cycles", "admission_cycles", "scheduler_cycles", "step_total_cycles", "cumulative_total_cycles",
)
SUMMARY_COLUMNS = (
    "workload", "request_id", "page_tokens", "bandwidth_bytes_per_cycle", "pe_count", "head_dispatch_cycles", "scheduler_queue_bytes_per_head", "baseline", "policy_kind", "policy_threshold_decode_steps", "policy_activation_decode_step", "decode_steps",
    "full_kv_cumulative_bytes", "baseline_cumulative_bytes", "net_bytes_saved", "net_bytes_saved_fraction",
    "break_even_decode_step", "break_even_model_call", "full_kv_cumulative_cycles", "baseline_cumulative_cycles",
    "net_cycles_saved", "net_cycles_saved_fraction", "scheduler_cycle_source",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3 byte/cycle DSE over validated A2 lifecycles and page replays.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--lifecycle-dir", type=Path, action="append", help="Validated A2 lifecycle directory; repeat with matching --page-replay-dir for a custom multi-workload suite.")
    source.add_argument("--workload-suite", choices=sorted(WORKLOAD_SUITES), help="Named frozen A2 workload suite. conservative_three is retrieval, reasoning, and long-horizon summarization.")
    parser.add_argument("--page-replay-dir", type=Path, action="append", help="Matching A2 page-replay directory; repeat in the same order as --lifecycle-dir. Cannot be used with --workload-suite.")
    parser.add_argument("--workload-name", action="append", help="Stable custom workload label; repeat in the same order as --lifecycle-dir. Defaults to each lifecycle directory name.")
    parser.add_argument("--a1-dir", type=Path, required=True, help="Completed A1 DSE used only as the declared scheduler-policy provenance.")
    parser.add_argument("--a2-freeze", type=Path, default=Path("analysis/route_a2_lifecycle_freeze.json"))
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory only; existing output directories are never overwritten.")
    parser.add_argument("--page-tokens", nargs="+", type=int, default=[16, 32, 64, 128])
    parser.add_argument("--bandwidth-bytes-per-cycle", nargs="+", type=float, default=[512.0, 1024.0, 2048.0])
    parser.add_argument("--throughput-ops-per-cycle", type=float, default=4096.0)
    parser.add_argument("--attention-ops-per-kv-token", type=float, default=512.0)
    parser.add_argument("--pe-counts", nargs="+", type=int, default=[4, 8, 16])
    parser.add_argument("--metadata-lookup-bytes-per-page", type=int, default=16)
    parser.add_argument("--metadata-lookup-cycles-per-page", type=float, default=1.0)
    parser.add_argument("--head-dispatch-cycles", nargs="+", type=float, default=[0.0], help="Declared whole-head LPT dispatch cost(s) from the A1 policy family.")
    parser.add_argument("--scheduler-queue-bytes-per-head", nargs="+", type=int, default=[0], help="Declared per-head per-decode queue traffic point(s) for the selected scheduler.")
    parser.add_argument("--oracle-min-decode-steps", nargs="+", type=int, default=[], help="Optional offline-only whole-request horizon gates. If the observed total decode steps are below a threshold, use Full KV for the entire request. This is an oracle upper bound, not an online policy.")
    parser.add_argument("--deferred-admission-decode-steps", nargs="+", type=int, default=[], help="Optional online-observable delay(s). Use Full KV for the first N decode attention calls; if call N+1 exists, compact then and charge all deferred declared admission bytes together. N=0 degenerates to the fixed packed baselines.")
    parser.add_argument("--deferred-admission-decode-step-range", nargs=2, type=int, metavar=("START", "STOP"), help="Inclusive integer deferred-delay sweep. It is merged and deduplicated with --deferred-admission-decode-steps; e.g. 0 32 evaluates every N from 0 through 32.")
    return parser.parse_args(argv)


def resolve_workloads(args: argparse.Namespace) -> list[tuple[str, Path, Path]]:
    """Resolve either a named frozen suite or explicit ordered input pairs."""
    if args.workload_suite:
        if args.page_replay_dir or args.workload_name:
            raise ValueError("--workload-suite cannot be combined with --page-replay-dir or --workload-name")
        return list(WORKLOAD_SUITES[args.workload_suite])
    if not args.page_replay_dir or len(args.lifecycle_dir) != len(args.page_replay_dir):
        raise ValueError("--lifecycle-dir and --page-replay-dir must have the same number of ordered entries")
    names = args.workload_name or [path.name for path in args.lifecycle_dir]
    if len(names) != len(args.lifecycle_dir) or len(set(names)) != len(names):
        raise ValueError("--workload-name must provide one unique label per --lifecycle-dir")
    return list(zip(names, args.lifecycle_dir, args.page_replay_dir))


def expand_inclusive_range(bounds: list[int] | None, *, flag: str) -> list[int]:
    if bounds is None:
        return []
    start, stop = bounds
    if start < 0 or stop < 0 or start > stop:
        raise ValueError(f"{flag} requires 0 <= START <= STOP")
    return list(range(start, stop + 1))


def resolve_policy_thresholds(args: argparse.Namespace) -> None:
    """Normalize policy axes before validating assumptions or writing provenance."""
    deferred = args.deferred_admission_decode_steps + expand_inclusive_range(args.deferred_admission_decode_step_range, flag="--deferred-admission-decode-step-range")
    args.deferred_admission_decode_steps = sorted(set(deferred))
    args.oracle_min_decode_steps = sorted(set(args.oracle_min_decode_steps))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def task_cycles(slots: int, page_count: int, *, kv_bytes: int, bandwidth: float, throughput: float, ops_per_token: float, metadata_lookup_bytes: int, metadata_lookup_cycles: float) -> float:
    if slots < 0 or page_count < 0:
        raise ValueError("slots/page count must be non-negative")
    bytes_cost = (slots * kv_bytes + page_count * metadata_lookup_bytes) / bandwidth
    compute_cost = slots * ops_per_token / throughput
    return max(bytes_cost, compute_cost) + page_count * metadata_lookup_cycles


def layer_cycles(tasks: list[tuple[int, float]], *, pe_count: int, policy: str, head_dispatch_cycles: float) -> float:
    """One layer barrier with static affinity or whole-head LPT scheduling."""
    loads = [0.0] * pe_count
    if policy == "static_head":
        for head, cycles in tasks:
            loads[head % pe_count] += cycles
    elif policy == "length_aware_head":
        for _head, cycles in sorted(tasks, key=lambda item: (-item[1], item[0])):
            pe = min(range(pe_count), key=lambda index: loads[index])
            loads[pe] += cycles + head_dispatch_cycles
    else:
        raise ValueError(f"Unsupported scheduler policy: {policy}")
    return max(loads, default=0.0)


def attention_cycles(rows: list[dict[str, str]], *, kind: str, page_tokens: int, window: int, kv_bytes: int, bandwidth: float, throughput: float, ops_per_token: float, metadata_lookup_bytes: int, metadata_lookup_cycles: float, pe_count: int, policy: str, head_dispatch_cycles: float) -> float:
    by_layer: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for row in rows:
        cache = int(row["cache_tokens_after"])
        hot = min(window, cache)
        if kind == "full":
            slots, pages = cache, 0
        elif kind == "ideal":
            slots, pages = hot + int(row["cold_logical_tokens"]), 0
        elif kind == "physical":
            slots, pages = hot + int(row["cold_allocated_slots"]), int(row["cold_allocated_slots"]) // page_tokens
        else:
            raise ValueError(f"Unknown attention kind: {kind}")
        by_layer[int(row["layer"])].append((int(row["kv_head"]), task_cycles(slots, pages, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=metadata_lookup_bytes, metadata_lookup_cycles=metadata_lookup_cycles)))
    return sum(layer_cycles(tasks, pe_count=pe_count, policy=policy, head_dispatch_cycles=head_dispatch_cycles) for _, tasks in sorted(by_layer.items()))


def validate_a1(a1_dir: Path) -> dict[str, Any]:
    manifest_path = a1_dir / "scheduler_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"A1 scheduler manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a1-scheduler-dse-1.0":
        raise ValueError("Unsupported A1 scheduler schema")
    return manifest


def verify_a2_freeze(freeze_path: Path, lifecycle_dir: Path, replay_dir: Path) -> dict[str, Any]:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("schema_version") != "kvzap-route-a2-lifecycle-freeze-1.0":
        raise ValueError("Unsupported A2 freeze schema")
    artifacts = freeze.get("artifact_sha256", {})
    for directory in (lifecycle_dir, replay_dir):
        expected = artifacts.get(directory.name)
        if expected is None:
            raise ValueError(f"A2 freeze does not contain artifact hashes for {directory.name}")
        for name, digest in expected.items():
            path = directory / name
            if not path.is_file() or sha256(path) != digest:
                raise ValueError(f"A2 freeze hash mismatch: {path}")
    return freeze


def build_rows(lifecycle_dir: Path, replay_dir: Path, page_tokens: int) -> tuple[list[dict[str, str]], dict[tuple[int, int, int], dict[str, str]], dict[str, Any]]:
    lifecycle_manifest = json.loads((lifecycle_dir / "lifecycle_manifest.json").read_text(encoding="utf-8"))
    source = read_csv(lifecycle_dir / "lifecycle_events.csv")
    replay_manifest = json.loads((replay_dir / "lifecycle_page_replay_manifest.json").read_text(encoding="utf-8"))
    if page_tokens not in replay_manifest.get("page_tokens", []):
        raise ValueError(f"Page size {page_tokens} absent from replay manifest")
    if replay_manifest.get("source_artifact_sha256", {}).get("lifecycle_events") != sha256(lifecycle_dir / "lifecycle_events.csv"):
        raise ValueError("Replay does not hash-match lifecycle events")
    replay = [row for row in read_csv(replay_dir / "lifecycle_page_replay_events.csv") if int(row["page_tokens"]) == page_tokens]
    indexed = {(int(row["model_call"]), int(row["layer"]), int(row["kv_head"])): row for row in replay}
    expected = len(source)
    if len(indexed) != expected:
        raise ValueError(f"Replay row coverage mismatch for P={page_tokens}: {len(indexed)} != {expected}")
    return source, indexed, lifecycle_manifest


def policy_variants(oracle_min_decode_steps: list[int], deferred_admission_decode_steps: list[int]) -> list[dict[str, Any]]:
    """Describe fixed baselines plus optional, separately-labelled policy cases."""
    variants = [
        {"id": "full_kv", "baseline": "full_kv", "policy_kind": "fixed", "threshold": "", "attention": "full", "scheduler": "static_head"},
        {"id": "ideal_packed_kvzap", "baseline": "ideal_packed_kvzap", "policy_kind": "fixed", "threshold": "", "attention": "ideal", "scheduler": "static_head"},
        {"id": "packed_static_head", "baseline": "packed_static_head", "policy_kind": "fixed", "threshold": "", "attention": "physical", "scheduler": "static_head"},
        {"id": "packed_length_aware_head", "baseline": "packed_length_aware_head", "policy_kind": "fixed", "threshold": "", "attention": "physical", "scheduler": "length_aware_head"},
    ]
    for threshold in oracle_min_decode_steps:
        variants.extend([
            {"id": f"packed_oracle_static_head:{threshold}", "baseline": "packed_oracle_static_head", "policy_kind": "oracle_horizon_gate", "threshold": threshold, "attention": "physical", "scheduler": "static_head"},
            {"id": f"packed_oracle_length_aware_head:{threshold}", "baseline": "packed_oracle_length_aware_head", "policy_kind": "oracle_horizon_gate", "threshold": threshold, "attention": "physical", "scheduler": "length_aware_head"},
        ])
    for threshold in deferred_admission_decode_steps:
        variants.extend([
            {"id": f"packed_deferred_static_head:{threshold}", "baseline": "packed_deferred_static_head", "policy_kind": "deferred_observed_steps", "threshold": threshold, "attention": "physical", "scheduler": "static_head"},
            {"id": f"packed_deferred_length_aware_head:{threshold}", "baseline": "packed_deferred_length_aware_head", "policy_kind": "deferred_observed_steps", "threshold": threshold, "attention": "physical", "scheduler": "length_aware_head"},
        ])
    return variants


def policy_active(policy_kind: str, threshold: int | str, *, decode_step: int, decode_steps: int) -> bool:
    """Whether a physical packed path serves this observed decode attention call."""
    if policy_kind == "fixed":
        return True
    if policy_kind == "oracle_horizon_gate":
        return decode_steps >= int(threshold)
    if policy_kind == "deferred_observed_steps":
        return decode_step > int(threshold)
    raise ValueError(f"Unsupported policy kind: {policy_kind}")


def policy_activation_step(policy_kind: str, threshold: int | str, *, decode_steps: int) -> int | str:
    if policy_kind == "fixed":
        return 1
    if policy_kind == "oracle_horizon_gate":
        return 1 if decode_steps >= int(threshold) else "not_activated"
    if policy_kind == "deferred_observed_steps":
        step = int(threshold) + 1
        return step if step <= decode_steps else "not_activated"
    raise ValueError(f"Unsupported policy kind: {policy_kind}")


def simulate(source: list[dict[str, str]], replay: dict[tuple[int, int, int], dict[str, str]], manifest: dict[str, Any], *, workload: str, page_tokens: int, bandwidth: float, throughput: float, ops_per_token: float, pe_count: int, metadata_lookup_bytes: int, metadata_lookup_cycles: float, head_dispatch_cycles: float, scheduler_queue_bytes_per_head: int, oracle_min_decode_steps: list[int], deferred_admission_decode_steps: list[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kv_bytes, window = int(manifest["kv_bytes_per_layer_head_token"]), int(manifest["sliding_window"])
    request_id = str(manifest["request_id"])
    by_call: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in source:
        by_call[int(row["model_call"])].append(row)
    decode_calls = sorted(call for call, rows in by_call.items() if rows[0]["phase"] == "decode")
    if not decode_calls:
        raise ValueError("A3 requires at least one observed decode model call")
    upfront = 0
    for call, rows in by_call.items():
        if call >= decode_calls[0]:
            continue
        for row in rows:
            key = (call, int(row["layer"]), int(row["kv_head"]))
            upfront += int(row["hot_to_cold_read_bytes"]) + int(row["cold_write_bytes"]) + int(replay[key]["metadata_update_bytes"])
    variants = policy_variants(oracle_min_decode_steps, deferred_admission_decode_steps)
    cumulative_bytes = {variant["id"]: 0.0 for variant in variants}
    cumulative_cycles = {variant["id"]: 0.0 for variant in variants}
    break_even: dict[str, tuple[int, int] | None] = {variant["id"]: None for variant in variants if variant["baseline"] != "full_kv"}
    step_rows: list[dict[str, Any]] = []
    decode_admission_history: list[int] = []
    for index, call in enumerate(decode_calls, start=1):
        rows = by_call[call]
        page_rows = [replay[(call, int(row["layer"]), int(row["kv_head"]))] for row in rows]
        full_read = sum(int(row["cache_tokens_after"]) * kv_bytes for row in rows)
        ideal_read = sum((min(window, int(row["cache_tokens_after"])) + int(page["cold_logical_tokens"])) * kv_bytes for row, page in zip(rows, page_rows))
        physical_read = sum((min(window, int(row["cache_tokens_after"])) + int(page["cold_allocated_slots"])) * kv_bytes for row, page in zip(rows, page_rows))
        metadata_read = sum((int(page["cold_allocated_slots"]) // page_tokens) * metadata_lookup_bytes for page in page_rows)
        decode_admission = sum(int(row["hot_to_cold_read_bytes"]) + int(row["cold_write_bytes"]) + int(page["metadata_update_bytes"]) for row, page in zip(rows, page_rows))
        fixed_admission = decode_admission + (upfront if index == 1 else 0)
        decode_admission_history.append(decode_admission)
        head_count = len(rows)
        queue_bytes = scheduler_queue_bytes_per_head * head_count
        full_cycles = attention_cycles(page_rows, kind="full", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=0, metadata_lookup_cycles=0.0, pe_count=pe_count, policy="static_head", head_dispatch_cycles=0.0)
        ideal_cycles = attention_cycles(page_rows, kind="ideal", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=0, metadata_lookup_cycles=0.0, pe_count=pe_count, policy="static_head", head_dispatch_cycles=0.0)
        static_cycles = attention_cycles(page_rows, kind="physical", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=metadata_lookup_bytes, metadata_lookup_cycles=metadata_lookup_cycles, pe_count=pe_count, policy="static_head", head_dispatch_cycles=0.0)
        selected_cycles = attention_cycles(page_rows, kind="physical", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=metadata_lookup_bytes, metadata_lookup_cycles=metadata_lookup_cycles, pe_count=pe_count, policy="length_aware_head", head_dispatch_cycles=head_dispatch_cycles)
        for variant in variants:
            baseline, kind, threshold = variant["baseline"], variant["policy_kind"], variant["threshold"]
            if baseline == "full_kv":
                active, attention, admission_bytes, scheduler_bytes = False, "full", 0, 0
            elif baseline == "ideal_packed_kvzap":
                active, attention, admission_bytes, scheduler_bytes = True, "ideal", 0, 0
            else:
                active = policy_active(kind, threshold, decode_step=index, decode_steps=len(decode_calls))
                attention = "physical" if active else "full"
                if not active:
                    admission_bytes = 0
                elif kind == "deferred_observed_steps" and index == int(threshold) + 1:
                    admission_bytes = upfront + sum(decode_admission_history)
                else:
                    admission_bytes = fixed_admission
                scheduler_bytes = queue_bytes if active and variant["scheduler"] == "length_aware_head" else 0
            attention_value = full_cycles if attention == "full" else ideal_cycles if attention == "ideal" else static_cycles if variant["scheduler"] == "static_head" else selected_cycles
            total_bytes = (full_read if attention == "full" else ideal_read if attention == "ideal" else physical_read) + (metadata_read if attention == "physical" else 0) + admission_bytes + scheduler_bytes
            total_cycles = attention_value + admission_bytes / bandwidth + scheduler_bytes / bandwidth
            variant_id = variant["id"]
            cumulative_bytes[variant_id] += total_bytes
            cumulative_cycles[variant_id] += total_cycles
            if baseline != "full_kv" and break_even[variant_id] is None and cumulative_bytes[variant_id] < cumulative_bytes["full_kv"]:
                break_even[variant_id] = (index, call)
            activation = policy_activation_step(kind, threshold, decode_steps=len(decode_calls)) if baseline not in ("full_kv", "ideal_packed_kvzap") else ""
            step_rows.append({
                "workload": workload, "request_id": request_id, "page_tokens": page_tokens, "bandwidth_bytes_per_cycle": bandwidth, "pe_count": pe_count, "head_dispatch_cycles": head_dispatch_cycles, "scheduler_queue_bytes_per_head": scheduler_queue_bytes_per_head, "baseline": baseline, "policy_kind": kind, "policy_threshold_decode_steps": threshold, "policy_activation_decode_step": activation,
                "model_call": call, "decode_step": index, "cache_tokens_after": int(rows[0]["cache_tokens_after"]),
                "full_read_bytes": full_read, "ideal_packed_read_bytes": ideal_read, "physical_packed_read_bytes": physical_read,
                "metadata_lookup_bytes": metadata_read if attention == "physical" else 0,
                "upfront_admission_bytes": upfront if admission_bytes and index == 1 and kind != "deferred_observed_steps" else (upfront if admission_bytes and kind == "deferred_observed_steps" and index == int(threshold) + 1 else 0),
                "decode_admission_bytes": admission_bytes - (upfront if admission_bytes and ((index == 1 and kind != "deferred_observed_steps") or (kind == "deferred_observed_steps" and index == int(threshold) + 1)) else 0),
                "scheduler_queue_bytes": scheduler_bytes, "step_total_bytes": total_bytes,
                "cumulative_total_bytes": cumulative_bytes[variant_id], "cumulative_full_kv_bytes": cumulative_bytes["full_kv"],
                "cumulative_net_bytes_saved": cumulative_bytes["full_kv"] - cumulative_bytes[variant_id],
                "attention_cycles": attention_value,
                "admission_cycles": admission_bytes / bandwidth,
                "scheduler_cycles": (selected_cycles - static_cycles) + queue_bytes / bandwidth if attention == "physical" and variant["scheduler"] == "length_aware_head" else 0.0,
                "step_total_cycles": total_cycles, "cumulative_total_cycles": cumulative_cycles[variant_id],
            })
    summaries = []
    for variant in variants:
        baseline, kind, threshold, variant_id = variant["baseline"], variant["policy_kind"], variant["threshold"], variant["id"]
        full_b, full_c = cumulative_bytes["full_kv"], cumulative_cycles["full_kv"]
        point = break_even.get(variant_id)
        summaries.append({"workload": workload, "request_id": request_id, "page_tokens": page_tokens, "bandwidth_bytes_per_cycle": bandwidth, "pe_count": pe_count, "head_dispatch_cycles": head_dispatch_cycles, "scheduler_queue_bytes_per_head": scheduler_queue_bytes_per_head, "baseline": baseline, "policy_kind": kind, "policy_threshold_decode_steps": threshold, "policy_activation_decode_step": policy_activation_step(kind, threshold, decode_steps=len(decode_calls)) if baseline not in ("full_kv", "ideal_packed_kvzap") else "", "decode_steps": len(decode_calls), "full_kv_cumulative_bytes": full_b, "baseline_cumulative_bytes": cumulative_bytes[variant_id], "net_bytes_saved": full_b - cumulative_bytes[variant_id], "net_bytes_saved_fraction": (full_b - cumulative_bytes[variant_id]) / full_b if full_b else math.nan, "break_even_decode_step": point[0] if point else "not_reached", "break_even_model_call": point[1] if point else "not_reached", "full_kv_cumulative_cycles": full_c, "baseline_cumulative_cycles": cumulative_cycles[variant_id], "net_cycles_saved": full_c - cumulative_cycles[variant_id], "net_cycles_saved_fraction": (full_c - cumulative_cycles[variant_id]) / full_c if full_c else math.nan, "scheduler_cycle_source": "A1_policy_constants_plus_A2_single_request_step_model" if variant["scheduler"] == "length_aware_head" else "A3_single_request_step_model"})
    return step_rows, summaries


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    resolve_policy_thresholds(args)
    if not args.page_tokens or not args.bandwidth_bytes_per_cycle or len(set(args.page_tokens)) != len(args.page_tokens) or len(set(args.bandwidth_bytes_per_cycle)) != len(args.bandwidth_bytes_per_cycle):
        raise ValueError("page sizes and bandwidth points must be non-empty and unique")
    if len(set(args.pe_counts)) != len(args.pe_counts) or len(set(args.head_dispatch_cycles)) != len(args.head_dispatch_cycles) or len(set(args.scheduler_queue_bytes_per_head)) != len(args.scheduler_queue_bytes_per_head) or len(set(args.oracle_min_decode_steps)) != len(args.oracle_min_decode_steps) or len(set(args.deferred_admission_decode_steps)) != len(args.deferred_admission_decode_steps) or min(args.page_tokens) <= 0 or min(args.bandwidth_bytes_per_cycle) <= 0 or min(args.throughput_ops_per_cycle, args.attention_ops_per_kv_token, *args.pe_counts) <= 0 or min(args.metadata_lookup_bytes_per_page, *args.scheduler_queue_bytes_per_head, *args.oracle_min_decode_steps, *args.deferred_admission_decode_steps) < 0 or min(args.metadata_lookup_cycles_per_page, *args.head_dispatch_cycles) < 0:
        raise ValueError("invalid non-negative/positive A3 assumptions")
    workloads = resolve_workloads(args)
    for _name, lifecycle_dir, replay_dir in workloads:
        validate(lifecycle_dir)
    freeze = verify_a2_freeze(args.a2_freeze, workloads[0][1], workloads[0][2])
    for _name, lifecycle_dir, replay_dir in workloads[1:]:
        verify_a2_freeze(args.a2_freeze, lifecycle_dir, replay_dir)
    a1 = validate_a1(args.a1_dir)
    all_steps: list[dict[str, Any]] = []
    all_summary: list[dict[str, Any]] = []
    for workload, lifecycle_dir, replay_dir in workloads:
        for page in args.page_tokens:
            source, replay, lifecycle_manifest = build_rows(lifecycle_dir, replay_dir, page)
            for bandwidth in args.bandwidth_bytes_per_cycle:
                for pe_count in args.pe_counts:
                    for dispatch_cycles in args.head_dispatch_cycles:
                        for queue_bytes in args.scheduler_queue_bytes_per_head:
                            steps, summaries = simulate(source, replay, lifecycle_manifest, workload=workload, page_tokens=page, bandwidth=bandwidth, throughput=args.throughput_ops_per_cycle, ops_per_token=args.attention_ops_per_kv_token, pe_count=pe_count, metadata_lookup_bytes=args.metadata_lookup_bytes_per_page, metadata_lookup_cycles=args.metadata_lookup_cycles_per_page, head_dispatch_cycles=dispatch_cycles, scheduler_queue_bytes_per_head=queue_bytes, oracle_min_decode_steps=args.oracle_min_decode_steps, deferred_admission_decode_steps=args.deferred_admission_decode_steps)
                            all_steps.extend(steps)
                            all_summary.extend(summaries)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "a3_step_results.csv", all_steps, STEP_COLUMNS)
    write_csv(args.output_dir / "a3_baseline_summary.csv", all_summary, SUMMARY_COLUMNS)
    workload_hashes = {}
    for index, (workload, lifecycle_dir, replay_dir) in enumerate(workloads):
        key = f"{index:02d}_{workload}"
        workload_hashes[key] = {"lifecycle_dir": str(lifecycle_dir), "page_replay_dir": str(replay_dir), "lifecycle_manifest": sha256(lifecycle_dir / "lifecycle_manifest.json"), "lifecycle_events": sha256(lifecycle_dir / "lifecycle_events.csv"), "page_replay_manifest": sha256(replay_dir / "lifecycle_page_replay_manifest.json"), "page_replay_events": sha256(replay_dir / "lifecycle_page_replay_events.csv")}
    manifest = {"schema_version": "kvzap-route-a3-traffic-cycle-dse-1.1", "git_commit": get_git_commit(), "workload_suite": args.workload_suite, "workloads": workload_hashes, "a1_dir": str(args.a1_dir), "source_artifact_sha256": {"a2_freeze": sha256(args.a2_freeze), "a1_scheduler_manifest": sha256(args.a1_dir / "scheduler_manifest.json")}, "a2_freeze_status": freeze["freeze_status"], "a1_schema_version": a1["schema_version"], "assumptions": {"page_tokens": args.page_tokens, "bandwidth_bytes_per_cycle": args.bandwidth_bytes_per_cycle, "throughput_ops_per_cycle": args.throughput_ops_per_cycle, "attention_ops_per_kv_token": args.attention_ops_per_kv_token, "pe_counts": args.pe_counts, "metadata_lookup_bytes_per_page": args.metadata_lookup_bytes_per_page, "metadata_lookup_cycles_per_page": args.metadata_lookup_cycles_per_page, "head_dispatch_cycles": args.head_dispatch_cycles, "scheduler_queue_bytes_per_head": args.scheduler_queue_bytes_per_head, "oracle_min_decode_steps": args.oracle_min_decode_steps, "deferred_admission_decode_steps": args.deferred_admission_decode_steps}, "baseline_definitions": {"full_kv": "Dense cache read at cache_tokens_after; no admission or metadata.", "ideal_packed_kvzap": "Hot window plus cold logical tokens; zero admission, metadata, and scheduler overhead.", "packed_static_head": "Hot window plus allocated cold slots, per-page metadata lookup, and declared A2 admission bytes; static head affinity.", "packed_length_aware_head": "Same physical bytes as packed_static_head plus declared queue traffic; whole-head LPT using A1 policy-family constants over A2 single-request step tasks.", "packed_oracle_*": "Offline-only all-or-nothing request gate using the completed observed decode horizon; below threshold it uses Full KV for all decode steps. It is an unattainable online upper bound without a separate horizon predictor.", "packed_deferred_*": "Dense Full-KV decode reads until the observed delay has elapsed, then retroactively charges all previously deferred declared admission bytes and uses physical packed pages. It is a policy model, not a mask-equivalence or accuracy result."}, "notes": ["Only phase=decode attention reads are modeled. Context/prompt lifecycle admission is charged once before decode step 1 for fixed packed baselines.", "For a deferred policy, pre-activation decode calls use Full KV and have no packing cost; activation at N+1 charges context plus all prior deferred decode admission accounting together.", "The oracle horizon gate is offline-only; the deferred gate is online-observable but changes when the KVzap decision takes effect. Neither establishes generation equivalence or accuracy.", "hot_to_cold_read_bytes, cold_write_bytes, and metadata_update_bytes are declared accounting inputs, not HBM counters.", "A1 provides policy/cost provenance; selected-scheduler cycles are an A3 single-request-step model, not a measured or native-batch A1 replay.", "All byte, cycle, break-even, and latency-related conclusions are modeled under these declared assumptions, not measured performance."]}
    (args.output_dir / "a3_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3 modeled {len(all_summary)} baseline summaries and {len(all_steps)} step rows: {args.output_dir}")


if __name__ == "__main__":
    main()
