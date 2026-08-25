"""Offline Route-A3 edge microarchitecture DSE over validated A2 traces.

This tool preserves the existing A3 evidence boundary: all traffic and cycle
numbers are declared accounting/model assumptions, never measurements.  It
adds a parameterized attention-stream-engine and admission-engine model for a
candidate edge target.  It does not load a model or change KVzap masks.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a3_traffic import (
    WORKLOAD_SUITES,
    attention_cycles,
    build_rows,
    expand_inclusive_range,
    policy_activation_step,
    policy_active,
    policy_variants,
    resolve_workloads,
    sha256,
    validate_a1,
    verify_a2_freeze,
)
from tools.validate_kvzap_decode_lifecycle_trace import validate


STEP_COLUMNS = (
    "workload", "request_id", "page_tokens", "bandwidth_bytes_per_cycle", "attention_engine_count", "admission_engine_count", "admission_pack_bytes_per_cycle", "admission_memory_burst_bytes", "admission_page_setup_cycles", "head_dispatch_cycles", "scheduler_queue_bytes_per_head", "baseline", "policy_kind", "policy_threshold_decode_steps", "policy_activation_decode_step", "model_call", "decode_step", "cache_tokens_after", "full_read_bytes", "ideal_packed_read_bytes", "physical_packed_read_bytes", "metadata_lookup_bytes", "admission_bytes", "admission_task_count", "admission_transfer_cycles", "admission_pack_cycles", "admission_setup_cycles", "admission_service_cycles", "scheduler_queue_bytes", "step_total_bytes", "cumulative_total_bytes", "cumulative_full_kv_bytes", "cumulative_net_bytes_saved", "attention_cycles", "scheduler_cycles", "step_total_cycles", "cumulative_total_cycles",
)
SUMMARY_COLUMNS = (
    "workload", "request_id", "page_tokens", "bandwidth_bytes_per_cycle", "attention_engine_count", "admission_engine_count", "admission_pack_bytes_per_cycle", "admission_memory_burst_bytes", "admission_page_setup_cycles", "head_dispatch_cycles", "scheduler_queue_bytes_per_head", "baseline", "policy_kind", "policy_threshold_decode_steps", "policy_activation_decode_step", "decode_steps", "full_kv_cumulative_bytes", "baseline_cumulative_bytes", "net_bytes_saved", "net_bytes_saved_fraction", "break_even_decode_step", "break_even_model_call", "full_kv_cumulative_cycles", "baseline_cumulative_cycles", "net_cycles_saved", "net_cycles_saved_fraction", "scheduler_cycle_source",
)
CONSTRAINT_COLUMNS = (
    "workload", "request_id", "page_tokens", "bandwidth_bytes_per_cycle", "attention_engine_count", "baseline", "policy_kind", "policy_threshold_decode_steps", "policy_activation_decode_step", "decode_steps", "candidate_dse_points", "constraint_status", "minimum_declared_total_pack_bytes_per_cycle", "minimum_capacity_candidate_count", "minimum_capacity_candidates", "recommended_admission_engine_count", "recommended_per_engine_pack_bytes_per_cycle", "recommended_net_cycles_saved", "recommended_net_cycles_saved_fraction", "interpretation",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3 edge attention/admission-engine DSE over validated A2 traces.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--lifecycle-dir", type=Path, action="append", help="Validated A2 lifecycle directory; repeat with matching --page-replay-dir.")
    source.add_argument("--workload-suite", choices=sorted(WORKLOAD_SUITES), help="Named frozen A2 workload suite.")
    parser.add_argument("--page-replay-dir", type=Path, action="append", help="Matching A2 replay directory; ordered with --lifecycle-dir.")
    parser.add_argument("--workload-name", action="append", help="Optional ordered custom workload labels.")
    parser.add_argument("--architecture-config", type=Path, required=True, help="Parameterized model/edge target descriptor JSON.")
    parser.add_argument("--a1-dir", type=Path, required=True, help="Completed A1 scheduler DSE for policy provenance.")
    parser.add_argument("--a2-freeze", type=Path, default=Path("analysis/route_a2_lifecycle_freeze.json"))
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory only; existing directories are never overwritten.")
    parser.add_argument("--page-tokens", nargs="+", type=int, default=[64, 128])
    parser.add_argument("--bandwidth-bytes-per-cycle", nargs="+", type=float, default=[512.0, 1024.0, 2048.0])
    parser.add_argument("--attention-engine-counts", nargs="+", type=int, default=None, help="Layer-local attention stream engines; defaults to edge descriptor candidates.")
    parser.add_argument("--throughput-ops-per-cycle", type=float, default=4096.0)
    parser.add_argument("--attention-ops-per-kv-token", type=float, default=512.0)
    parser.add_argument("--metadata-lookup-bytes-per-page", type=int, default=16)
    parser.add_argument("--metadata-lookup-cycles-per-page", type=float, default=1.0)
    parser.add_argument("--head-dispatch-cycles", type=float, default=4.0)
    parser.add_argument("--scheduler-queue-bytes-per-head", type=int, default=64)
    parser.add_argument("--admission-engine-count", type=int, default=1, help="Shared mature-KV pack engines. This is a declared model parameter, not measured hardware.")
    parser.add_argument("--admission-pack-bytes-per-cycle", type=float, default=512.0, help="Per admission engine scan/filter/write throughput assumption.")
    parser.add_argument("--admission-engine-counts", nargs="+", type=int, default=None, help="Admission-engine-count DSE points; overrides the singular compatibility flag.")
    parser.add_argument("--admission-pack-bytes-per-cycle-points", nargs="+", type=float, default=None, help="Per-admission-engine packing-throughput DSE points; overrides the singular compatibility flag.")
    parser.add_argument("--admission-memory-burst-bytes", type=int, default=64, help="Declared DRAM transaction granularity used to round admission transfers.")
    parser.add_argument("--admission-page-setup-cycles", type=float, default=1.0, help="Declared per cold-page allocation/descriptor setup cost.")
    parser.add_argument("--deferred-admission-decode-steps", nargs="+", type=int, default=[])
    parser.add_argument("--deferred-admission-decode-step-range", nargs=2, type=int, metavar=("START", "STOP"), help="Inclusive online deferred-delay range, merged with explicit points.")
    return parser.parse_args(argv)


def resolve_admission_points(args: argparse.Namespace) -> tuple[list[int], list[float]]:
    """Resolve explicit admission DSE axes while retaining single-point CLI use."""
    engine_counts = args.admission_engine_counts or [args.admission_engine_count]
    pack_points = args.admission_pack_bytes_per_cycle_points or [args.admission_pack_bytes_per_cycle]
    if min(engine_counts) <= 0 or min(pack_points) <= 0 or len(set(engine_counts)) != len(engine_counts) or len(set(pack_points)) != len(pack_points):
        raise ValueError("invalid or duplicate admission-engine DSE assumptions")
    return engine_counts, pack_points


def write_csv(path: Path, rows: list[dict[str, Any]], columns: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def derive_admission_constraints(summaries: list[dict[str, Any]], *, epsilon_cycles: float = 1e-9) -> list[dict[str, Any]]:
    """Extract the minimum scanned pack capacity needed for non-negative cycles.

    This is a feasibility table over declared DSE points, not a hardware
    requirement. Unactivated deferred policies correctly remain Full-KV
    fallback rather than pretending to require admission capacity.
    """
    selected = [row for row in summaries if row["baseline"] in {"packed_length_aware_head", "packed_deferred_length_aware_head"}]
    keys = ("workload", "request_id", "page_tokens", "bandwidth_bytes_per_cycle", "attention_engine_count", "baseline", "policy_kind", "policy_threshold_decode_steps", "policy_activation_decode_step", "decode_steps")
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        groups[tuple(row[key] for key in keys)].append(row)
    constraints: list[dict[str, Any]] = []
    for key, candidates in sorted(groups.items()):
        row = dict(zip(keys, key, strict=True))
        row["candidate_dse_points"] = len(candidates)
        if row["policy_activation_decode_step"] == "not_activated":
            row.update({"constraint_status": "not_applicable_full_kv_fallback", "minimum_declared_total_pack_bytes_per_cycle": "not_applicable", "minimum_capacity_candidate_count": 0, "minimum_capacity_candidates": "not_applicable", "recommended_admission_engine_count": "not_applicable", "recommended_per_engine_pack_bytes_per_cycle": "not_applicable", "recommended_net_cycles_saved": 0.0, "recommended_net_cycles_saved_fraction": 0.0, "interpretation": "Deferred policy never activates; it exactly falls back to Full KV, so no admission capacity is required by this trace horizon."})
            constraints.append(row)
            continue
        feasible = [candidate for candidate in candidates if float(candidate["net_cycles_saved"]) >= -epsilon_cycles]
        if not feasible:
            row.update({"constraint_status": "no_nonnegative_point_in_scan", "minimum_declared_total_pack_bytes_per_cycle": "not_found", "minimum_capacity_candidate_count": 0, "minimum_capacity_candidates": "not_found", "recommended_admission_engine_count": "not_found", "recommended_per_engine_pack_bytes_per_cycle": "not_found", "recommended_net_cycles_saved": "not_found", "recommended_net_cycles_saved_fraction": "not_found", "interpretation": "No scanned admission configuration reaches non-negative modeled cycles; expand the DSE or retain Full KV for this operating point."})
            constraints.append(row)
            continue
        capacity = lambda candidate: int(candidate["admission_engine_count"]) * float(candidate["admission_pack_bytes_per_cycle"])
        minimum = min(capacity(candidate) for candidate in feasible)
        frontier = [candidate for candidate in feasible if math.isclose(capacity(candidate), minimum)]
        recommended = max(frontier, key=lambda candidate: (float(candidate["net_cycles_saved"]), -int(candidate["admission_engine_count"])))
        row.update({"constraint_status": "nonnegative_point_found", "minimum_declared_total_pack_bytes_per_cycle": minimum, "minimum_capacity_candidate_count": len(frontier), "minimum_capacity_candidates": ";".join(f"E{candidate['admission_engine_count']}xP{candidate['admission_pack_bytes_per_cycle']}" for candidate in sorted(frontier, key=lambda candidate: (int(candidate["admission_engine_count"]), float(candidate["admission_pack_bytes_per_cycle"])))), "recommended_admission_engine_count": recommended["admission_engine_count"], "recommended_per_engine_pack_bytes_per_cycle": recommended["admission_pack_bytes_per_cycle"], "recommended_net_cycles_saved": recommended["net_cycles_saved"], "recommended_net_cycles_saved_fraction": recommended["net_cycles_saved_fraction"], "interpretation": "Minimum declared aggregate pack capacity among scanned points with non-negative modeled cycles; alternatives at that capacity are retained explicitly."})
        constraints.append(row)
    return constraints


def load_architecture_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "kvzap-route-a3-edge-target-1.0":
        raise ValueError("Unsupported edge target schema")
    model, edge = config.get("model", {}), config.get("edge_execution", {})
    required = ("hf_id", "num_hidden_layers", "num_attention_heads", "num_key_value_heads", "head_dim", "gqa_group_size", "kv_bytes_per_layer_head_token")
    if any(key not in model for key in required) or not edge.get("attention_engine_candidates"):
        raise ValueError("Edge target descriptor is missing model dimensions or attention engine candidates")
    if model["num_attention_heads"] != model["num_key_value_heads"] * model["gqa_group_size"]:
        raise ValueError("Descriptor GQA dimensions disagree")
    return config


def validate_descriptor_against_trace(descriptor: dict[str, Any], source: list[dict[str, str]], lifecycle_manifest: dict[str, Any]) -> None:
    model = descriptor["model"]
    if lifecycle_manifest.get("model") != model["hf_id"]:
        raise ValueError("Edge descriptor model does not match lifecycle manifest")
    if int(lifecycle_manifest["kv_bytes_per_layer_head_token"]) != int(model["kv_bytes_per_layer_head_token"]):
        raise ValueError("Edge descriptor KV bytes/token does not match lifecycle manifest")
    layers = {int(row["layer"]) for row in source}
    heads = {int(row["kv_head"]) for row in source}
    if len(layers) != int(model["num_hidden_layers"]) or len(heads) != int(model["num_key_value_heads"]):
        raise ValueError("Edge descriptor layer/KV-head dimensions do not match lifecycle trace")


def admission_task(row: dict[str, str], page: dict[str, str], *, bandwidth: float, burst_bytes: int, pack_bytes_per_cycle: float, page_setup_cycles: float, metadata_bytes_per_page: int) -> dict[str, float]:
    bytes_count = int(row["hot_to_cold_read_bytes"]) + int(row["cold_write_bytes"]) + int(page["metadata_update_bytes"])
    allocations = int(page["metadata_update_bytes"]) / metadata_bytes_per_page
    if int(page["metadata_update_bytes"]) % metadata_bytes_per_page:
        raise ValueError("metadata_update_bytes is not an integral page allocation count")
    bursts = math.ceil(bytes_count / burst_bytes) if bytes_count else 0
    transfer = bursts * burst_bytes / bandwidth
    pack = bytes_count / pack_bytes_per_cycle
    setup = allocations * page_setup_cycles
    return {"bytes": float(bytes_count), "transfer": transfer, "pack": pack, "setup": setup, "service": max(transfer, pack) + setup}


def schedule_admission(tasks: list[dict[str, float]], engine_count: int) -> dict[str, float]:
    """LPT makespan for independent mature-KV admissions on shared pack engines."""
    loads = [0.0] * engine_count
    for task in sorted(tasks, key=lambda item: -item["service"]):
        engine = min(range(engine_count), key=lambda index: loads[index])
        loads[engine] += task["service"]
    return {
        "bytes": sum(task["bytes"] for task in tasks),
        "task_count": float(len(tasks)),
        "transfer": sum(task["transfer"] for task in tasks),
        "pack": sum(task["pack"] for task in tasks),
        "setup": sum(task["setup"] for task in tasks),
        "service": max(loads, default=0.0),
    }


def add_admission(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    """Sequential composition; context prefill is completed before decode step one."""
    return {key: left[key] + right[key] for key in left}


def simulate_edge(source: list[dict[str, str]], replay: dict[tuple[int, int, int], dict[str, str]], manifest: dict[str, Any], *, workload: str, page_tokens: int, bandwidth: float, attention_engines: int, throughput: float, ops_per_token: float, metadata_lookup_bytes: int, metadata_lookup_cycles: float, head_dispatch_cycles: float, scheduler_queue_bytes_per_head: int, admission_engine_count: int, admission_pack_bytes_per_cycle: float, admission_memory_burst_bytes: int, admission_page_setup_cycles: float, deferred_thresholds: list[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kv_bytes, window = int(manifest["kv_bytes_per_layer_head_token"]), int(manifest["sliding_window"])
    metadata_bytes = int(manifest["metadata_bytes_per_cold_page"])
    request_id = str(manifest["request_id"])
    by_call: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in source:
        by_call[int(row["model_call"])].append(row)
    decode_calls = sorted(call for call, rows in by_call.items() if rows[0]["phase"] == "decode")
    if not decode_calls:
        raise ValueError("A3-edge requires observed decode calls")

    def tasks_for(call_rows: list[dict[str, str]]) -> list[dict[str, float]]:
        return [admission_task(row, replay[(int(row["model_call"]), int(row["layer"]), int(row["kv_head"]))], bandwidth=bandwidth, burst_bytes=admission_memory_burst_bytes, pack_bytes_per_cycle=admission_pack_bytes_per_cycle, page_setup_cycles=admission_page_setup_cycles, metadata_bytes_per_page=metadata_bytes) for row in call_rows]

    empty = {"bytes": 0.0, "task_count": 0.0, "transfer": 0.0, "pack": 0.0, "setup": 0.0, "service": 0.0}
    upfront_task_list = [task for call, rows in by_call.items() if call < decode_calls[0] for task in tasks_for(rows)]
    upfront = schedule_admission(upfront_task_list, admission_engine_count)
    variants = policy_variants([], deferred_thresholds)
    cumulative_bytes = {variant["id"]: 0.0 for variant in variants}
    cumulative_cycles = {variant["id"]: 0.0 for variant in variants}
    break_even: dict[str, tuple[int, int] | None] = {variant["id"]: None for variant in variants if variant["baseline"] != "full_kv"}
    decode_history: list[list[dict[str, float]]] = []
    steps: list[dict[str, Any]] = []
    for index, call in enumerate(decode_calls, start=1):
        rows = by_call[call]
        page_rows = [replay[(call, int(row["layer"]), int(row["kv_head"]))] for row in rows]
        current_tasks = tasks_for(rows)
        decode_history.append(current_tasks)
        current = schedule_admission(current_tasks, admission_engine_count)
        full_read = sum(int(row["cache_tokens_after"]) * kv_bytes for row in rows)
        ideal_read = sum((min(window, int(row["cache_tokens_after"])) + int(page["cold_logical_tokens"])) * kv_bytes for row, page in zip(rows, page_rows))
        physical_read = sum((min(window, int(row["cache_tokens_after"])) + int(page["cold_allocated_slots"])) * kv_bytes for row, page in zip(rows, page_rows))
        metadata_read = sum((int(page["cold_allocated_slots"]) // page_tokens) * metadata_lookup_bytes for page in page_rows)
        full_cycles = attention_cycles(page_rows, kind="full", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=0, metadata_lookup_cycles=0.0, pe_count=attention_engines, policy="static_head", head_dispatch_cycles=0.0)
        ideal_cycles = attention_cycles(page_rows, kind="ideal", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=0, metadata_lookup_cycles=0.0, pe_count=attention_engines, policy="static_head", head_dispatch_cycles=0.0)
        static_cycles = attention_cycles(page_rows, kind="physical", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=metadata_lookup_bytes, metadata_lookup_cycles=metadata_lookup_cycles, pe_count=attention_engines, policy="static_head", head_dispatch_cycles=0.0)
        lpt_cycles = attention_cycles(page_rows, kind="physical", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=metadata_lookup_bytes, metadata_lookup_cycles=metadata_lookup_cycles, pe_count=attention_engines, policy="length_aware_head", head_dispatch_cycles=head_dispatch_cycles)
        queue_bytes = scheduler_queue_bytes_per_head * len(rows)
        for variant in variants:
            baseline, kind, threshold = variant["baseline"], variant["policy_kind"], variant["threshold"]
            if baseline == "full_kv":
                active, attention, admission, scheduler_bytes = False, "full", empty, 0
            elif baseline == "ideal_packed_kvzap":
                active, attention, admission, scheduler_bytes = True, "ideal", empty, 0
            else:
                active = policy_active(kind, threshold, decode_step=index, decode_steps=len(decode_calls))
                attention = "physical" if active else "full"
                if not active:
                    admission = empty
                elif kind == "deferred_observed_steps" and index == int(threshold) + 1 and int(threshold) > 0:
                    delayed = [task for task_list in decode_history for task in task_list]
                    admission = schedule_admission(upfront_task_list + delayed, admission_engine_count)
                else:
                    admission = add_admission(upfront, current) if index == 1 else current
                scheduler_bytes = queue_bytes if active and variant["scheduler"] == "length_aware_head" else 0
            attention_value = full_cycles if attention == "full" else ideal_cycles if attention == "ideal" else static_cycles if variant["scheduler"] == "static_head" else lpt_cycles
            read_bytes = full_read if attention == "full" else ideal_read if attention == "ideal" else physical_read
            total_bytes = read_bytes + (metadata_read if attention == "physical" else 0) + admission["bytes"] + scheduler_bytes
            total_cycles = attention_value + admission["service"] + scheduler_bytes / bandwidth
            variant_id = variant["id"]
            cumulative_bytes[variant_id] += total_bytes
            cumulative_cycles[variant_id] += total_cycles
            if baseline != "full_kv" and break_even[variant_id] is None and cumulative_bytes[variant_id] < cumulative_bytes["full_kv"]:
                break_even[variant_id] = (index, call)
            activation = policy_activation_step(kind, threshold, decode_steps=len(decode_calls)) if baseline not in ("full_kv", "ideal_packed_kvzap") else ""
            steps.append({
                "workload": workload, "request_id": request_id, "page_tokens": page_tokens, "bandwidth_bytes_per_cycle": bandwidth, "attention_engine_count": attention_engines, "admission_engine_count": admission_engine_count, "admission_pack_bytes_per_cycle": admission_pack_bytes_per_cycle, "admission_memory_burst_bytes": admission_memory_burst_bytes, "admission_page_setup_cycles": admission_page_setup_cycles, "head_dispatch_cycles": head_dispatch_cycles, "scheduler_queue_bytes_per_head": scheduler_queue_bytes_per_head, "baseline": baseline, "policy_kind": kind, "policy_threshold_decode_steps": threshold, "policy_activation_decode_step": activation, "model_call": call, "decode_step": index, "cache_tokens_after": int(rows[0]["cache_tokens_after"]), "full_read_bytes": full_read, "ideal_packed_read_bytes": ideal_read, "physical_packed_read_bytes": physical_read, "metadata_lookup_bytes": metadata_read if attention == "physical" else 0, "admission_bytes": admission["bytes"], "admission_task_count": admission["task_count"], "admission_transfer_cycles": admission["transfer"], "admission_pack_cycles": admission["pack"], "admission_setup_cycles": admission["setup"], "admission_service_cycles": admission["service"], "scheduler_queue_bytes": scheduler_bytes, "step_total_bytes": total_bytes, "cumulative_total_bytes": cumulative_bytes[variant_id], "cumulative_full_kv_bytes": cumulative_bytes["full_kv"], "cumulative_net_bytes_saved": cumulative_bytes["full_kv"] - cumulative_bytes[variant_id], "attention_cycles": attention_value, "scheduler_cycles": (lpt_cycles - static_cycles) + queue_bytes / bandwidth if attention == "physical" and variant["scheduler"] == "length_aware_head" else 0.0, "step_total_cycles": total_cycles, "cumulative_total_cycles": cumulative_cycles[variant_id],
            })
    summaries = []
    for variant in variants:
        variant_id, baseline, kind, threshold = variant["id"], variant["baseline"], variant["policy_kind"], variant["threshold"]
        full_b, full_c = cumulative_bytes["full_kv"], cumulative_cycles["full_kv"]
        point = break_even.get(variant_id)
        summaries.append({"workload": workload, "request_id": request_id, "page_tokens": page_tokens, "bandwidth_bytes_per_cycle": bandwidth, "attention_engine_count": attention_engines, "admission_engine_count": admission_engine_count, "admission_pack_bytes_per_cycle": admission_pack_bytes_per_cycle, "admission_memory_burst_bytes": admission_memory_burst_bytes, "admission_page_setup_cycles": admission_page_setup_cycles, "head_dispatch_cycles": head_dispatch_cycles, "scheduler_queue_bytes_per_head": scheduler_queue_bytes_per_head, "baseline": baseline, "policy_kind": kind, "policy_threshold_decode_steps": threshold, "policy_activation_decode_step": policy_activation_step(kind, threshold, decode_steps=len(decode_calls)) if baseline not in ("full_kv", "ideal_packed_kvzap") else "", "decode_steps": len(decode_calls), "full_kv_cumulative_bytes": full_b, "baseline_cumulative_bytes": cumulative_bytes[variant_id], "net_bytes_saved": full_b - cumulative_bytes[variant_id], "net_bytes_saved_fraction": (full_b - cumulative_bytes[variant_id]) / full_b if full_b else math.nan, "break_even_decode_step": point[0] if point else "not_reached", "break_even_model_call": point[1] if point else "not_reached", "full_kv_cumulative_cycles": full_c, "baseline_cumulative_cycles": cumulative_cycles[variant_id], "net_cycles_saved": full_c - cumulative_cycles[variant_id], "net_cycles_saved_fraction": (full_c - cumulative_cycles[variant_id]) / full_c if full_c else math.nan, "scheduler_cycle_source": "A3-edge attention-engine plus declared shared admission-engine model"})
    return steps, summaries


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    descriptor = load_architecture_config(args.architecture_config)
    args.deferred_admission_decode_steps = sorted(set(args.deferred_admission_decode_steps + expand_inclusive_range(args.deferred_admission_decode_step_range, flag="--deferred-admission-decode-step-range")))
    engines = args.attention_engine_counts or descriptor["edge_execution"]["attention_engine_candidates"]
    admission_engine_counts, admission_pack_points = resolve_admission_points(args)
    numeric = [*args.page_tokens, *args.bandwidth_bytes_per_cycle, *engines, args.throughput_ops_per_cycle, args.attention_ops_per_kv_token, args.metadata_lookup_bytes_per_page, args.admission_memory_burst_bytes]
    if min(numeric) <= 0 or args.metadata_lookup_cycles_per_page < 0 or args.head_dispatch_cycles < 0 or args.scheduler_queue_bytes_per_head < 0 or args.admission_page_setup_cycles < 0 or any(value < 0 for value in args.deferred_admission_decode_steps) or len(set(args.page_tokens)) != len(args.page_tokens) or len(set(args.bandwidth_bytes_per_cycle)) != len(args.bandwidth_bytes_per_cycle) or len(set(engines)) != len(engines):
        raise ValueError("invalid or duplicate A3-edge assumptions")
    workloads = resolve_workloads(args)
    for _name, lifecycle_dir, _replay_dir in workloads:
        validate(lifecycle_dir)
    freeze = verify_a2_freeze(args.a2_freeze, workloads[0][1], workloads[0][2])
    for _name, lifecycle_dir, replay_dir in workloads[1:]:
        verify_a2_freeze(args.a2_freeze, lifecycle_dir, replay_dir)
    a1 = validate_a1(args.a1_dir)
    all_steps: list[dict[str, Any]] = []
    all_summary: list[dict[str, Any]] = []
    workload_hashes: dict[str, Any] = {}
    for index, (workload, lifecycle_dir, replay_dir) in enumerate(workloads):
        for page in args.page_tokens:
            source, replay, lifecycle_manifest = build_rows(lifecycle_dir, replay_dir, page)
            validate_descriptor_against_trace(descriptor, source, lifecycle_manifest)
            for bandwidth in args.bandwidth_bytes_per_cycle:
                for engine_count in engines:
                    for admission_engine_count in admission_engine_counts:
                        for admission_pack_bytes_per_cycle in admission_pack_points:
                            steps, summaries = simulate_edge(source, replay, lifecycle_manifest, workload=workload, page_tokens=page, bandwidth=bandwidth, attention_engines=engine_count, throughput=args.throughput_ops_per_cycle, ops_per_token=args.attention_ops_per_kv_token, metadata_lookup_bytes=args.metadata_lookup_bytes_per_page, metadata_lookup_cycles=args.metadata_lookup_cycles_per_page, head_dispatch_cycles=args.head_dispatch_cycles, scheduler_queue_bytes_per_head=args.scheduler_queue_bytes_per_head, admission_engine_count=admission_engine_count, admission_pack_bytes_per_cycle=admission_pack_bytes_per_cycle, admission_memory_burst_bytes=args.admission_memory_burst_bytes, admission_page_setup_cycles=args.admission_page_setup_cycles, deferred_thresholds=args.deferred_admission_decode_steps)
                            all_steps.extend(steps)
                            all_summary.extend(summaries)
        key = f"{index:02d}_{workload}"
        workload_hashes[key] = {"lifecycle_dir": str(lifecycle_dir), "page_replay_dir": str(replay_dir), "lifecycle_manifest": sha256(lifecycle_dir / "lifecycle_manifest.json"), "lifecycle_events": sha256(lifecycle_dir / "lifecycle_events.csv"), "page_replay_manifest": sha256(replay_dir / "lifecycle_page_replay_manifest.json"), "page_replay_events": sha256(replay_dir / "lifecycle_page_replay_events.csv")}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "a3_edge_step_results.csv", all_steps, STEP_COLUMNS)
    write_csv(args.output_dir / "a3_edge_baseline_summary.csv", all_summary, SUMMARY_COLUMNS)
    write_csv(args.output_dir / "a3_edge_admission_constraints.csv", derive_admission_constraints(all_summary), CONSTRAINT_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a3-edge-dse-1.1", "git_commit": get_git_commit(), "architecture_config": str(args.architecture_config), "architecture_config_sha256": sha256(args.architecture_config), "workload_suite": args.workload_suite, "workloads": workload_hashes, "a1_dir": str(args.a1_dir), "source_artifact_sha256": {"a2_freeze": sha256(args.a2_freeze), "a1_scheduler_manifest": sha256(args.a1_dir / "scheduler_manifest.json")}, "a2_freeze_status": freeze["freeze_status"], "a1_schema_version": a1["schema_version"], "assumptions": {"page_tokens": args.page_tokens, "bandwidth_bytes_per_cycle": args.bandwidth_bytes_per_cycle, "attention_engine_counts": engines, "throughput_ops_per_cycle": args.throughput_ops_per_cycle, "attention_ops_per_kv_token": args.attention_ops_per_kv_token, "metadata_lookup_bytes_per_page": args.metadata_lookup_bytes_per_page, "metadata_lookup_cycles_per_page": args.metadata_lookup_cycles_per_page, "head_dispatch_cycles": args.head_dispatch_cycles, "scheduler_queue_bytes_per_head": args.scheduler_queue_bytes_per_head, "admission_engine_counts": admission_engine_counts, "admission_pack_bytes_per_cycle_points": admission_pack_points, "admission_memory_burst_bytes": args.admission_memory_burst_bytes, "admission_page_setup_cycles": args.admission_page_setup_cycles, "deferred_admission_decode_steps": args.deferred_admission_decode_steps}, "admission_model": "per-(model_call, layer, KV-head) declared A2 admission bytes are rounded to memory bursts, combined with pack throughput and per-page setup, then LPT-scheduled on shared admission engines; context admission is sequentially charged before decode step one.", "required_followups": ["No generation-equivalence or accuracy result: the deferred policy changes when the packed path becomes active.", "No HBM/DRAM, allocator, latency, throughput, power, area, or PPA measurement is produced.", "Another model requires its own descriptor plus A0/A2/A3-edge evidence; this descriptor is not a cross-model claim."], "notes": ["attention_engine_count is a head-group task service-resource count, not a systolic-array MAC count.", "No cross-engine partial-softmax merge is modeled; all pages of a KV head-group remain on one attention engine per layer.", "All model constants and microarchitecture costs are explicit assumptions, not hardware calibration."]}
    (args.output_dir / "a3_edge_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3-edge modeled {len(all_summary)} summaries and {len(all_steps)} step rows: {args.output_dir}")


if __name__ == "__main__":
    main()
