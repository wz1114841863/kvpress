"""A4.1.3.7 untimed Qwen three-layer all-head native-storage semantic gate."""

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
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAQwenExternalColdStorageAttentionBackendSet
from kvpress.route_a_qwen_cache import RouteAQwenMultiLayerExternalColdCache
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4122_cache_ownership_gate import generated_output_relation
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4142_SCHEMA = "kvzap-route-a4142-qwen-multilayer-allhead-native-storage-gate-1.0"
TARGET_LAYERS = (0, 18, 35)


def parse_args(*, description: str = "A4.1.3.7 untimed Qwen layers {0,18,35} all-KV-head native-storage replacement semantic gate; not a performance benchmark.") -> argparse.Namespace:
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
    parser.add_argument("--target-layers", nargs="+", default=[str(layer) for layer in TARGET_LAYERS], help="Must be exactly: 0 18 35.")
    parser.add_argument("--target-kv-head", choices=("all",), default="all", help="Every KV head in every target layer is persistently replaced.")
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--require-any-pending", action="store_true", help="Require pending staging in at least one target-layer/KV-head state.")
    parser.add_argument("--require-any-full-multi-tail-packed", action="store_true", help="Require one target-layer/KV-head state to cover a sealed full page, multi-page state, and a nonempty tail.")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def config(args: argparse.Namespace) -> dict[str, Any]:
    return {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}


def run_path(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, backend, cache, args: argparse.Namespace) -> tuple[str, list[int]]:
    seed_everything(args.seed)
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        result = pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True)
    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[0], str) or not isinstance(result[1], list) or not result[1]:
        raise AssertionError("A4.1.3.7 gate did not return an answer plus nonempty generated token IDs")
    return result


def aggregate_full_multi_tail_page_coverage(coverage: dict[str, Any]) -> dict[str, Any]:
    """Find one layer/head witness; do not require every head to retain cold K/V."""
    witnesses = [
        {"layer": int(layer["layer"]), "kv_head": int(head["kv_head"])}
        for layer in coverage["layers"]
        for head in layer["heads"]
        if bool(head["ever_sealed_packed_page"])
        and bool(head["ever_multi_page_packed"])
        and int(head["max_packed_tail_tokens"]) > 0
    ]
    return {
        "requires_single_layer_head_full_multi_tail": True,
        "witnesses": witnesses,
        "covered": bool(witnesses),
    }


