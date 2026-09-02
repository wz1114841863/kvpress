"""Read-only real-Qwen A4.0 single-layer/head packed-attention integration gate.

This runner intentionally leaves the model's dense Full-KV attention untouched.
It verifies that the A4.0 three-store reference can consume real post-RoPE
cache K/V, the original KVzap scores, and a real decode query without changing
the generated answer.  It is a prerequisite to, not a substitute for, a
policy-on attention backend or A4.1 timing.
"""

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
from transformers.models.qwen3.modeling_qwen3 import apply_rotary_pos_emb

from kvpress import KVzapPress
from kvpress.lifecycle import language_model_layers
from kvpress.route_a_attention import RouteAPackedAttentionState, dense_same_mask_attention
from kvpress.utils import extract_keys_and_values, get_prerope_key_states, get_prerope_query_states
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, file_sha256, get_git_commit, stable_hash, validate_gate_a_evidence
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only A4.0 real-Qwen packed-attention integration gate; no Route-A attention substitution or measurement.")
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
    parser.add_argument("--admission-budget", type=int, default=512)
    parser.add_argument("--target-layer", type=int, default=0)
    parser.add_argument("--target-kv-head", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=8, help="Small integration probe; at least two tokens are required to observe q_len=1 decode.")
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


class RealQwenA40Gate:
    """A non-mutating post-hook for one selected layer and KV head."""

    def __init__(self, model, predictor: KVzapPress, *, layer: int, kv_head: int, threshold: float, window: int, page_tokens: int, admission_budget: int, rtol: float, atol: float) -> None:
        layers = language_model_layers(model)
        if not 0 <= layer < len(layers):
            raise ValueError("target layer is outside the model")
        self.model, self.predictor, self.layer, self.kv_head = model, predictor, layer, kv_head
        self.threshold, self.window, self.page_tokens, self.admission_budget = threshold, window, page_tokens, admission_budget
        self.rtol, self.atol = rtol, atol
        self.state: RouteAPackedAttentionState | None = None
        self._hook = None
        self.comparisons: list[dict[str, float | int]] = []

    def __enter__(self):
        self.predictor.post_init_from_model(self.model)
        self._hook = language_model_layers(self.model)[self.layer].self_attn.register_forward_hook(self._observe, with_kwargs=True)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._hook is not None:
            self._hook.remove()
        self._hook = None
        return None

    def _observe(self, module, _inputs, kwargs, _output) -> None:
        hidden = kwargs.get("hidden_states")
        positions = kwargs.get("cache_position")
        if hidden is None or positions is None or hidden.ndim != 3 or hidden.shape[0] != 1:
            raise AssertionError("A4.0 gate requires [1,T,hidden] hidden states and cache positions")
        flat_positions = positions.detach().reshape(-1)
        if flat_positions.numel() != hidden.shape[1]:
            raise AssertionError("cache positions disagree with query length")
        start = int(flat_positions[0].item())
        if not torch.equal(flat_positions, torch.arange(start, start + hidden.shape[1], device=flat_positions.device, dtype=flat_positions.dtype)):
            raise AssertionError("cache positions are not contiguous")
        scores = self.predictor.score(module, hidden, None, None, None, kwargs)
        if scores.ndim != 3 or scores.shape[0] != 1 or scores.shape[-1] != hidden.shape[1]:
            raise AssertionError("unexpected KVzap score shape")
        keys, values = extract_keys_and_values(kwargs["past_key_values"], self.layer)
        if keys.ndim != 4 or values.shape != keys.shape or keys.shape[0] != 1 or keys.shape[1] != scores.shape[1]:
            raise AssertionError("post-RoPE cache does not match KVzap heads")
        if self.state is None:
            if not 0 <= self.kv_head < keys.shape[1]:
                raise ValueError("target KV head is outside the model")
            self.state = RouteAPackedAttentionState(heads=keys.shape[1], head_dim=keys.shape[-1], window=self.window, page_tokens=self.page_tokens, admission_budget=self.admission_budget)
        self.state.append(keys[0, :, start:start + hidden.shape[1]], values[0, :, start:start + hidden.shape[1]], scores[0] >= self.threshold, start_position=start)
        # Only q_len=1 is a causal decode attention comparison: all cache keys
        # visible to this query are valid, and Route-A state is already updated.
        if hidden.shape[1] != 1:
            return
        position_embeddings = kwargs.get("position_embeddings")
        if position_embeddings is None:
            raise AssertionError("Qwen3 position_embeddings are required for post-RoPE query reconstruction")
        query = get_prerope_query_states(module, hidden)
        raw_key = get_prerope_key_states(module, hidden)
        query, _ = apply_rotary_pos_emb(query, raw_key, *position_embeddings)
        groups = query.shape[1] // keys.shape[1]
        if groups * keys.shape[1] != query.shape[1]:
            raise AssertionError("Qwen GQA heads are not divisible by KV heads")
        route_query = query[0, self.kv_head * groups, 0] * float(module.scaling)
        route = self.state.attention(route_query, head=self.kv_head)
        dense = dense_same_mask_attention(route_query, self.state.same_mask_records(self.kv_head))
        torch.testing.assert_close(route, dense, rtol=self.rtol, atol=self.atol)
        self.comparisons.append({"cache_position": start, "max_abs_difference": float((route - dense).abs().max().item()), **self.state.state_summary(self.kv_head)})


