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
from kvpress.route_a_policy_backend import RouteAPolicyAttentionBackend
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
    parser.add_argument("--target-layer", type=int, default=0)
    parser.add_argument("--target-kv-head", default="0", help="KV-head index, or 'all' to substitute every KV head in the selected layer.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--require-pending-nonempty", action="store_true", help="Fail unless at least one policy decode comparison has pending retained cold staging.")
    parser.add_argument("--require-all-selected-heads-pending", action="store_true", help="Optional strict coverage assertion. This can legitimately fail when a selected original-mask head retains no mature cold token; use --require-pending-nonempty for the standard all-head gate.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def generate(pipe, request: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    seed_everything(args.seed)
    return pipe(str(request["context"]), question=str(request["question"]), max_new_tokens=args.max_new_tokens, enable_thinking=False)


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens) <= 0 or args.window_size < 0:
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
    print("Pass 1/2: Full-KV bypass reference (zero Route-A admission)...")
    full = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    selected = None if args.target_kv_head == "all" else args.target_kv_head
    backend = RouteAPolicyAttentionBackend(pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision), layer=args.target_layer, kv_head=selected, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol)
    print("Pass 2/2: selected Route-A fast path with policy-on decode substitution...")
    with torch.no_grad(), backend:
        fast = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    if not backend.comparisons or backend.policy_decode_calls <= 0:
        raise AssertionError("no complete policy-on decode comparison was observed")
    if args.require_pending_nonempty and not any(int(row["pending_tokens"]) > 0 for row in backend.comparisons):
        raise AssertionError("required non-empty pending cold staging was not observed")
    coverage = backend.coverage()
    expected = set(coverage["selected_kv_heads"])
    compared = {int(row["kv_head"]) for row in backend.comparisons}
    if compared != expected:
        raise AssertionError(f"not every selected KV head produced a policy comparison: seen={sorted(compared)}, expected={sorted(expected)}")
    if args.require_all_selected_heads_pending:
        seen = {int(row["kv_head"]) for row in backend.comparisons if int(row["pending_tokens"]) > 0}
        if seen != expected:
            raise AssertionError(f"strict pending coverage failed: seen={sorted(seen)}, expected={sorted(expected)}; inspect manifest coverage to distinguish no retained cold token from pending absence")
    config = {key: value for key, value in vars(args).items() if key not in {"output_dir", "gate_a_evidence"}}
    manifest = {
        "schema_version": "kvzap-route-a40-policy-on-qwen-gate-1.0", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "gate_a_evidence": gate_a, "full_kv_bypass_answer_sha256": answer_hash(full), "route_a_fast_path_answer_sha256": answer_hash(fast), "answers_identical": answer_hash(full) == answer_hash(fast),
        "policy_decode_call_count": backend.policy_decode_calls, "comparisons": backend.comparisons, "policy_coverage": coverage,
        "source_artifact_sha256": {"gate_a_manifest": file_sha256(args.gate_a_evidence / "manifest.json"), "gate_a_score_mask": file_sha256(args.gate_a_evidence / "score_mask.npz")},
        "control_plane": {"full_kv_bypass": "Pass 1 uses no Route-A backend or admission.", "route_a_fast_path": "Pass 2 substitutes each selected KV-head's GQA query group at q_len=1; selected groups read hot/pending/packed only."},
        "observational_guards": {"selected_head_original_attention_called_during_policy_decode": False, "dms_press_used": False, "masked_key_indices_created": False, "fake_key_attention_used": False, "model_cache_mutated_by_backend": False},
        "boundaries": ["This is a minimal single-layer policy-on generation gate. With --target-kv-head all, every KV-head group in the selected layer is Route-A; other layers remain dense.", "The Full-KV and Route-A answers need not match; numerical equality is required only between each substituted head's packed/pending/hot attention and the same-mask dense reference.", "No field is an allocator/HBM counter, timing, latency, throughput, energy, area, frequency, cross-workload result, or RTL evidence."],
        "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    path = args.output_dir / "a40_policy_on_qwen_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Policy-on Route-A gate passed: {path}")


if __name__ == "__main__":
    main()
