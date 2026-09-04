"""Untimed A4.1.2.8 all-head forced/independent continuation diagnostic."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import DynamicCache, pipeline

from kvpress.route_a_continuation_diagnostic import apply_route_a_state_guard, first_token_mismatch, prefix_equal_before_step
from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackend, RouteAColdOwnershipAttentionBackend
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import logit_summary, paired_logit_relation
from tools.run_kvzap_route_a4124_multitoken_bridge_gate import assert_any_head_coverage, parse_target_kv_head
from tools.run_kvzap_route_a4127_allhead_activation_diagnostic import requirement
from tools.run_kvzap_route_a412_whole_decode_gate import read_source
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4128_SCHEMA = "kvzap-route-a4128-allhead-continuation-diagnostic-1.0"


def token_ids_digest(token_ids: list[int]) -> str:
    return hashlib.sha256(json.dumps(token_ids, separators=(",", ":")).encode("utf-8")).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.2.8 untimed all-head forced/independent continuation diagnostic; not a benchmark.")
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
    parser.add_argument("--target-layer", type=int, required=True)
    parser.add_argument("--target-kv-head", type=parse_target_kv_head, required=True, help="Must be 'all' for this all-head diagnostic.")
    parser.add_argument("--max-new-tokens", type=int, default=8, help="Fixed token count; must match replay source coverage.")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--require-any-pending", action="store_true")
    parser.add_argument("--require-any-multi-page-packed", action="store_true")
    parser.add_argument("--require-any-full-packed-page", action="store_true")
    parser.add_argument("--require-any-tail-packed-page", action="store_true")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def run_continuation(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, backend, args: argparse.Namespace, forced_token_ids: list[int] | None) -> dict[str, Any]:
    """Run fixed-length continuation; forced mode keeps the generated inputs paired."""
    seed_everything(args.seed)
    cache = DynamicCache()
    logits: list[torch.Tensor] = []
    generated: list[int] = []
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        question_position = torch.arange(int(context_ids.shape[1]), int(context_ids.shape[1]) + int(question_ids.shape[1]), device=pipe.model.device).unsqueeze(0)
        output = pipe.model(input_ids=question_ids, past_key_values=cache, position_ids=question_position, num_logits_to_keep=1)
        logits.append(output.logits[0, -1].detach())
        for step in range(args.max_new_tokens):
            if forced_token_ids is None:
                token = int(logits[-1].argmax().item())
            else:
                token = int(forced_token_ids[step])
            generated.append(token)
            if step + 1 == args.max_new_tokens:
                break
            token_ids = torch.tensor([[token]], dtype=question_ids.dtype, device=pipe.model.device)
            position = torch.tensor([[int(context_ids.shape[1]) + int(question_ids.shape[1]) + step]], device=pipe.model.device)
            output = pipe.model(input_ids=token_ids, past_key_values=cache, position_ids=position, num_logits_to_keep=1)
            logits.append(output.logits[0, -1].detach())
    if len(logits) != args.max_new_tokens or len(generated) != args.max_new_tokens:
        raise AssertionError("continuation did not produce the declared fixed token count")
    return {"logits": logits, "generated_token_ids": generated, "backend": backend}


def assert_all_head_multitoken_bridge(backend, coverage: dict, *, expected_heads: tuple[int, ...], token_count: int, label: str) -> None:
    observed_heads = tuple(int(row["kv_head"]) for row in coverage.get("heads", []))
    if observed_heads != expected_heads:
        raise AssertionError(f"{label} selected KV-head coverage mismatch: observed={observed_heads}, expected={expected_heads}")
    summary = backend.multi_token_comparison_summary()
    expected_comparisons = len(expected_heads) * token_count
    if int(summary["comparison_count"]) != expected_comparisons:
        raise AssertionError(f"{label} multi-token bridge count mismatch: observed={summary['comparison_count']}, expected={expected_comparisons}")


def backend_summary(backend, *, expected_heads: tuple[int, ...], token_count: int, args: argparse.Namespace, require_ownership: bool) -> dict[str, Any]:
    if require_ownership:
        backend.assert_ownership_guard_complete()
    coverage = backend.coverage()
    assert_all_head_multitoken_bridge(backend, coverage, expected_heads=expected_heads, token_count=token_count, label="Route-A" if require_ownership else "same-mask dense")
    if apply_route_a_state_guard(is_route_a_path=require_ownership, requested=args.require_any_pending):
        assert_any_head_coverage(coverage, field="ever_pending", label="pending staging")
    if apply_route_a_state_guard(is_route_a_path=require_ownership, requested=args.require_any_multi_page_packed):
        assert_any_head_coverage(coverage, field="ever_multi_page_packed", label="multi-page packed coverage")
    if apply_route_a_state_guard(is_route_a_path=require_ownership, requested=args.require_any_full_packed_page):
        assert_any_head_coverage(coverage, field="ever_sealed_packed_page", label="sealed full packed-page coverage")
    if apply_route_a_state_guard(is_route_a_path=require_ownership, requested=args.require_any_tail_packed_page):
        assert_any_head_coverage(coverage, field="max_packed_tail_tokens", label="nonempty packed-tail coverage")
    backend.assert_replay_complete()
    return {
        "coverage": coverage,
        "multi_token_attention_comparison": backend.multi_token_comparison_summary(),
        "replay_consumption": backend.replay_consumption_summary(),
        "native_cold_ownership": backend.ownership_summary() if require_ownership else None,
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.target_kv_head is not None:
        raise ValueError("A4.1.2.8 requires --target-kv-head all")
    if args.request_id and not args.input_jsonl:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps, args.top_k) <= 0 or args.target_layer < 0 or args.window_size < 0:
        raise ValueError("invalid continuation-diagnostic dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("diagnostic is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    if args.target_layer >= len(language_model.layers):
        raise ValueError("target layer is outside the loaded model")
    expected_heads = tuple(range(int(language_model.layers[args.target_layer].self_attn.config.num_key_value_heads)))
    args.resolved_target_layers = [args.target_layer]
    args.resolved_target_kv_heads = list(expected_heads)
    events, source, digest = read_source(args.replay_source_dir, args=args, layers=(args.target_layer,))
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if context_ids.shape[1] <= args.window_size or question_ids.shape[1] <= 1:
        raise ValueError("requires protected context and multi-token question")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config["replay_event_file_sha256"] = digest
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4128_allhead_continuation_started.json", schema_version=A4128_SCHEMA, boundaries=["Untimed fixed-length paired continuation; no timing or profiler data.", "Forced continuation uses dense generated token IDs as common inputs; independent greedy continuation may diverge after its first token mismatch.", "No quality, allocator, HBM, physical-memory, throughput, energy, area, hardware, or RTL claim."])
    common = dict(layer=args.target_layer, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events[args.target_layer])
    print("Pass 1/3: all-head causal same-mask dense greedy reference...")
    dense_backend = DenseSameMaskAttentionBackend(pipe.model, None, **common)
    dense = run_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=dense_backend, args=args, forced_token_ids=None)
    assert_no_runtime_mask_state(pipe.model)
    dense_summary = backend_summary(dense_backend, expected_heads=expected_heads, token_count=int(question_ids.shape[1]), args=args, require_ownership=False)
    print("Pass 2/3: all-head Route-A forced common-token continuation...")
    forced_backend = RouteAColdOwnershipAttentionBackend(pipe.model, None, **common)
    forced = run_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=forced_backend, args=args, forced_token_ids=dense["generated_token_ids"])
    assert_no_runtime_mask_state(pipe.model)
    forced_summary = backend_summary(forced_backend, expected_heads=expected_heads, token_count=int(question_ids.shape[1]), args=args, require_ownership=True)
    print("Pass 3/3: all-head Route-A independent greedy continuation...")
    independent_backend = RouteAColdOwnershipAttentionBackend(pipe.model, None, **common)
    independent = run_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=independent_backend, args=args, forced_token_ids=None)
    assert_no_runtime_mask_state(pipe.model)
    independent_summary = backend_summary(independent_backend, expected_heads=expected_heads, token_count=int(question_ids.shape[1]), args=args, require_ownership=True)
    forced_steps = []
    for step, (dense_logit, route_logit) in enumerate(zip(dense["logits"], forced["logits"], strict=True)):
        forced_steps.append({"generated_token_offset": step, "dense_vs_route": paired_logit_relation(dense_logit, route_logit), "dense": logit_summary(dense_logit, top_k=args.top_k), "route_a_forced": logit_summary(route_logit, top_k=args.top_k)})
    independent_steps = []
    for step, (dense_logit, route_logit) in enumerate(zip(dense["logits"], independent["logits"], strict=True)):
        same_input_prefix = prefix_equal_before_step(dense["generated_token_ids"], independent["generated_token_ids"], step)
        independent_steps.append({"generated_token_offset": step, "same_generated_input_prefix_before_step": same_input_prefix, "dense_vs_route": paired_logit_relation(dense_logit, route_logit) if same_input_prefix else None, "route_a_independent": logit_summary(route_logit, top_k=args.top_k)})
    mismatch = first_token_mismatch(dense["generated_token_ids"], independent["generated_token_ids"])
    guard_requirements = {
        "any_pending": requirement(requested=args.require_any_pending, satisfied=any(bool(row["ever_pending"]) for row in forced_summary["coverage"]["heads"])),
        "any_multi_page_packed": requirement(requested=args.require_any_multi_page_packed, satisfied=any(bool(row["ever_multi_page_packed"]) for row in forced_summary["coverage"]["heads"])),
        "any_full_packed_page": requirement(requested=args.require_any_full_packed_page, satisfied=any(bool(row["ever_sealed_packed_page"]) for row in forced_summary["coverage"]["heads"])),
        "any_tail_packed_page": requirement(requested=args.require_any_tail_packed_page, satisfied=any(bool(row["max_packed_tail_tokens"]) for row in forced_summary["coverage"]["heads"])),
    }
    manifest = {
        "schema_version": A4128_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": digest, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"]},
        "diagnostic": {
            "context_token_count": int(context_ids.shape[1]),
            "question_token_count": int(question_ids.shape[1]),
            "max_new_tokens": args.max_new_tokens,
            "same_mask_dense_greedy_reference": {"generated_token_ids": dense["generated_token_ids"], "generated_token_ids_sha256": token_ids_digest(dense["generated_token_ids"]), **dense_summary},
            "route_a_forced_dense_token_continuation": {"forced_token_ids": forced["generated_token_ids"], "forced_token_ids_match_dense": forced["generated_token_ids"] == dense["generated_token_ids"], **forced_summary},
            "forced_common_input_logit_steps": forced_steps,
            "route_a_independent_greedy_continuation": {"generated_token_ids": independent["generated_token_ids"], "generated_token_ids_sha256": token_ids_digest(independent["generated_token_ids"]), "generated_tokens_equal_dense": mismatch is None, "first_generated_token_mismatch": mismatch, **independent_summary},
            "independent_greedy_logit_steps": independent_steps,
        },
        "observational_guards": {"all_selected_kv_heads_bridge_covered": True, "finite_forced_and_independent_logits": True, "forced_common_input_replay_consumption_complete": True, "independent_replay_consumption_complete": True, "native_dense_cold_slots_physically_freed": False},
        "guard_requirements": guard_requirements,
        "boundaries": ["Untimed fixed-length semantic continuation diagnostic, not a performance result.", "Forced common-token logits are paired while inputs remain identical; independent greedy rows after a mismatch are output-impact diagnostics, not same-input numerical comparisons.", "This does not measure quality, Full-KV equivalence, allocator memory, HBM traffic, throughput, energy, area, hardware acceleration, or RTL."],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    path = args.output_dir / "a4128_allhead_continuation_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.2.8 all-head continuation diagnostic completed: {path}")


if __name__ == "__main__":
    main()
