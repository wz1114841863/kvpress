"""A4.1.2.2 selected-head native-cold ownership integration gate.

The gate is deliberately semantic, small, and untimed.  It poisons selected
mature cold K/V in the native DynamicCache after Route-A has copied the values
into its hot/pending/packed reference state.  Selected decode attention must
therefore use Route-A state: an accidental dense native-cold read becomes NaN.
The native cache allocation remains in place, so this is not a memory-saving
or performance experiment.
"""

from __future__ import annotations

import argparse
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import DynamicCache, pipeline

from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackend, RouteAColdOwnershipAttentionBackend
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4122_SCHEMA = "kvzap-route-a4122-cache-ownership-gate-1.1"


def parse_args(*, description: str = "A4.1.2.2 untimed selected-head native-cold ownership gate; not a storage or performance benchmark.") -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
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
    parser.add_argument("--target-layer", type=int, required=True, help="Exactly one selected layer in the replay source.")
    parser.add_argument("--target-kv-head", type=int, required=True, help="Exactly one selected KV head whose mature native cold cells are poisoned.")
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--require-pending-nonempty", action="store_true")
    parser.add_argument("--require-multi-page-packed", action="store_true")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def manifest_config(args: argparse.Namespace) -> dict[str, Any]:
    return {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}


def run_path(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, backend, args: argparse.Namespace) -> tuple[str, list[int]]:
    seed_everything(args.seed)
    cache = DynamicCache()
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        result = pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True)
    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[0], str) or not isinstance(result[1], list) or not result[1]:
        raise AssertionError("ownership gate did not return an answer plus nonempty generated token IDs")
    return result


def selected_head_coverage(coverage: dict[str, Any], head: int) -> dict[str, Any]:
    rows = [row for row in coverage.get("heads", []) if row.get("kv_head") == head]
    if len(rows) != 1:
        raise AssertionError("ownership gate could not locate exactly one selected-head coverage row")
    return rows[0]


def generated_output_relation(dense_answer: str, dense_tokens: list[int], route_answer: str, route_tokens: list[int]) -> dict[str, Any]:
    """Record, but do not reject, greedy token drift after guarded reductions."""
    first = next((index for index, (dense, route) in enumerate(zip(dense_tokens, route_tokens)) if dense != route), None)
    if first is None and len(dense_tokens) != len(route_tokens):
        first = min(len(dense_tokens), len(route_tokens))
    return {
        "answer_sha256_equal": answer_hash(dense_answer) == answer_hash(route_answer),
        "generated_token_ids_equal": dense_tokens == route_tokens,
        "dense_generated_token_count": len(dense_tokens),
        "route_a_generated_token_count": len(route_tokens),
        "first_generated_token_difference": None if first is None else {
            "index": first,
            "dense_token_id": None if first >= len(dense_tokens) else dense_tokens[first],
            "route_a_token_id": None if first >= len(route_tokens) else route_tokens[first],
        },
    }


