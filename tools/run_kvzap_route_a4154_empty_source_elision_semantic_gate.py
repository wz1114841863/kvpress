"""A4.1.7.3 untimed semantic gate for Route-A empty-source elision."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import torch
import transformers
from transformers import pipeline

from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import paired_logit_relation
from tools.run_kvzap_route_a4128_allhead_continuation_diagnostic import token_ids_digest
from tools.run_kvzap_route_a412_whole_decode_gate import read_source
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import make_backend_and_cache
from tools.run_kvzap_route_a4151_guard_elided_execution_semantic_gate import continuation
from tools.run_kvzap_route_a4152_certified_execution_mode_whole_decode_measurement import validate_route_certificate, verify_backend
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request


A4154_SCHEMA = "kvzap-route-a4154-empty-source-elision-semantic-gate-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.3 untimed Route-A empty-source-elision semantic gate; not a timing benchmark.")
    request = parser.add_mutually_exclusive_group(); request.add_argument("--preset", choices=PRESETS, default="retrieval"); request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id"); parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL); parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR); parser.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    parser.add_argument("--threshold", type=float, default=-4.0); parser.add_argument("--window-size", type=int, default=128); parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--admission-budget", type=int, required=True); parser.add_argument("--target-layers", nargs="+", default=["all"]); parser.add_argument("--target-kv-head", choices=("all",), default="all")
    parser.add_argument("--max-new-tokens", type=int, default=8); parser.add_argument("--seed", type=int, default=42); parser.add_argument("--rtol", type=float, default=1e-4); parser.add_argument("--atol", type=float, default=1e-5); parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0); parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--device", default="cuda"); parser.add_argument("--replay-source-dir", type=Path, required=True); parser.add_argument("--route-a-execution-certification", type=Path, required=True); parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def run_route(*, pipe, context_ids, question_ids, layers, expected_heads, events, args, elide_empty_sources: bool, forced_token_ids=None):
    calls: Counter[str] = Counter()
    def measure(name, operation): calls[name] += 1; return operation()
    backend, cache = make_backend_and_cache(path=EXTERNAL_STORAGE_PATH, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, component_measure=measure, same_mask_numerical_guard_mode="execution_only", elide_empty_sources=elide_empty_sources)
    run = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args, forced_token_ids=forced_token_ids)
    assert_no_runtime_mask_state(pipe.model)
    guard = verify_backend(path=EXTERNAL_STORAGE_PATH, backend=backend, cache=cache, expected_heads=expected_heads, args=args)
    return {**run, "guard": guard, "component_call_counts": dict(sorted(calls.items())), "empty_source_elision": backend.empty_source_elision_summary()}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None: raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512: raise ValueError("A4.1.7.3 requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit) <= 0 or args.window_size < 0: raise ValueError("invalid A4.1.7.3 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION): raise ValueError("A4.1.7.3 is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}"); pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision: raise ValueError("loaded model revision differs from frozen revision")
    lm = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model; layers = tuple(range(len(lm.layers))); expected_heads = {layer: tuple(range(int(lm.layers[layer].self_attn.config.num_key_value_heads))) for layer in layers}
    args.resolved_target_layers = list(layers); args.resolved_target_kv_heads_by_layer = {str(layer): list(heads) for layer, heads in expected_heads.items()}; args.require_any_pending = False; args.require_any_full_multi_tail_packed = True
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    if source["config"].get("admission_budget") != args.admission_budget: raise ValueError("replay source admission budget differs")
    route_certificate = validate_route_certificate(path=args.route_a_execution_certification, args=args, event_sha256=event_sha256)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False); context_ids = tokenized["context_ids"].to(pipe.model.device); question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}; config.update({"replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only", "baseline_elide_empty_sources": False, "candidate_elide_empty_sources": True})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4154_empty_source_elision_started.json", schema_version=A4154_SCHEMA, boundaries=["Untimed A4.1.7.3 semantic gate; no timing, allocator, profiler, HBM, throughput, or hardware claim.", "Candidate elides only empty Route-A source partials and retains replay, external ownership, page, native-cold poison and execution-only guards.", "Paired logits/tokens certify one fixed replay/request only."])
    print("Pass 1/3: Route-A execution-only baseline without empty-source elision..."); baseline = run_route(pipe=pipe, context_ids=context_ids, question_ids=question_ids, layers=layers, expected_heads=expected_heads, events=events, args=args, elide_empty_sources=False)
    print("Pass 2/3: Route-A execution-only empty-source-elision forced-token pair..."); elided_forced = run_route(pipe=pipe, context_ids=context_ids, question_ids=question_ids, layers=layers, expected_heads=expected_heads, events=events, args=args, elide_empty_sources=True, forced_token_ids=baseline["generated_token_ids"])
    print("Pass 3/3: Route-A execution-only empty-source-elision independent greedy..."); elided_independent = run_route(pipe=pipe, context_ids=context_ids, question_ids=question_ids, layers=layers, expected_heads=expected_heads, events=events, args=args, elide_empty_sources=True)
    relations = [paired_logit_relation(a, b) for a, b in zip(baseline["logits"], elided_forced["logits"], strict=True)]
    for left, right in zip(baseline["logits"], elided_forced["logits"], strict=True): torch.testing.assert_close(left, right, rtol=args.rtol, atol=args.atol)
    if elided_independent["generated_token_ids"] != baseline["generated_token_ids"]: raise AssertionError("empty-source-elided independent greedy tokens differ from baseline")
    def total(run, suffix): return sum(value for name, value in run["component_call_counts"].items() if name.endswith(suffix))
    skip = elided_forced["empty_source_elision"]
    if sum(int(row["pending_skip_count"]) for row in skip["layers"]) <= 0: raise AssertionError("candidate never observed an empty pending-source skip")
    merge_evaluations = total(elided_forced, "route_a_online_softmax_merge")
    for source_name in ("hot", "pending", "packed"):
        partials = total(elided_forced, f"route_a_attention_{source_name}")
        skips = total(elided_forced, f"route_a_empty_source_skip_{source_name}")
        if partials + skips != merge_evaluations:
            raise AssertionError(f"{source_name} source accounting differs from merge evaluations: partials={partials}, skips={skips}, merges={merge_evaluations}")
    if total(elided_forced, "route_a_attention_hot") <= 0 or total(elided_forced, "route_a_attention_packed") <= 0: raise AssertionError("candidate failed to read nonempty hot or packed Route-A sources")
    manifest = {"schema_version": A4154_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"]}, "route_a_execution_certificate": route_certificate, "diagnostic": {label: {key: value for key, value in run.items() if key != "logits"} | {"generated_token_ids_sha256": token_ids_digest(run["generated_token_ids"])} for label, run in {"baseline": baseline, "elided_forced": elided_forced, "elided_independent": elided_independent}.items()} | {"baseline_vs_elided_forced_logit_steps": relations, "candidate_source_accounting": {source_name: {"partial_attention_calls": total(elided_forced, f"route_a_attention_{source_name}"), "empty_source_skip_calls": total(elided_forced, f"route_a_empty_source_skip_{source_name}"), "merge_evaluations": merge_evaluations} for source_name in ("hot", "pending", "packed")}}, "observational_guards": {"execution_only_actual_numerical_guard_work_absent": True, "replay_consumption_complete": True, "all_layers_all_kv_heads_external_storage_substituted": True, "persistent_selected_native_cold_absent": True, "required_any_full_multi_tail_packed_coverage": True, "forced_full_model_logits_close": True, "independent_greedy_tokens_equal_baseline": True, "empty_pending_source_skip_observed": True, "source_partial_or_skip_accounting_matches_merge": True, "nonempty_hot_and_packed_attention_observed": True}, "boundaries": ["This is fixed-request empty-source-elision semantic evidence only.", "It does not measure runtime, HBM traffic, allocator memory, throughput, energy, hardware, or RTL benefit."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / "a4154_empty_source_elision_manifest.json"; path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(f"A4.1.7.3 empty-source-elision semantic gate completed: {path}")


if __name__ == "__main__": main()