def run(pipe, request: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], RealQwenA40Gate]:
    seed_everything(args.seed)
    normal = pipe(str(request["context"]), question=str(request["question"]), max_new_tokens=args.max_new_tokens, enable_thinking=False)
    assert_no_runtime_mask_state(pipe.model)
    gate = RealQwenA40Gate(pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision), layer=args.target_layer, kv_head=args.target_kv_head, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol)
    seed_everything(args.seed)
    with torch.no_grad(), gate:
        observed = pipe(str(request["context"]), question=str(request["question"]), max_new_tokens=args.max_new_tokens, enable_thinking=False)
    assert_no_runtime_mask_state(pipe.model)
    return normal, observed, gate


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens) <= 0 or args.window_size < 0:
        raise ValueError("invalid integration-gate dimensions")
    if args.max_new_tokens < 2:
        raise ValueError("max-new-tokens must be at least 2 for a decode comparison")
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.0 gate is currently bounded to frozen Qwen3-8B and official MLP revisions")
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
        raise ValueError("context does not exceed the protected hot window")
    print("Pass 1/2: normal dense Full-KV generation...")
    normal, observed, gate = run(pipe, request, args)
    if answer_hash(normal) != answer_hash(observed):
        raise AssertionError("read-only A4.0 integration hook changed the Full-KV answer; no output was written")
    if not gate.comparisons:
        raise AssertionError("no q_len=1 decode comparison was observed; no output was written")
    config = {key: value for key, value in vars(args).items() if key not in {"output_dir", "gate_a_evidence"}}
    manifest = {
        "schema_version": "kvzap-route-a40-real-qwen-integration-gate-1.0", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "gate_a_evidence": gate_a,
        "answer_sha256": answer_hash(normal), "answers_identical": True, "comparison_count": len(gate.comparisons), "comparisons": gate.comparisons,
        "source_artifact_sha256": {"gate_a_manifest": file_sha256(args.gate_a_evidence / "manifest.json"), "gate_a_score_mask": file_sha256(args.gate_a_evidence / "score_mask.npz")},
        "observational_guards": {"model_attention_replaced": False, "dms_press_used": False, "masked_key_indices_created": False, "fake_key_attention_used": False, "model_cache_mutated_by_gate": False},
        "boundaries": ["This is a read-only real-tensor A4.0 integration gate. The model remains dense Full KV and the Route-A result is compared only with its same-mask dense reference.", "It is not policy-on generation, an allocator/HBM counter, timing, latency, throughput, energy, area, frequency, or RTL evidence."],
        "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    path = args.output_dir / "a40_real_qwen_integration_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.0 real-Qwen integration gate passed: {path}")


if __name__ == "__main__":
    main()
