"""Untimed A4.1.2.9 replayed-mask multi-layer continuation diagnostic."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import pipeline

from kvpress.route_a_continuation_diagnostic import apply_route_a_state_guard, first_token_mismatch, prefix_equal_before_step
from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAColdOwnershipAttentionBackendSet, RouteANumericalGuardError
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import logit_summary, paired_logit_relation
from tools.run_kvzap_route_a4128_allhead_continuation_diagnostic import run_continuation, token_ids_digest
from tools.run_kvzap_route_a412_whole_decode_gate import read_source, resolve_target_layers
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request


A4129_SCHEMA = "kvzap-route-a4129-multilayer-continuation-diagnostic-1.0"


def parse_args(*, phase: str, default_target_layers: list[str], target_layer_help: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"{phase} untimed all-head multi-layer forced/independent continuation diagnostic; not a benchmark.")
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
    parser.add_argument("--target-layers", nargs="+", default=default_target_layers, help=target_layer_help)
    parser.add_argument("--target-kv-head", default="all", choices=["all"], help="Every KV head is substituted in every selected layer.")
    parser.add_argument("--max-new-tokens", type=int, default=8, help="Fixed token count; must match replay-source coverage.")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--require-any-pending", action="store_true", help="Require pending staging in at least one Route-A selected-layer/head state.")
    parser.add_argument("--require-any-multi-page-packed", action="store_true", help="Require at least one Route-A selected-layer/head state with two packed pages.")
    parser.add_argument("--require-any-full-packed-page", action="store_true", help="Require at least one Route-A selected-layer/head state with a sealed full page.")
    parser.add_argument("--require-any-tail-packed-page", action="store_true", help="Require at least one Route-A selected-layer/head state with a nonempty tail.")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def resolve_diagnostic_layers(values: list[str], layer_count: int) -> tuple[int, ...]:
    """Resolve explicit indices or the literal ``all`` without ambiguity."""
    if values == ["all"]:
        return tuple(range(layer_count))
    if "all" in values:
        raise ValueError("--target-layers all cannot be combined with explicit layer indices")
    return resolve_target_layers(values, layer_count)


def assert_scope(layers: tuple[int, ...], *, layer_count: int, scope: str) -> None:
    if scope == "three_layer" and layers != (0, 18, 35):
        raise ValueError("A4.1.2.9 initial scope is exactly --target-layers 0 18 35")
    if scope == "all_layers" and layers != tuple(range(layer_count)):
        raise ValueError("A4.1.2.10 scope requires --target-layers all")


def assert_scope_selector(values: list[str], *, scope: str) -> None:
    """Keep the all-layer gate auditable: no hand-enumerated substitute."""
    if scope == "all_layers" and values != ["all"]:
        raise ValueError("A4.1.2.10 scope requires the literal --target-layers all")


def expected_heads_by_layer(language_model, layers: tuple[int, ...]) -> dict[int, tuple[int, ...]]:
    return {
        layer: tuple(range(int(language_model.layers[layer].self_attn.config.num_key_value_heads)))
        for layer in layers
    }


def assert_bridge_coverage(backend_set, *, expected_heads: dict[int, tuple[int, ...]], token_count: int, label: str) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    coverage_rows = {int(row["layer"]): row for row in backend_set.coverage()["layers"]}
    if set(coverage_rows) != set(expected_heads):
        raise AssertionError(f"{label} coverage layer set differs from requested layers")
    for layer, heads in expected_heads.items():
        coverage = coverage_rows[layer]
        observed_heads = tuple(int(row["kv_head"]) for row in coverage["heads"])
        if observed_heads != heads:
            raise AssertionError(f"{label} layer {layer} selected KV heads mismatch: observed={observed_heads}, expected={heads}")
        summary = backend_set.backends[layer].multi_token_comparison_summary()
        expected_count = len(heads) * token_count
        if int(summary["comparison_count"]) != expected_count:
            raise AssertionError(f"{label} layer {layer} multi-token bridge count mismatch: observed={summary['comparison_count']}, expected={expected_count}")
        summaries.append({"layer": layer, **summary})
    return {"layers": summaries}


def any_route_a_state(coverage: dict[str, Any], field: str) -> bool:
    return any(bool(head[field]) for layer in coverage["layers"] for head in layer["heads"])


def require_state_coverage(*, coverage: dict[str, Any], args: argparse.Namespace) -> None:
    guards = (
        (args.require_any_pending, "ever_pending", "pending staging"),
        (args.require_any_multi_page_packed, "ever_multi_page_packed", "multi-page packed coverage"),
        (args.require_any_full_packed_page, "ever_sealed_packed_page", "sealed full packed-page coverage"),
        (args.require_any_tail_packed_page, "max_packed_tail_tokens", "nonempty packed-tail coverage"),
    )
    for requested, field, label in guards:
        if requested and not any_route_a_state(coverage, field):
            raise AssertionError(f"required aggregate {label} was not observed in any selected layer/head")


def requirement(*, requested: bool, satisfied: bool) -> dict[str, bool | None]:
    return {"requested": requested, "satisfied": satisfied if requested else None}


def backend_summary(backend_set, *, expected_heads: dict[int, tuple[int, ...]], token_count: int, args: argparse.Namespace, require_ownership: bool) -> dict[str, Any]:
    if require_ownership:
        backend_set.assert_ownership_guard_complete()
    coverage = backend_set.coverage()
    bridge = assert_bridge_coverage(backend_set, expected_heads=expected_heads, token_count=token_count, label="Route-A" if require_ownership else "same-mask dense")
    if apply_route_a_state_guard(is_route_a_path=require_ownership, requested=any((args.require_any_pending, args.require_any_multi_page_packed, args.require_any_full_packed_page, args.require_any_tail_packed_page))):
        require_state_coverage(coverage=coverage, args=args)
    backend_set.assert_replay_complete()
    return {
        "coverage": coverage,
        "multi_token_attention_comparison": bridge,
        "replay_consumption_by_layer": {
            str(layer): backend.replay_consumption_summary()
            for layer, backend in backend_set.backends.items()
        },
        "native_cold_ownership": backend_set.ownership_summary() if require_ownership else None,
    }


def run_or_write_numerical_failure(*, stage: str, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, backend, args: argparse.Namespace, forced_token_ids: list[int] | None, output_dir: Path, artifact_stem: str, schema_version: str, config: dict[str, Any], replay_source: dict[str, Any]):
    """Persist scalar-only ULP-breach context before ending a fresh gate."""
    try:
        return run_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, args=args, forced_token_ids=forced_token_ids)
    except RouteANumericalGuardError as error:
        path = output_dir / f"{artifact_stem}_numerical_guard_failure.json"
        payload = {
            "schema_version": "kvzap-route-a-executed-dtype-guard-failure-1.0",
            "status": "failed_numerical_guard",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "gate_schema_version": schema_version,
            "stage": stage,
            "git_commit": get_git_commit(),
            "config": config,
            "replay_source": replay_source,
            "error": error.details,
            "boundaries": ["Scalar-only numerical-guard failure diagnostic; no K/V, attention, activation, or full logits tensors are serialized.", "The FP32 same-mask guard ran before this execution-dtype ULP failure.", "This is not timing, allocator, HBM, quality, performance, or hardware evidence."],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise AssertionError(f"{error}; diagnostic={path}") from error


def main(*, schema_version: str = A4129_SCHEMA, phase: str = "A4.1.2.9", scope: str = "three_layer", artifact_stem: str = "a4129_multilayer_continuation") -> None:
    if scope == "three_layer":
        default_target_layers, target_layer_help = ["0", "18", "35"], "Initial multi-layer gate is exactly: 0 18 35."
    elif scope == "all_layers":
        default_target_layers, target_layer_help = ["all"], "A4.1.2.10 requires exactly 'all' (all model layers)."
    else:
        raise ValueError(f"unknown multi-layer diagnostic scope: {scope}")
    args = parse_args(phase=phase, default_target_layers=default_target_layers, target_layer_help=target_layer_help)
    assert_scope_selector(args.target_layers, scope=scope)
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id and not args.input_jsonl:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps, args.top_k) <= 0 or args.window_size < 0:
        raise ValueError("invalid multi-layer continuation dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("diagnostic is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    layers = resolve_diagnostic_layers(args.target_layers, len(language_model.layers))
    assert_scope(layers, layer_count=len(language_model.layers), scope=scope)
    args.resolved_target_layers = list(layers)
    expected_heads = expected_heads_by_layer(language_model, layers)
    args.resolved_target_kv_heads_by_layer = {str(layer): list(heads) for layer, heads in expected_heads.items()}
    events, source, digest = read_source(args.replay_source_dir, args=args, layers=layers)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if context_ids.shape[1] <= args.window_size or question_ids.shape[1] <= 1:
        raise ValueError("requires protected context and multi-token question")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config["replay_event_file_sha256"] = digest
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name=f"{artifact_stem}_started.json", schema_version=schema_version, boundaries=["Untimed fixed-length paired continuation; no timing or profiler data.", "Forced continuation uses dense generated token IDs as common inputs; independent greedy continuation can diverge after its first mismatch.", "No quality, allocator, HBM, physical-memory, throughput, energy, area, hardware, or RTL claim."])
    replay_provenance = {"directory": str(args.replay_source_dir), "event_file_sha256": digest, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"]}
    common = dict(layers=layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events)
    print(f"Pass 1/3: all-head causal same-mask dense greedy reference in layers {list(layers)}...")
    dense_backend = DenseSameMaskAttentionBackendSet(pipe.model, None, **common)
    dense = run_or_write_numerical_failure(stage="same_mask_dense_greedy_reference", pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=dense_backend, args=args, forced_token_ids=None, output_dir=args.output_dir, artifact_stem=artifact_stem, schema_version=schema_version, config=config, replay_source=replay_provenance)
    assert_no_runtime_mask_state(pipe.model)
    dense_summary = backend_summary(dense_backend, expected_heads=expected_heads, token_count=int(question_ids.shape[1]), args=args, require_ownership=False)
    print(f"Pass 2/3: all-head Route-A forced common-token continuation in layers {list(layers)}...")
    forced_backend = RouteAColdOwnershipAttentionBackendSet(pipe.model, None, **common)
    forced = run_or_write_numerical_failure(stage="route_a_forced_dense_token_continuation", pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=forced_backend, args=args, forced_token_ids=dense["generated_token_ids"], output_dir=args.output_dir, artifact_stem=artifact_stem, schema_version=schema_version, config=config, replay_source=replay_provenance)
    assert_no_runtime_mask_state(pipe.model)
    forced_summary = backend_summary(forced_backend, expected_heads=expected_heads, token_count=int(question_ids.shape[1]), args=args, require_ownership=True)
    print(f"Pass 3/3: all-head Route-A independent greedy continuation in layers {list(layers)}...")
    independent_backend = RouteAColdOwnershipAttentionBackendSet(pipe.model, None, **common)
    independent = run_or_write_numerical_failure(stage="route_a_independent_greedy_continuation", pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=independent_backend, args=args, forced_token_ids=None, output_dir=args.output_dir, artifact_stem=artifact_stem, schema_version=schema_version, config=config, replay_source=replay_provenance)
    assert_no_runtime_mask_state(pipe.model)
    independent_summary = backend_summary(independent_backend, expected_heads=expected_heads, token_count=int(question_ids.shape[1]), args=args, require_ownership=True)
    forced_steps = [
        {"generated_token_offset": step, "dense_vs_route": paired_logit_relation(dense_logit, route_logit), "dense": logit_summary(dense_logit, top_k=args.top_k), "route_a_forced": logit_summary(route_logit, top_k=args.top_k)}
        for step, (dense_logit, route_logit) in enumerate(zip(dense["logits"], forced["logits"], strict=True))
    ]
    independent_steps = []
    for step, (dense_logit, route_logit) in enumerate(zip(dense["logits"], independent["logits"], strict=True)):
        same_input_prefix = prefix_equal_before_step(dense["generated_token_ids"], independent["generated_token_ids"], step)
        independent_steps.append({"generated_token_offset": step, "same_generated_input_prefix_before_step": same_input_prefix, "dense_vs_route": paired_logit_relation(dense_logit, route_logit) if same_input_prefix else None, "route_a_independent": logit_summary(route_logit, top_k=args.top_k)})
    forced_coverage = forced_summary["coverage"]
    requirements = {
        "any_pending": requirement(requested=args.require_any_pending, satisfied=any_route_a_state(forced_coverage, "ever_pending")),
        "any_multi_page_packed": requirement(requested=args.require_any_multi_page_packed, satisfied=any_route_a_state(forced_coverage, "ever_multi_page_packed")),
        "any_full_packed_page": requirement(requested=args.require_any_full_packed_page, satisfied=any_route_a_state(forced_coverage, "ever_sealed_packed_page")),
        "any_tail_packed_page": requirement(requested=args.require_any_tail_packed_page, satisfied=any_route_a_state(forced_coverage, "max_packed_tail_tokens")),
    }
    manifest = {
        "schema_version": schema_version,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "replay_source": replay_provenance,
        "diagnostic": {
            "context_token_count": int(context_ids.shape[1]), "question_token_count": int(question_ids.shape[1]), "max_new_tokens": args.max_new_tokens,
            "same_mask_dense_greedy_reference": {"generated_token_ids": dense["generated_token_ids"], "generated_token_ids_sha256": token_ids_digest(dense["generated_token_ids"]), **dense_summary},
            "route_a_forced_dense_token_continuation": {"forced_token_ids": forced["generated_token_ids"], "forced_token_ids_match_dense": forced["generated_token_ids"] == dense["generated_token_ids"], **forced_summary},
            "forced_common_input_logit_steps": forced_steps,
            "route_a_independent_greedy_continuation": {"generated_token_ids": independent["generated_token_ids"], "generated_token_ids_sha256": token_ids_digest(independent["generated_token_ids"]), "generated_tokens_equal_dense": independent["generated_token_ids"] == dense["generated_token_ids"], "first_generated_token_mismatch": first_token_mismatch(dense["generated_token_ids"], independent["generated_token_ids"]), **independent_summary},
            "independent_greedy_logit_steps": independent_steps,
        },
        "observational_guards": {"all_selected_layers_and_kv_heads_bridge_covered": True, "finite_forced_and_independent_logits": True, "forced_common_input_replay_consumption_complete": True, "independent_replay_consumption_complete": True, "native_dense_cold_slots_physically_freed": False},
        "guard_requirements": requirements,
        "boundaries": ["Untimed fixed-length semantic continuation diagnostic, not a performance result.", "Forced common-token logits are paired while inputs remain identical; independent rows after a mismatch are output-impact diagnostics, not same-input numerical comparisons.", "This does not measure quality, Full-KV equivalence, allocator memory, HBM traffic, throughput, energy, area, hardware acceleration, or RTL."],
        "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    path = args.output_dir / f"{artifact_stem}_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{phase} multi-layer continuation diagnostic completed: {path}")


if __name__ == "__main__":
    main()