def require_multilayer_replacement(*, backend: RouteAQwenExternalColdStorageAttentionBackendSet, cache: RouteAQwenMultiLayerExternalColdCache, expected_heads: dict[int, tuple[int, ...]], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    backend.assert_replay_complete()
    backend.assert_external_storage_interface_complete()
    adapters = backend.external_adapters_by_layer()
    cache.assert_target_storage_contracts(adapters_by_layer=adapters)
    coverage = backend.coverage()
    rows_by_layer = {int(row["layer"]): row for row in coverage["layers"]}
    if set(rows_by_layer) != set(expected_heads):
        raise AssertionError("multi-layer coverage does not match requested target layers")
    pending_seen = False
    for layer, heads in expected_heads.items():
        rows = rows_by_layer[layer]["heads"]
        if tuple(int(row["kv_head"]) for row in rows) != heads:
            raise AssertionError(f"layer {layer} all-head coverage differs from Qwen KV heads")
        if backend.backends[layer].policy_decode_calls <= 0 or any(int(row["comparison_count"]) <= 0 for row in rows):
            raise AssertionError(f"layer {layer} did not substitute every selected KV head during decode")
        pending_seen = pending_seen or any(bool(row["ever_pending"]) for row in rows)
    if args.require_any_pending and not pending_seen:
        raise AssertionError("no target-layer KV head observed pending retained cold staging")
    page_coverage = aggregate_full_multi_tail_page_coverage(coverage)
    if args.require_any_full_multi_tail_packed and not page_coverage["covered"]:
        raise AssertionError("no target-layer KV head observed a sealed full page plus multi-page state and nonempty tail")
    storage = cache.target_storage_summaries(adapters_by_layer=adapters)
    storage_rows = {int(row["layer"]): row for row in storage["layers"]}
    if set(storage_rows) != set(expected_heads):
        raise AssertionError("persistent cache storage layers differ from requested target layers")
    for layer, heads in expected_heads.items():
        row = storage_rows[layer]
        if tuple(int(head) for head in row["selected_kv_heads"]) != heads:
            raise AssertionError(f"persistent cache selected heads differ at layer {layer}")
        if row["persistent_unselected_kv_heads"] != 0 or row["persistent_selected_native_cold_tensor_tokens"] != 0:
            raise AssertionError(f"persistent cache retained dense target-layer K/V at layer {layer}")
    return coverage, storage, page_coverage


def main(
    *,
    schema_version: str = A4142_SCHEMA,
    phase: str = "A4.1.3.7",
    artifact_stem: str = "a4142_qwen_multilayer_allhead_native_storage",
    required_admission_budget: int | None = 1,
    required_state_flags: tuple[str, ...] = ("require_any_pending",),
) -> None:
    args = parse_args(description=f"{phase} untimed Qwen layers {{0,18,35}} all-KV-head native-storage replacement semantic gate; not a performance benchmark.")
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if tuple(args.target_layers) != tuple(str(layer) for layer in TARGET_LAYERS) or args.target_kv_head != "all":
        raise ValueError(f"{phase} requires --target-layers 0 18 35 --target-kv-head all")
    if required_admission_budget is not None and args.admission_budget != required_admission_budget:
        raise ValueError(f"{phase} requires --admission-budget {required_admission_budget}")
    for flag in required_state_flags:
        if not getattr(args, flag):
            raise ValueError(f"{phase} requires --{flag.replace('_', '-')}")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps) <= 0 or args.window_size < 0:
        raise ValueError(f"invalid {phase} dimensions")
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError(f"{phase} is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=TARGET_LAYERS)
    if source["config"].get("admission_budget") != args.admission_budget:
        raise ValueError("replay source admission budget differs from multi-layer native-storage configuration")
    require_cuda_device(args.device)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    if max(TARGET_LAYERS) >= len(language_model.layers):
        raise ValueError(f"Qwen model has fewer layers than the {phase} target set")
    expected_heads = {layer: tuple(range(int(language_model.layers[layer].self_attn.config.num_key_value_heads))) for layer in TARGET_LAYERS}
    args.resolved_target_layers = list(TARGET_LAYERS)
    args.resolved_target_kv_heads_by_layer = {str(layer): list(heads) for layer, heads in expected_heads.items()}
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    resolved = config(args)
    resolved["replay_event_file_sha256"] = event_sha256
    initialize_output_directory(args.output_dir, config=resolved, git_commit=get_git_commit(), record_name=f"{artifact_stem}_started.json", schema_version=schema_version, boundaries=[
        f"{phase} is an untimed three-layer all-KV-head Qwen semantic cache-interface gate, not a latency or allocator measurement.",
        "At layers 0, 18, and 35, persistent cache storage omits every selected KV head; retained hot/pending/packed state belongs to independent Route-A external adapters.",
        "Qwen receives transient full-shaped attention views only for current API compatibility. They are not persistent cache storage and establish no allocator, HBM, or performance result.",
    ])
    common = dict(layers=TARGET_LAYERS, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events)
    print("Pass 1/3: Full-KV bypass (zero Route-A admission)...")
    full_answer, full_tokens = run_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=None, cache=DynamicCache(), args=args)
    assert_no_runtime_mask_state(pipe.model)
    print(f"Pass 2/3: three-layer all-head same-mask dense KVzap control in layers {list(TARGET_LAYERS)}...")
    dense_backend = DenseSameMaskAttentionBackendSet(pipe.model, None, **common)
    dense_answer, dense_tokens = run_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=dense_backend, cache=DynamicCache(), args=args)
    assert_no_runtime_mask_state(pipe.model)
    dense_backend.assert_replay_complete()
    print(f"Pass 3/3: three-layer all-head Qwen native-storage replacement in layers {list(TARGET_LAYERS)}...")
    route_backend = RouteAQwenExternalColdStorageAttentionBackendSet(pipe.model, None, **common)
    route_cache = RouteAQwenMultiLayerExternalColdCache(selected_kv_heads_by_layer=expected_heads)
    route_answer, route_tokens = run_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=route_backend, cache=route_cache, args=args)
    assert_no_runtime_mask_state(pipe.model)
    route_coverage, storage, page_coverage = require_multilayer_replacement(backend=route_backend, cache=route_cache, expected_heads=expected_heads, args=args)
    relation = generated_output_relation(dense_answer, dense_tokens, route_answer, route_tokens)
    manifest = {
        "schema_version": schema_version, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": resolved, "config_hash": stable_hash(resolved),
        "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]},
        "outcomes": {
            "full_kv_bypass": {"answer_sha256": answer_hash(full_answer), "generated_token_count": len(full_tokens), "generated_token_ids_sha256": token_ids_hash(full_tokens), "zero_route_a_admission": True},
            "same_mask_dense_replay": {"answer_sha256": answer_hash(dense_answer), "generated_token_count": len(dense_tokens), "generated_token_ids_sha256": token_ids_hash(dense_tokens), "policy_decode_calls_by_layer": dense_backend.policy_decode_calls, "coverage": dense_backend.coverage()},
            "same_mask_route_a_qwen_multilayer_allhead_native_storage_replacement": {"answer_sha256": answer_hash(route_answer), "generated_token_count": len(route_tokens), "generated_token_ids_sha256": token_ids_hash(route_tokens), "policy_decode_calls_by_layer": route_backend.policy_decode_calls, "coverage": route_coverage, "aggregate_page_coverage": page_coverage, "native_cold_ownership": route_backend.ownership_summary(), "persistent_cache_storage": storage},
        },
        "same_mask_dense_route_generated_output_relation": relation,
        "observational_guards": {
            "paired_mask_mode": "replayed_dense_mask", "full_kv_bypass_zero_route_a_admission": True, "route_a_predictor_scored_online": False, "replay_mask_consumption_complete": True,
            "fp32_same_mask_guard": {"rtol": args.rtol, "atol": args.atol}, "all_selected_layers_and_kv_heads_substituted": True,
            "all_selected_native_cold_read_guard_complete": True, "persistent_unselected_kv_heads_by_target_layer": 0,
            "persistent_selected_mature_cold_absent": True, "persistent_selected_native_cold_tensor_tokens": 0,
            "transient_attention_view_is_not_persistent_cache": True,
            "required_any_pending_coverage": not args.require_any_pending or any(bool(head["ever_pending"]) for layer in route_coverage["layers"] for head in layer["heads"]),
            "required_any_full_multi_tail_packed_coverage": not args.require_any_full_multi_tail_packed or page_coverage["covered"],
        },
        "boundaries": [
            "Untimed layers {0,18,35} all-KV-head Qwen semantic cache-interface gate only; not timing, throughput, allocator, HBM traffic, energy, area, frequency, hardware acceleration, or RTL evidence.",
            "All persistent selected KV tensors are absent only at the three target layers; non-target Qwen layers retain native cache state. Transient dense-shaped attention views do not establish physical allocation or traffic results.",
            "Same-mask dense/Route-A generated output relation is recorded, not required; only the applicable same-mask numerical guards are hard gates.",
        ], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    path = args.output_dir / f"{artifact_stem}_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{phase} Qwen multi-layer all-head native-storage replacement gate passed: {path}")


if __name__ == "__main__":
    main()
