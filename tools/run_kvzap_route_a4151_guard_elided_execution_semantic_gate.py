"""A4.1.7.0 untimed certification for guard-elided Route-A execution mode."""

from __future__ import annotations

import argparse
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import pipeline

from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import paired_logit_relation
from tools.run_kvzap_route_a4128_allhead_continuation_diagnostic import token_ids_digest
from tools.run_kvzap_route_a412_whole_decode_gate import read_source
from tools.run_kvzap_route_a4142_qwen_multilayer_allhead_native_storage_gate import require_multilayer_replacement
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import EXTERNAL_STORAGE_PATH, make_backend_and_cache, route_guard_summary
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4151_SCHEMA = "kvzap-route-a4151-guard-elided-execution-semantic-gate-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.0 untimed guard-elided Route-A execution semantic gate; not a benchmark.")
    request = parser.add_mutually_exclusive_group(); request.add_argument("--preset", choices=PRESETS, default="retrieval"); request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id"); parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL); parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR); parser.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    parser.add_argument("--threshold", type=float, default=-4.0); parser.add_argument("--window-size", type=int, default=128); parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--admission-budget", type=int, required=True); parser.add_argument("--target-layers", nargs="+", default=["all"]); parser.add_argument("--target-kv-head", choices=("all",), default="all")
    parser.add_argument("--max-new-tokens", type=int, default=8); parser.add_argument("--seed", type=int, default=42); parser.add_argument("--rtol", type=float, default=1e-4); parser.add_argument("--atol", type=float, default=1e-5); parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0); parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--device", default="cuda"); parser.add_argument("--replay-source-dir", type=Path, required=True); parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def continuation(*, pipe, context_ids, question_ids, backend, cache, args, forced_token_ids: list[int] | None) -> dict[str, Any]:
    seed_everything(args.seed); logits, generated = [], []
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        position = torch.arange(int(context_ids.shape[1]), int(context_ids.shape[1]) + int(question_ids.shape[1]), device=pipe.model.device).unsqueeze(0)
        output = pipe.model(input_ids=question_ids, past_key_values=cache, position_ids=position, num_logits_to_keep=1); logits.append(output.logits[0, -1].detach())
        for step in range(args.max_new_tokens):
            token = int(forced_token_ids[step]) if forced_token_ids is not None else int(logits[-1].argmax().item()); generated.append(token)
            if step + 1 == args.max_new_tokens: break
            output = pipe.model(input_ids=torch.tensor([[token]], dtype=question_ids.dtype, device=pipe.model.device), past_key_values=cache, position_ids=torch.tensor([[int(context_ids.shape[1]) + int(question_ids.shape[1]) + step]], device=pipe.model.device), num_logits_to_keep=1); logits.append(output.logits[0, -1].detach())
    if len(logits) != args.max_new_tokens: raise AssertionError("declared continuation horizon was not reached")
    return {"logits": logits, "generated_token_ids": generated}


def verify_backend(*, backend, cache, expected_heads, args, guard_mode: str) -> dict[str, Any]:
    backend.assert_replay_complete()
    if guard_mode == "execution_only" and any(item.same_mask_numerical_guard_enforced for item in backend.backends.values()):
        raise AssertionError("guard-elided backend retained a per-query same-mask numerical guard")
    return {"same_mask_numerical_guard_mode": guard_mode, "external_storage_guard": route_guard_summary(backend=backend, cache=cache, expected_heads=expected_heads, args=args)}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512: raise ValueError("A4.1.7.0 requires --target-layers all --target-kv-head all --admission-budget 512")
    if args.request_id is not None and args.input_jsonl is None: raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit) <= 0 or args.window_size < 0: raise ValueError("invalid A4.1.7.0 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION): raise ValueError("A4.1.7.0 is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}"); pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision: raise ValueError("loaded model revision differs from frozen revision")
    lm = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model; layers = tuple(range(len(lm.layers))); expected_heads = {layer: tuple(range(int(lm.layers[layer].self_attn.config.num_key_value_heads))) for layer in layers}
    args.resolved_target_layers = list(layers); args.resolved_target_kv_heads_by_layer = {str(layer): list(heads) for layer, heads in expected_heads.items()}; args.require_any_pending = False; args.require_any_full_multi_tail_packed = True
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    if source["config"].get("admission_budget") != 512: raise ValueError("replay source budget differs")
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False); context_ids = tokenized["context_ids"].to(pipe.model.device); question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}; config.update({"replay_event_file_sha256": event_sha256, "guarded_reference_mode": "enforce", "execution_mode": "execution_only"})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4151_guard_elided_execution_started.json", schema_version=A4151_SCHEMA, boundaries=["Untimed A4.1.7.0 semantic certification; no timing, allocator, profiler, HBM, throughput, or hardware claim.", "The execution-only path removes per-query same-mask dense/numerical checks but retains replay, Route-A state, external ownership and native-cold poison guards.", "Paired full-model logits are a fixed-request certification check, not a general quality result."])
    runs = {}
    for label, mode, forced in (("guarded_reference", "enforce", None), ("execution_only_forced", "execution_only", None), ("execution_only_independent", "execution_only", None)):
        print(f"Running {label} Route-A external-storage continuation...")
        backend, cache = make_backend_and_cache(path=EXTERNAL_STORAGE_PATH, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, same_mask_numerical_guard_mode=mode)
        forced_ids = runs["guarded_reference"]["generated_token_ids"] if label == "execution_only_forced" else forced
        out = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args, forced_token_ids=forced_ids)
        assert_no_runtime_mask_state(pipe.model); runs[label] = {**out, **verify_backend(backend=backend, cache=cache, expected_heads=expected_heads, args=args, guard_mode=mode)}
    forced_relations = [paired_logit_relation(a, b) for a, b in zip(runs["guarded_reference"]["logits"], runs["execution_only_forced"]["logits"], strict=True)]
    for guarded, execution in zip(runs["guarded_reference"]["logits"], runs["execution_only_forced"]["logits"], strict=True): torch.testing.assert_close(execution, guarded, rtol=args.rtol, atol=args.atol)
    if runs["execution_only_independent"]["generated_token_ids"] != runs["guarded_reference"]["generated_token_ids"]: raise AssertionError("guard-elided independent greedy tokens differ from guarded Route-A reference")
    manifest = {"schema_version": A4151_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"]}, "diagnostic": {label: {key: value for key, value in row.items() if key != "logits"} | {"generated_token_ids_sha256": token_ids_digest(row["generated_token_ids"])} for label, row in runs.items()} | {"guarded_vs_execution_only_forced_logit_steps": forced_relations}, "observational_guards": {"guarded_reference_fp32_same_mask_enforced": True, "execution_only_per_query_same_mask_numerical_guards_absent": True, "replay_consumption_complete": True, "all_layers_all_kv_heads_external_storage_substituted": True, "persistent_selected_native_cold_absent": True, "required_any_full_multi_tail_packed_coverage": True, "forced_full_model_logits_close": True, "independent_greedy_tokens_equal_guarded": True}, "boundaries": ["This is a fixed-request guard-elided semantic certification, not timing or quality evidence.", "A4.1.4/A4.1.6 timing and profiler observations remain separate.", "No HBM, allocator, throughput, energy, hardware, or RTL conclusion."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / "a4151_guard_elided_execution_manifest.json"; path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(f"A4.1.7.0 guard-elided execution semantic gate completed: {path}")


if __name__ == "__main__": main()