def require_route_coverage(*, backend: RouteAColdOwnershipAttentionBackend, args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    backend.assert_replay_complete()
    backend.assert_ownership_guard_complete()
    if backend.policy_decode_calls <= 0 or not backend.comparisons:
        raise AssertionError("ownership gate observed no selected-head Route-A decode attention")
    coverage = backend.coverage()
    selected = selected_head_coverage(coverage, args.target_kv_head)
    if args.require_pending_nonempty and not selected["ever_pending"]:
        raise AssertionError("selected KV head never observed pending retained cold staging")
    if args.require_multi_page_packed and not (selected["ever_multi_page_packed"] and selected["ever_sealed_packed_page"]):
        raise AssertionError("selected KV head never observed a full sealed page plus a second packed page")
    ownership = backend.ownership_summary()
    if ownership["native_cold_slots_physically_freed"]:
        raise AssertionError("ownership gate must not claim native DynamicCache slots were physically freed")
    return coverage, ownership


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layer < 0 or args.target_kv_head < 0 or min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.2.2 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("ownership gate is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    if args.target_layer >= len(language_model.layers):
        raise ValueError("target layer is outside the loaded model")
    kv_heads = int(language_model.layers[args.target_layer].self_attn.config.num_key_value_heads)
    if args.target_kv_head >= kv_heads:
        raise ValueError("target KV head is outside the selected layer")
    layers = (args.target_layer,)
    args.resolved_target_layers = list(layers)
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = manifest_config(args)
    config["replay_event_file_sha256"] = event_sha256
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4122_cache_ownership_started.json", schema_version=A4122_SCHEMA, boundaries=["A4.1.2.2 is an untimed ownership/semantic gate, not a latency or allocator measurement.", "Selected mature native-cache cold K/V is NaN-poisoned after Route-A copies it; selected attention reads hot/pending/packed state.", "Native DynamicCache allocation and dense slot shape remain present, so this does not measure physical storage savings."])

    print("Pass 1/3: Full-KV bypass (zero Route-A admission)...")
    full_answer, full_tokens = run_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=None, args=args)
    assert_no_runtime_mask_state(pipe.model)
    print("Pass 2/3: same-mask dense KVzap selected-head control...")
    dense_backend = DenseSameMaskAttentionBackend(pipe.model, None, layer=args.target_layer, kv_head=args.target_kv_head, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events[args.target_layer])
    dense_answer, dense_tokens = run_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=dense_backend, args=args)
    assert_no_runtime_mask_state(pipe.model)
    dense_backend.assert_replay_complete()
    dense_coverage = dense_backend.coverage()
    if dense_backend.policy_decode_calls <= 0 or not dense_backend.comparisons:
        raise AssertionError("same-mask dense control observed no selected-head policy decode attention")
    print("Pass 3/3: Route-A selected-head native-cold ownership fast path...")
    route_backend = RouteAColdOwnershipAttentionBackend(pipe.model, None, layer=args.target_layer, kv_head=args.target_kv_head, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events[args.target_layer])
    route_answer, route_tokens = run_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=route_backend, args=args)
    assert_no_runtime_mask_state(pipe.model)
    route_coverage, ownership = require_route_coverage(backend=route_backend, args=args)
    output_relation = generated_output_relation(dense_answer, dense_tokens, route_answer, route_tokens)

    outcomes = {
        "full_kv_bypass": {"answer_sha256": answer_hash(full_answer), "generated_token_count": len(full_tokens), "generated_token_ids_sha256": token_ids_hash(full_tokens), "zero_route_a_admission": True},
        "same_mask_dense_replay": {"answer_sha256": answer_hash(dense_answer), "generated_token_count": len(dense_tokens), "generated_token_ids_sha256": token_ids_hash(dense_tokens), "policy_decode_calls": dense_backend.policy_decode_calls, "coverage": dense_coverage},
        "same_mask_route_a_owned_cold_replay": {"answer_sha256": answer_hash(route_answer), "generated_token_count": len(route_tokens), "generated_token_ids_sha256": token_ids_hash(route_tokens), "policy_decode_calls": route_backend.policy_decode_calls, "coverage": route_coverage, "native_cold_ownership": ownership},
    }
    manifest = {"schema_version": A4122_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]}, "outcomes": outcomes, "same_mask_dense_route_generated_output_relation": output_relation, "observational_guards": {"paired_mask_mode": "replayed_dense_mask", "full_kv_bypass_zero_route_a_admission": True, "route_a_predictor_scored_online": False, "replay_mask_consumption_complete": True, "fp32_same_mask_guard": {"rtol": args.rtol, "atol": args.atol}, "max_executed_dtype_ulps": args.max_executed_dtype_ulps, "same_mask_dense_route_generated_output_equality_required": False, "selected_native_mature_cold_values_poisoned": True, "selected_native_cold_read_guard_complete": True, "selected_route_a_decode_output_finite": True, "native_dense_cold_slots_physically_freed": False}, "boundaries": ["This is an A4.1.2.2 semantic ownership gate, not timing, throughput, allocator, HBM traffic, energy, area, frequency, hardware acceleration, or RTL evidence.", "NaN poisoning proves selected mature original K/V is not silently consumed from the native dense cache by the selected Route-A attention path; it does not remove the native dense tensor allocation.", "Full-KV bypass is a policy control. Same-mask dense/Route-A generated output relation is recorded, not required: permitted numerical reduction differences can alter later greedy tokens despite the per-head FP32 numerical guard."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / "a4122_cache_ownership_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.2.2 selected-head native-cold ownership gate passed: {path}")


if __name__ == "__main__":
    main()
