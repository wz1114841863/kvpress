"""Untimed A4.1.2.7 all-head Route-A downstream-activation diagnostic."""

from __future__ import annotations

import argparse
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import torch
import transformers
from transformers import DynamicCache, pipeline

from kvpress.route_a_activation_diagnostic import summarize_layer_activation_relations
from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackend, RouteAColdOwnershipAttentionBackend
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import logit_summary, paired_logit_relation
from tools.run_kvzap_route_a4124_multitoken_bridge_gate import assert_any_head_coverage, assert_complete_selected_head_bridge_coverage, parse_target_kv_head
from tools.run_kvzap_route_a412_whole_decode_gate import read_source
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4127_SCHEMA = "kvzap-route-a4127-allhead-activation-diagnostic-1.0"


def requirement(*, requested: bool, satisfied: bool) -> dict[str, bool | None]:
    """Record request state separately from satisfaction; never use vacuous truth."""
    return {"requested": requested, "satisfied": satisfied if requested else None}


@contextlib.contextmanager
def capture_question_layer_outputs(language_model) -> Iterator[dict[int, torch.Tensor]]:
    """Capture decoder-layer outputs transiently for one question forward only."""
    captured: dict[int, torch.Tensor] = {}
    handles = []

    def make_hook(layer: int):
        def hook(_module, _inputs, output) -> None:
            hidden = output[0] if isinstance(output, tuple) else output
            if not isinstance(hidden, torch.Tensor) or hidden.ndim != 3:
                raise AssertionError(f"decoder layer {layer} returned no [B,T,H] hidden state")
            if layer in captured:
                raise AssertionError(f"decoder layer {layer} executed more than once during one question forward")
            # Transient CPU FP32 copies permit paired comparison after the two
            # forwards. They are summarized below and never written to disk.
            captured[layer] = hidden.detach().to(dtype=torch.float32).cpu()
        return hook

    try:
        for layer, module in enumerate(language_model.layers):
            handles.append(module.register_forward_hook(make_hook(layer)))
        yield captured
    finally:
        for handle in handles:
            handle.remove()


