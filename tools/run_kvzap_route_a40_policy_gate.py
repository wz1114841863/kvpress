"""Run the first real policy-on Route-A Qwen decode substitution gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import pipeline

from kvpress import KVzapPress
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAPolicyAttentionBackendSet, compare_original_mask_events
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, file_sha256, get_git_commit, stable_hash, validate_gate_a_evidence
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal policy-on Route-A Qwen decode gate: one layer/KV-head, no fake-key cold fallback, no timing claim.")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR)
    parser.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    parser.add_argument("--gate-a-evidence", type=Path, default=Path("traces/hardware_predictor_gate_a_01"))
    parser.add_argument("--threshold", type=float, default=-4.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--admission-budget", type=int, required=True)
    parser.add_argument("--target-layers", nargs="+", default=["0"], help="One or more layer indices, or exactly 'all' for every model layer.")
    parser.add_argument("--target-kv-head", default="0", help="KV-head index, or 'all' to substitute every KV head in the selected layer.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0, help="Maximum post-cast ULP diagnostic difference. FP32 same-mask rtol/atol remains a mandatory semantic guard.")
    parser.add_argument("--with-same-mask-dense-baseline", action="store_true", help="Run an independent online same-mask dense KVzap control before Route-A and require per-layer original-mask digests to match.")
    parser.add_argument("--mask-drift-example-limit", type=int, default=32, help="Maximum per-layer mask-drift examples saved when the paired online masks differ.")
    parser.add_argument("--require-pending-nonempty", action="store_true", help="Fail unless at least one policy decode comparison has pending retained cold staging.")
    parser.add_argument("--require-all-selected-heads-pending", action="store_true", help="Optional strict coverage assertion. This can legitimately fail when a selected original-mask head retains no mature cold token; use --require-pending-nonempty for the standard all-head gate.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def generate(pipe, request: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    seed_everything(args.seed)
    return pipe(str(request["context"]), question=str(request["question"]), max_new_tokens=args.max_new_tokens, enable_thinking=False)


def resolve_target_layers(values: list[str], layer_count: int) -> tuple[int, ...]:
    if values == ["all"]:
        return tuple(range(layer_count))
    if "all" in values:
        raise ValueError("--target-layers all cannot be combined with explicit layers")
    try:
        layers = tuple(int(value) for value in values)
    except ValueError as error:
        raise ValueError("--target-layers must contain non-negative integers or exactly 'all'") from error
    if not layers or len(set(layers)) != len(layers) or any(not 0 <= layer < layer_count for layer in layers):
        raise ValueError(f"--target-layers must be unique indices in [0,{layer_count})")
    return layers


def mask_summaries(coverage: dict[str, Any]) -> dict[int, tuple[str, int]]:
    return {
        int(layer["layer"]): (str(layer["original_mask_sha256"]), int(layer["original_mask_decision_count"]))
        for layer in coverage["layers"]
    }


def write_mask_drift_diagnostic(*, args: argparse.Namespace, request: dict[str, Any], full: dict[str, Any], dense: dict[str, Any], fast: dict[str, Any], dense_backend: DenseSameMaskAttentionBackendSet, route_backend: RouteAPolicyAttentionBackendSet, report: dict[str, Any]) -> Path:
    """Persist a bounded failed-gate report in the requested fresh directory."""
    config = {key: value for key, value in vars(args).items() if key not in {"output_dir", "gate_a_evidence"}}
    payload = {
        "schema_version": "kvzap-route-a40-online-mask-drift-diagnostic-1.0",
        "status": "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "answer_sha256": {"full_kv_bypass": answer_hash(full), "online_same_mask_dense_kvzap": answer_hash(dense), "route_a_fast_path": answer_hash(fast)},
        "dense_mask_summaries": mask_summaries(dense_backend.coverage()),
        "route_a_mask_summaries": mask_summaries(route_backend.coverage()),
        "mask_drift": report,
        "boundaries": ["This is a failed online-mask-pairing diagnostic, not a successful experiment result.", "Examples contain only layer, KV-head, cache position, predictor score, and boolean keep decision; no token text or K/V tensors are serialized.", "It is not a timing, allocator, HBM, throughput, energy, area, or RTL measurement."],
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    path = args.output_dir / "a40_online_mask_drift_diagnostic.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps, args.mask_drift_example_limit) <= 0 or args.window_size < 0:
        raise ValueError("invalid Route-A policy-gate dimensions")
    if args.max_new_tokens < 2:
        raise ValueError("max-new-tokens must be at least 2")
    if args.target_kv_head != "all":
        try:
            args.target_kv_head = int(args.target_kv_head)
        except ValueError as error:
            raise ValueError("--target-kv-head must be a non-negative integer or 'all'") from error
        if args.target_kv_head < 0:
            raise ValueError("--target-kv-head must be non-negative or 'all'")
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("policy gate is currently bounded to frozen Qwen3-8B and official MLP revisions")
    gate_a = validate_gate_a_evidence(args.gate_a_evidence, model_name=args.model_name, predictor_name=args.predictor_name, threshold=args.threshold, window_size=args.window_size)
    if not gate_a["passed"]:
        raise ValueError("frozen Gate-A evidence validation failed")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    predictor_snapshot = Path(snapshot_download(repo_id=args.predictor_name, revision=args.predictor_revision))
    if predictor_snapshot.name != args.predictor_revision:
        raise ValueError("resolved predictor snapshot differs from frozen revision")
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    if int(tokenized["context_ids"].shape[1]) <= args.window_size:
        raise ValueError("context does not exceed protected hot window")
    total_passes = 3 if args.with_same_mask_dense_baseline else 2
    print(f"Pass 1/{total_passes}: Full-KV bypass reference (zero Route-A admission)...")
    full = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    selected_layers = resolve_target_layers(args.target_layers, len(language_model.layers))
    args.resolved_target_layers = list(selected_layers)
    selected = None if args.target_kv_head == "all" else args.target_kv_head
    dense = None
    dense_backend = None
    dense_coverage = None
    if args.with_same_mask_dense_baseline:
        dense_backend = DenseSameMaskAttentionBackendSet(pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision), layers=selected_layers, kv_head=selected, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps)
        print(f"Pass 2/{total_passes}: independent online same-mask dense KVzap control in layers {list(selected_layers)}...")
        with torch.no_grad(), dense_backend:
            dense = generate(pipe, request, args)
        assert_no_runtime_mask_state(pipe.model)
        if not dense_backend.comparisons or not all(count > 0 for count in dense_backend.policy_decode_calls.values()):
            raise AssertionError("no complete same-mask dense KVzap decode comparison was observed")
        dense_coverage = dense_backend.coverage()
    backend = RouteAPolicyAttentionBackendSet(pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision), layers=selected_layers, kv_head=selected, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps)
    print(f"Pass {total_passes}/{total_passes}: Route-A fast path with policy-on decode substitution in layers {list(selected_layers)}...")
    with torch.no_grad(), backend:
        fast = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    if not backend.comparisons or not all(count > 0 for count in backend.policy_decode_calls.values()):
        raise AssertionError("no complete policy-on decode comparison was observed")
    if args.require_pending_nonempty and not any(int(row["pending_tokens"]) > 0 for row in backend.comparisons):
        raise AssertionError("required non-empty pending cold staging was not observed")
    coverage = backend.coverage()
    if dense_coverage is not None:
        report = compare_original_mask_events(dense_backend.mask_events(), backend.mask_events(), max_examples=args.mask_drift_example_limit)
        if mask_summaries(dense_coverage) != mask_summaries(coverage) or not report["matched"]:
            diagnostic = write_mask_drift_diagnostic(args=args, request=request, full=full, dense=dense, fast=fast, dense_backend=dense_backend, route_backend=backend, report=report)
            first = next((example for layer in report["layers"] for example in layer["examples"]), None)
            raise AssertionError(f"online same-mask dense KVzap and Route-A fast path produced different per-layer original-mask decisions; diagnostic={diagnostic}; first_difference={first}")
    for layer_coverage in coverage["layers"]:
        layer = int(layer_coverage["layer"])
        expected = set(layer_coverage["selected_kv_heads"])
        compared = {int(row["kv_head"]) for row in backend.comparisons if int(row["layer"]) == layer}
        if compared != expected:
            raise AssertionError(f"layer {layer}: not every selected KV head produced a policy comparison: seen={sorted(compared)}, expected={sorted(expected)}")
    if args.require_all_selected_heads_pending:
        for layer_coverage in coverage["layers"]:
            layer = int(layer_coverage["layer"])
            expected = set(layer_coverage["selected_kv_heads"])
            seen = {int(row["kv_head"]) for row in backend.comparisons if int(row["layer"]) == layer and int(row["pending_tokens"]) > 0}
            if seen != expected:
                raise AssertionError(f"layer {layer}: strict pending coverage failed: seen={sorted(seen)}, expected={sorted(expected)}; inspect manifest coverage to distinguish no retained cold token from pending absence")
    config = {key: value for key, value in vars(args).items() if key not in {"output_dir", "gate_a_evidence"}}
    manifest = {
        "schema_version": "kvzap-route-a40-policy-on-qwen-gate-1.3", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "gate_a_evidence": gate_a, "full_kv_bypass_answer_sha256": answer_hash(full), "same_mask_dense_kvzap": None if dense is None or dense_backend is None or dense_coverage is None else {"answer_sha256": answer_hash(dense), "answers_identical_to_full_kv": answer_hash(dense) == answer_hash(full), "policy_decode_call_count_by_layer": dense_backend.policy_decode_calls, "comparisons": dense_backend.comparisons, "policy_coverage": dense_coverage, "original_mask_digest_matches_route_a": True}, "route_a_fast_path_answer_sha256": answer_hash(fast), "answers_identical": answer_hash(full) == answer_hash(fast),
        "policy_decode_call_count_by_layer": backend.policy_decode_calls, "comparisons": backend.comparisons, "policy_coverage": coverage,
        "source_artifact_sha256": {"gate_a_manifest": file_sha256(args.gate_a_evidence / "manifest.json"), "gate_a_score_mask": file_sha256(args.gate_a_evidence / "score_mask.npz")},
        "control_plane": {"full_kv_bypass": "Pass 1 uses no Route-A backend or admission.", "same_mask_dense_kvzap": None if not args.with_same_mask_dense_baseline else "Pass 2 scores original KVzap masks online and substitutes each selected group with hot plus retained dense-cold K/V; it has no pending FIFO, admission service, or packed pages.", "route_a_fast_path": f"Pass {total_passes} substitutes each selected layer/KV-head GQA query group at q_len=1; selected groups read hot/pending/packed only."},
        "observational_guards": {"selected_head_original_attention_called_during_policy_decode": False, "fp32_same_mask_guard": {"rtol": args.rtol, "atol": args.atol}, "executed_dtype_ulp_limit": args.max_executed_dtype_ulps, "dms_press_used": False, "masked_key_indices_created": False, "fake_key_attention_used": False, "model_cache_mutated_by_backend": False},
        "boundaries": ["This is a policy-on generation gate for the declared layers. With --target-kv-head all, every KV-head group in every declared layer is Route-A; undeclared layers remain dense.", "When enabled, the same-mask dense KVzap control is independent of Route-A state and its original-mask digest must match Route-A per selected layer. The Full-KV, same-mask dense, and Route-A answers need not match.", "No field is an allocator/HBM counter, timing, latency, throughput, energy, area, frequency, cross-workload result, or RTL evidence."],
        "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    path = args.output_dir / "a40_policy_on_qwen_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Policy-on Route-A gate passed: {path}")


if __name__ == "__main__":
    main()
