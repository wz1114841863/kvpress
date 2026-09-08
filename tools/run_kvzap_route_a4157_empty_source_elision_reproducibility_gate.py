"""A4.1.7.6 multi-batch reproducibility gate for empty-source elision.

This repeats the semantically certified A4.1.7.4 pair while collecting only
read-only device-wide telemetry outside each timed region.  The telemetry can
contextualize variability but is not a hardware counter or a performance gate.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import pipeline

from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device, summarize_paired_reset_records, summarize_reported_repetitions, write_raw_repetitions
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_whole_decode_gate import read_source
from tools.run_kvzap_route_a4155_empty_source_elision_paired_measurement import BASELINE_PATH, CANDIDATE_PATH, paired_schedule, run_one
from tools.run_kvzap_route_a4156_empty_source_elision_phase_profiler import validate_a4155_manifest
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request


A4157_SCHEMA = "kvzap-route-a4157-empty-source-elision-reproducibility-gate-1.0"
TELEMETRY_FIELDS = ("index", "name", "driver_version", "pstate", "temperature_gpu_c", "utilization_gpu_percent", "utilization_memory_percent", "clocks_sm_mhz", "clocks_mem_mhz", "power_draw_w", "memory_used_mib", "memory_total_mib")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.6 repeated paired Route-A empty-source-elision reproducibility gate with read-only GPU telemetry; Python software only.")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR)
    parser.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    parser.add_argument("--threshold", type=float, default=-4.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--admission-budget", type=int, required=True)
    parser.add_argument("--target-layers", nargs="+", default=["all"], help="Must be the literal all.")
    parser.add_argument("--target-kv-head", choices=("all",), default="all")
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--batches", type=int, default=3)
    parser.add_argument("--warmup-repetitions-per-batch", type=int, default=1)
    parser.add_argument("--measured-repetitions-per-batch", type=int, default=5)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--paired-measurement-manifest", type=Path, required=True, help="Completed matching A4.1.7.4 manifest.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def parse_gpu_telemetry(text: str) -> dict[str, Any]:
    """Parse exactly one CSV GPU row without inferring unavailable values."""
    rows = [line.strip() for line in text.splitlines() if line.strip()]
    if len(rows) != 1:
        raise ValueError("nvidia-smi telemetry must return exactly one GPU row")
    values = [item.strip() for item in rows[0].split(",")]
    if len(values) != len(TELEMETRY_FIELDS):
        raise ValueError("nvidia-smi telemetry field count differs from schema")
    return {key: value for key, value in zip(TELEMETRY_FIELDS, values, strict=True)}


def gpu_telemetry(device: str) -> dict[str, Any]:
    """Read device-global nvidia-smi state outside timed work; never inspect processes."""
    resolved = require_cuda_device(device)
    index = resolved.index if resolved.index is not None else 0
    query = "index,name,driver_version,pstate,temperature.gpu,utilization.gpu,utilization.memory,clocks.sm,clocks.mem,power.draw,memory.used,memory.total"
    try:
        completed = subprocess.run(["nvidia-smi", f"--id={index}", f"--query-gpu={query}", "--format=csv,noheader,nounits"], check=True, capture_output=True, text=True, timeout=15)
        return {"available": True, "fields": parse_gpu_telemetry(completed.stdout)}
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        return {"available": False, "error": f"{type(error).__name__}: {error}"}


def robust_delta_summary(pair_summary: dict[str, Any]) -> dict[str, Any]:
    """Keep robust signed-delta context without silently dropping outliers."""
    rows = pair_summary["pair_rows"]
    result: dict[str, Any] = {"pair_count": len(rows), "metrics": {}}
    for metric in ("wall_ms_candidate_minus_baseline", "cuda_event_ms_candidate_minus_baseline"):
        values = [float(row[metric]) for row in rows]
        median = statistics.median(values)
        absolute_deviations = [abs(value - median) for value in values]
        result["metrics"][metric] = {"median": median, "median_absolute_deviation": statistics.median(absolute_deviations), "raw_values": values}
    return result


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError("A4.1.7.6 requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit, args.batches, args.warmup_repetitions_per_batch, args.measured_repetitions_per_batch) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.7.6 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.1.7.6 is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    layers = tuple(range(len(language_model.layers)))
    expected_heads = {layer: tuple(range(int(language_model.layers[layer].self_attn.config.num_key_value_heads))) for layer in layers}
    args.resolved_target_layers = list(layers)
    args.resolved_target_kv_heads_by_layer = {str(layer): list(heads) for layer, heads in expected_heads.items()}
    args.require_any_pending, args.require_any_full_multi_tail_packed = False, True
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    if source["config"].get("admission_budget") != args.admission_budget:
        raise ValueError("replay source admission budget differs from A4.1.7.6 configuration")
    paired_measurement = validate_a4155_manifest(path=args.paired_measurement_manifest, args=args, event_sha256=event_sha256)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids, question_ids = tokenized["context_ids"].to(pipe.model.device), tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({"replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only", "timed_region": "question_forward_plus_greedy_decode_after_untimed_context_prefill", "pairing": "adjacent_fresh_reset_runs_randomized_within_pair", "telemetry_scope": "device_global_nvidia_smi_before_and_after_timed_region_no_process_inspection"})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4157_empty_source_elision_reproducibility_started.json", schema_version=A4157_SCHEMA, boundaries=["A4.1.7.6 is a multi-batch paired Python-reference software reproducibility gate after completed A4.1.7.4 semantic/timing evidence.", "Device-wide nvidia-smi telemetry is read outside timed regions and does not inspect processes; it only contextualizes run variability.", "Timing, allocator, and telemetry observations are not HBM traffic, throughput, energy, hardware acceleration, or RTL evidence."])
    records, outcomes = [], []
    execution_order = 0
    pairs_per_batch = args.warmup_repetitions_per_batch + args.measured_repetitions_per_batch
    for batch_id in range(args.batches):
        print(f"Batch {batch_id + 1}/{args.batches}...")
        for local_pair, (repetition, warmup, ordered) in enumerate(paired_schedule(warmups=args.warmup_repetitions_per_batch, measured=args.measured_repetitions_per_batch, seed=args.seed + batch_id)):
            pair_id = batch_id * pairs_per_batch + local_pair
            for path, elide in ordered:
                print(f"{('Warmup' if warmup else 'Measured')} batch {batch_id}, pair {pair_id}, repetition {repetition + 1}: {path} (execution_order={execution_order})")
                before = gpu_telemetry(args.device)
                record, outcome = run_one(pipe=pipe, context_ids=context_ids, question_ids=question_ids, path=path, elide_empty_sources=elide, args=args, layers=layers, expected_heads=expected_heads, events=events, event_sha256=event_sha256, repetition=repetition, pair_id=pair_id, execution_order=execution_order, warmup=warmup, expected_token_digest=paired_measurement["token_ids_sha256"])
                after = gpu_telemetry(args.device)
                record.update({"batch_id": batch_id, "telemetry_before": before, "telemetry_after": after})
                outcome["batch_id"] = batch_id
                records.append(record); outcomes.append(outcome); execution_order += 1
    raw_path = write_raw_repetitions(args.output_dir, records)
    batch_summaries = []
    for batch_id in range(args.batches):
        batch_records = [record for record in records if record["batch_id"] == batch_id]
        pairs = summarize_paired_reset_records(batch_records, baseline_path=BASELINE_PATH, candidate_path=CANDIDATE_PATH)
        batch_summaries.append({"batch_id": batch_id, "paired_reset_run_summary": pairs, "robust_delta_summary": robust_delta_summary(pairs)})
    all_pairs = summarize_paired_reset_records(records, baseline_path=BASELINE_PATH, candidate_path=CANDIDATE_PATH)
    summary = summarize_reported_repetitions(records)
    summary.update({"raw_path": raw_path.name, "all_batches_paired_reset_run_summary": all_pairs, "all_batches_robust_delta_summary": robust_delta_summary(all_pairs), "batch_summaries": batch_summaries})
    manifest = {"schema_version": A4157_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"]}, "paired_measurement": paired_measurement, "summary": summary, "outcomes": outcomes, "observational_guards": {"a4155_paired_measurement_verified": True, "execution_only_actual_numerical_guard_work_absent": True, "replay_mask_consumption_complete_each_reset_run": True, "all_layers_all_kv_heads_external_storage_substituted_each_reset_run": True, "persistent_selected_native_cold_absent_each_reset_run": True, "required_any_full_multi_tail_packed_coverage_each_reset_run": True, "fresh_reset_run_token_digests_match_a4154_certificate": True, "adjacent_paired_fresh_reset_runs": True, "multi_batch_distributions_retained": True, "telemetry_recorded_outside_timed_region": True, "allocator_peaks_are_run_local_maxima": True}, "boundaries": ["This is fixed-request multi-batch Python-reference software reproducibility evidence; it cannot establish hardware latency, throughput, or acceleration.", "Telemetry is device-wide nvidia-smi state observed outside timed work, not per-process attribution or hardware traffic counters.", "Allocator values are PyTorch allocated/reserved counters, not HBM capacity or traffic; full-KV and same-mask dense remain distinct prior controls."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / "a4157_empty_source_elision_reproducibility_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.7.6 empty-source-elision reproducibility gate completed: {path}")


if __name__ == "__main__":
    main()