def question_forward_with_layer_capture(*, pipe, language_model, context_ids: torch.Tensor, question_ids: torch.Tensor, backend, args: argparse.Namespace) -> tuple[torch.Tensor, dict[int, torch.Tensor]]:
    """Run untimed prefill plus one question forward, capturing only question layers."""
    seed_everything(args.seed)
    cache = DynamicCache()
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        positions = torch.arange(int(context_ids.shape[1]), int(context_ids.shape[1]) + int(question_ids.shape[1]), device=pipe.model.device).unsqueeze(0)
        with capture_question_layer_outputs(language_model) as captured:
            outputs = pipe.model(input_ids=question_ids, past_key_values=cache, position_ids=positions, num_logits_to_keep=1)
    if set(captured) != set(range(len(language_model.layers))):
        raise AssertionError(f"question layer capture incomplete: observed={sorted(captured)}, expected={list(range(len(language_model.layers)))}")
    if any(tuple(hidden.shape[:2]) != (1, int(question_ids.shape[1])) for hidden in captured.values()):
        raise AssertionError("captured question hidden-state shape differs from [1, question_tokens, hidden]")
    return outputs.logits[0, -1].detach(), captured


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.2.7 untimed all-KV-head downstream-activation diagnostic; not a benchmark.")
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
    parser.add_argument("--max-new-tokens", type=int, default=8)
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


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.target_kv_head is not None:
        raise ValueError("A4.1.2.7 requires --target-kv-head all")
    if args.request_id and not args.input_jsonl:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps, args.top_k) <= 0 or args.target_layer < 0 or args.window_size < 0:
        raise ValueError("invalid activation-diagnostic dimensions")
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
    kv_head_count = int(language_model.layers[args.target_layer].self_attn.config.num_key_value_heads)
    expected_heads = tuple(range(kv_head_count))
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
    initialize_output_directory(
        args.output_dir,
        config=config,
        git_commit=get_git_commit(),
        record_name="a4127_allhead_activation_started.json",
        schema_version=A4127_SCHEMA,
        boundaries=[
            "Untimed context-prefill plus one question-forward diagnostic; no greedy decode.",
            "Forward hooks retain only transient activation tensors and serialize scalar summaries, never hidden states.",
            "Hooks alter execution and this artifact makes no timing, allocator, HBM, physical-memory, or hardware claim.",
        ],
    )
    print("Pass 1/3: Full-KV logits (no activation capture)...")
    from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import first_question_forward
    full_logits = first_question_forward(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=None, args=args)
    assert_no_runtime_mask_state(pipe.model)
    print("Pass 2/3: all-head causal same-mask dense bridge with activation capture...")
    dense_backend = DenseSameMaskAttentionBackend(pipe.model, None, layer=args.target_layer, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events[args.target_layer])
    dense_logits, dense_layers = question_forward_with_layer_capture(pipe=pipe, language_model=language_model, context_ids=context_ids, question_ids=question_ids, backend=dense_backend, args=args)
    assert_no_runtime_mask_state(pipe.model)
    print("Pass 3/3: all-head Route-A owned-cold bridge with activation capture...")
    route_backend = RouteAColdOwnershipAttentionBackend(pipe.model, None, layer=args.target_layer, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events[args.target_layer])
    route_logits, route_layers = question_forward_with_layer_capture(pipe=pipe, language_model=language_model, context_ids=context_ids, question_ids=question_ids, backend=route_backend, args=args)
    assert_no_runtime_mask_state(pipe.model)
    route_backend.assert_ownership_guard_complete()
    dense_coverage, route_coverage = dense_backend.coverage(), route_backend.coverage()
    token_count = int(question_ids.shape[1])
    assert_complete_selected_head_bridge_coverage(dense_coverage, expected_selected_kv_heads=expected_heads, question_token_count=token_count, label="same-mask dense")
    assert_complete_selected_head_bridge_coverage(route_coverage, expected_selected_kv_heads=expected_heads, question_token_count=token_count, label="Route-A")
    if args.require_any_pending:
        assert_any_head_coverage(route_coverage, field="ever_pending", label="pending staging")
    if args.require_any_multi_page_packed:
        assert_any_head_coverage(route_coverage, field="ever_multi_page_packed", label="multi-page packed coverage")
    if args.require_any_full_packed_page:
        assert_any_head_coverage(route_coverage, field="ever_sealed_packed_page", label="sealed full packed-page coverage")
    if args.require_any_tail_packed_page:
        assert_any_head_coverage(route_coverage, field="max_packed_tail_tokens", label="nonempty packed-tail coverage")
    if not torch.isfinite(dense_logits).all() or not torch.isfinite(route_logits).all():
        raise AssertionError("paired same-mask logits are non-finite")
    activation_relation = summarize_layer_activation_relations(dense_layers, route_layers)
    first_difference = activation_relation["first_layer_with_nonzero_difference"]
    if first_difference is not None and first_difference < args.target_layer:
        raise AssertionError("activation difference appeared before the selected ownership layer")
    dense_route_relation = paired_logit_relation(dense_logits, route_logits)
    guards = {
        "all_selected_kv_heads_bridge_covered": True,
        "causal_multitoken_same_mask_dense_bridge_complete": True,
        "causal_multitoken_route_a_bridge_complete": True,
        "finite_same_mask_dense_and_route_logits": True,
        "first_activation_difference_not_before_target_layer": first_difference is None or first_difference >= args.target_layer,
        "native_dense_cold_slots_physically_freed": False,
        "prefix_replay_only": True,
        "same_mask_dense_route_first_argmax_equal": dense_route_relation["argmax_token_id_equal"],
    }
    guard_requirements = {
        "any_pending": requirement(requested=args.require_any_pending, satisfied=any(bool(row["ever_pending"]) for row in route_coverage["heads"])),
        "any_multi_page_packed": requirement(requested=args.require_any_multi_page_packed, satisfied=any(bool(row["ever_multi_page_packed"]) for row in route_coverage["heads"])),
        "any_full_packed_page": requirement(requested=args.require_any_full_packed_page, satisfied=any(bool(row["ever_sealed_packed_page"]) for row in route_coverage["heads"])),
        "any_tail_packed_page": requirement(requested=args.require_any_tail_packed_page, satisfied=any(bool(row["max_packed_tail_tokens"]) for row in route_coverage["heads"])),
    }
    diagnostic: dict[str, Any] = {
        "context_token_count": int(context_ids.shape[1]),
        "question_token_count": token_count,
        "full_kv_bypass": logit_summary(full_logits, top_k=args.top_k),
        "same_mask_dense_replay": {
            "control_path": "causal_multi_token_same_mask_dense_bridge",
            "logits": logit_summary(dense_logits, top_k=args.top_k),
            "coverage": dense_coverage,
            "multi_token_attention_comparison": dense_backend.multi_token_comparison_summary(),
            "replay_consumption": dense_backend.replay_consumption_summary(),
        },
        "same_mask_route_a_owned_cold_replay": {
            "logits": logit_summary(route_logits, top_k=args.top_k),
            "coverage": route_coverage,
            "multi_token_attention_comparison": route_backend.multi_token_comparison_summary(),
            "native_cold_ownership": route_backend.ownership_summary(),
            "replay_consumption": route_backend.replay_consumption_summary(),
        },
        "full_vs_dense": paired_logit_relation(full_logits, dense_logits),
        "dense_vs_route": dense_route_relation,
        "per_layer_question_activation_relation": activation_relation,
    }
    manifest = {
        "schema_version": A4127_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": digest, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"]},
        "diagnostic": diagnostic,
        "observational_guards": guards,
        "guard_requirements": guard_requirements,
        "boundaries": [
            "Untimed paired activation diagnostic only; not a quality, full-decode, timing, allocator, HBM, physical-memory, or hardware result.",
            "Captured activation tensors are transient and omitted from output; only bounded scalar summaries are serialized.",
            "First-argmax equality is recorded rather than required so this diagnostic can localize a finite drift.",
        ],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    path = args.output_dir / "a4127_allhead_activation_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.2.7 all-head activation diagnostic completed: {path}")


if __name__ == "__main__":
    main()
