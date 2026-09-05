"""A4.1.3.3 untimed Qwen cache-interface replacement semantic gate."""

from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import DynamicCache, pipeline

from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackend, RouteAQwenExternalColdStorageAttentionBackend
from kvpress.route_a_qwen_cache import RouteAQwenSingleLayerExternalColdCache
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4122_cache_ownership_gate import generated_output_relation, manifest_config, parse_args, selected_head_coverage
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4138_SCHEMA = "kvzap-route-a4138-qwen-native-storage-replacement-gate-1.0"


def run_path(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, backend, cache, args: Any) -> tuple[str, list[int]]:
    seed_everything(args.seed)
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        result = pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True)
    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[0], str) or not isinstance(result[1], list) or not result[1]:
        raise AssertionError("A4.1.3.3 gate did not return an answer plus nonempty generated token IDs")
    return result


def require_replacement_contract(*, backend: RouteAQwenExternalColdStorageAttentionBackend, cache: RouteAQwenSingleLayerExternalColdCache, args: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    backend.assert_replay_complete()
    backend.assert_external_storage_interface_complete()
    cache.assert_target_storage_contract(adapter=backend.external_cold_storage)
    if backend.policy_decode_calls <= 0 or not backend.comparisons:
        raise AssertionError("A4.1.3.3 observed no selected-head Route-A decode attention")
    coverage = backend.coverage()
    selected = selected_head_coverage(coverage, args.target_kv_head)
    if args.require_pending_nonempty and not selected["ever_pending"]:
        raise AssertionError("selected KV head never observed pending retained cold staging")
    if args.require_multi_page_packed and not (selected["ever_multi_page_packed"] and selected["ever_sealed_packed_page"]):
        raise AssertionError("selected KV head never observed a full sealed page plus a second packed page")
    ownership = backend.ownership_summary()
    storage = cache.target_storage_summary(adapter=backend.external_cold_storage)
    if storage["persistent_selected_native_cold_tensor_tokens"] != 0 or not storage["persistent_selected_mature_cold_absent"]:
        raise AssertionError("replacement cache retains selected mature cold K/V")
    return coverage, ownership, storage


def main() -> None:
    args = parse_args(description="A4.1.3.3 untimed Qwen single layer/head native-storage replacement semantic gate; not a performance benchmark.")
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layer != 0:
        raise ValueError("A4.1.3.3 prototype requires --target-layer 0")
    if args.target_kv_head < 0 or min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.3.3 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.1.3.3 is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    kv_heads = int(language_model.layers[0].self_attn.config.num_key_value_heads)
    if args.target_kv_head >= kv_heads:
        raise ValueError("target KV head is outside layer-zero K/V heads")
    layers = (0,)
    args.resolved_target_layers = [0]
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = manifest_config(args)
    config["replay_event_file_sha256"] = event_sha256
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4138_qwen_native_storage_replacement_started.json", schema_version=A4138_SCHEMA, boundaries=[
        "A4.1.3.3 is an untimed Qwen cache-interface semantic gate, not a latency or allocator measurement.",
        "At target layer zero, persistent cache storage has dense K/V only for unselected heads; selected mature cold K/V is absent and Route-A external state owns retained cold reads.",
        "Qwen attention receives a transient dense-shaped view solely to satisfy its current interface. That view is not persistent cache storage and does not establish allocator, HBM, or performance benefit.",
    ])
    common = dict(layer=0, kv_head=args.target_kv_head, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events[0])
    print("Pass 1/3: Full-KV bypass (zero Route-A admission)...")
    full_answer, full_tokens = run_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=None, cache=DynamicCache(), args=args)
    assert_no_runtime_mask_state(pipe.model)
    print("Pass 2/3: same-mask dense KVzap selected-head control...")
    dense_backend = DenseSameMaskAttentionBackend(pipe.model, None, **common)
    dense_answer, dense_tokens = run_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=dense_backend, cache=DynamicCache(), args=args)
    assert_no_runtime_mask_state(pipe.model)
    dense_backend.assert_replay_complete()
    if dense_backend.policy_decode_calls <= 0 or not dense_backend.comparisons:
        raise AssertionError("same-mask dense control observed no selected-head policy decode attention")
    print("Pass 3/3: Qwen Route-A native-storage replacement interface...")
    route_backend = RouteAQwenExternalColdStorageAttentionBackend(pipe.model, None, **common)
    route_cache = RouteAQwenSingleLayerExternalColdCache(target_layer=0, selected_kv_head=args.target_kv_head)
    route_answer, route_tokens = run_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=route_backend, cache=route_cache, args=args)
    assert_no_runtime_mask_state(pipe.model)
    route_coverage, ownership, storage = require_replacement_contract(backend=route_backend, cache=route_cache, args=args)
    relation = generated_output_relation(dense_answer, dense_tokens, route_answer, route_tokens)
    manifest = {
        "schema_version": A4138_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]},
        "outcomes": {
            "full_kv_bypass": {"answer_sha256": answer_hash(full_answer), "generated_token_count": len(full_tokens), "generated_token_ids_sha256": token_ids_hash(full_tokens), "zero_route_a_admission": True},
            "same_mask_dense_replay": {"answer_sha256": answer_hash(dense_answer), "generated_token_count": len(dense_tokens), "generated_token_ids_sha256": token_ids_hash(dense_tokens), "policy_decode_calls": dense_backend.policy_decode_calls, "coverage": dense_backend.coverage()},
            "same_mask_route_a_qwen_native_storage_replacement": {"answer_sha256": answer_hash(route_answer), "generated_token_count": len(route_tokens), "generated_token_ids_sha256": token_ids_hash(route_tokens), "policy_decode_calls": route_backend.policy_decode_calls, "coverage": route_coverage, "native_cold_ownership": ownership, "persistent_cache_storage": storage},
        },
        "same_mask_dense_route_generated_output_relation": relation,
        "observational_guards": {
            "paired_mask_mode": "replayed_dense_mask", "full_kv_bypass_zero_route_a_admission": True, "route_a_predictor_scored_online": False, "replay_mask_consumption_complete": True,
            "fp32_same_mask_guard": {"rtol": args.rtol, "atol": args.atol}, "selected_native_cold_read_guard_complete": True,
            "persistent_selected_mature_cold_absent": True, "persistent_selected_native_cold_tensor_tokens": 0,
            "transient_attention_view_is_not_persistent_cache": True,
        },
        "boundaries": [
            "Untimed single-layer/head Qwen semantic cache-interface gate only; it is not timing, throughput, allocator, HBM traffic, energy, area, frequency, hardware acceleration, or RTL evidence.",
            "The target cache persistently omits selected mature cold K/V, but Qwen's current dense attention interface receives a transient full-shaped view. No physical allocation or traffic conclusion follows without separate measurement.",
            "Same-mask dense/Route-A generated output relation is recorded, not required; guarded reductions may alter later greedy tokens.",
        ], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    path = args.output_dir / "a4138_qwen_native_storage_replacement_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.3.3 Qwen native-storage replacement gate passed: {path}")


if __name__ == "__main__":
    main()
