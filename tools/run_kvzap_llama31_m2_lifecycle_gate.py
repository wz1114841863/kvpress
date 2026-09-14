#!/usr/bin/env python3
"""M2 all-layer Route-A lifecycle portability gate for Nous Llama 3.1 8B.

Dense attention is the sole online mask source.  Route-A replays its decisions
exactly once at two explicit *functional-reference* admission points: budget
one exposes pending staging; budget 512 exposes packed-page state.  Neither is
a hardware parameter or a performance measurement.
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

from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAPolicyAttentionBackendSet
from tools.export_kvzap_predictor_trace import assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_llama31_m1_semantic_gate import (
    EXPECTED_STRUCTURE, M1_SCHEMA, answer_hash, assert_all_layer_head_coverage,
    assert_numerical_guard_work, make_predictor, read_completed_m0,
    source_coverage, validate_runtime_structure,
)
from tools.run_kvzap_trace import PRESETS, build_builtin_request, load_jsonl_request, seed_everything
from tools.validate_kvzap_llama31_m0_provenance import DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION, OFFICIAL_PREDICTOR_REPO


M2_SCHEMA = "kvzap-llama31-m2-lifecycle-gate-1.0"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M2 all-layer/all-KV-head Route-A lifecycle gate for Nous Llama 3.1 8B; functional state evidence, not a benchmark.")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--m0-manifest", type=Path, required=True)
    parser.add_argument("--m1-manifest", type=Path, required=True)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_REPO)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--predictor-repo-id-override", required=True)
    parser.add_argument("--threshold", type=float, default=-7.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, required=True, help="Functional-reference page granularity; not a hardware selection.")
    parser.add_argument("--pending-admission-budget", type=int, required=True, help="Must be functional point 1; not a hardware size.")
    parser.add_argument("--packing-admission-budget", type=int, required=True, help="Must be functional point 512; not a hardware size.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def read_completed_m1(path: Path, *, m0_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"M1 manifest is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != M1_SCHEMA or report.get("status") != "complete":
        raise ValueError("M2 requires a completed kvzap-llama31-m1-semantic-gate-1.0 manifest")
    config, provenance, guards = report.get("config"), report.get("m0_provenance"), report.get("observational_guards")
    if not isinstance(config, dict) or not isinstance(provenance, dict) or not isinstance(guards, dict):
        raise ValueError("M1 manifest lacks configuration/provenance/guard sections")
    expected = {"model_name": DEFAULT_MODEL_REPO, "model_revision": DEFAULT_MODEL_REVISION, "predictor_repo_id_override": OFFICIAL_PREDICTOR_REPO, "threshold": -7.0, "window_size": 128, "predictor_model_type": "linear", "target_layers": "all", "target_kv_heads": "all"}
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"M1 {key} differs from the fixed M2 contract: {config.get(key)!r}")
    if provenance.get("manifest_sha256") != m0_sha256:
        raise ValueError("M1 does not hash-bind the supplied completed M0 manifest")
    required = ("m0_complete_explicit_override_bound", "all_32_layers_and_all_8_kv_heads_selected", "all_selected_groups_have_policy_comparisons", "same_mask_dense_events_replayed_exactly_once_by_route_a", "same_mask_fp32_and_executed_dtype_guards_executed", "route_a_hot_service_observed")
    if not all(guards.get(name) is True for name in required):
        raise ValueError("M1 prerequisite guard is absent or false")
    if report.get("predictor_snapshot", {}).get("repo_id") != OFFICIAL_PREDICTOR_REPO:
        raise ValueError("M1 predictor repository differs from the reviewed official Linear predictor")
    revision = config.get("predictor_revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError("M1 lacks a fixed predictor revision")
    return report


def final_states(backend: RouteAPolicyAttentionBackendSet, *, layers: int, heads: int) -> list[dict[str, Any]]:
    result = []
    for layer in range(layers):
        state = backend.backends[layer].state
        if state is None or state.heads != heads:
            raise AssertionError(f"layer {layer} lacks a complete Route-A state")
        state.assert_conservation()
        result.append({"layer": layer, "next_position": state.next_position, **state.mask_summary(), "heads": [{"kv_head": head, **state.state_summary(head)} for head in range(heads)]})
    return result


def page_witness(coverage: dict[str, Any]) -> dict[str, Any]:
    witnesses = [{"layer": int(layer["layer"]), "kv_head": int(head["kv_head"])} for layer in coverage["layers"] for head in layer["heads"] if bool(head["ever_sealed_packed_page"]) and bool(head["ever_multi_page_packed"]) and int(head["max_packed_tail_tokens"]) > 0]
    return {"requires_one_full_multi_tail_witness": True, "covered": bool(witnesses), "witnesses": witnesses}


def generate(pipe, request: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    seed_everything(args.seed)
    return pipe(str(request["context"]), question=str(request["question"]), max_new_tokens=args.max_new_tokens, enable_thinking=False)


def run_point(*, name: str, budget: int, pipe, request: dict[str, Any], args: argparse.Namespace, revision: str, layers: int, heads: int) -> dict[str, Any]:
    selected_layers = tuple(range(layers))
    predictor = make_predictor(predictor_revision=revision, override=args.predictor_repo_id_override)
    dense_backend = DenseSameMaskAttentionBackendSet(pipe.model, predictor, layers=selected_layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps)
    print(f"M2 {name}: online same-mask dense source, admission budget={budget}...")
    with torch.no_grad(), dense_backend:
        dense = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    if predictor.kvzap_model_name != OFFICIAL_PREDICTOR_REPO:
        raise AssertionError(f"M2 {name}: dense source did not use the explicit official predictor override")
    dense_coverage = dense_backend.coverage()
    assert_all_layer_head_coverage(dense_coverage, expected_layers=layers, expected_kv_heads=heads, label=f"M2 {name} dense")
    assert_numerical_guard_work(dense_backend.same_mask_numerical_guard_work_summary(), layers, label=f"M2 {name} dense")
    route_backend = RouteAPolicyAttentionBackendSet(pipe.model, None, layers=selected_layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=dense_backend.mask_events())
    print(f"M2 {name}: Route-A exact-mask replay, admission budget={budget}...")
    with torch.no_grad(), route_backend:
        route = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    route_backend.assert_replay_complete()
    if dense_backend.mask_events() != route_backend.mask_events():
        raise AssertionError(f"M2 {name}: replay differs from online dense event source")
    coverage = route_backend.coverage()
    assert_all_layer_head_coverage(coverage, expected_layers=layers, expected_kv_heads=heads, label=f"M2 {name} Route-A")
    assert_numerical_guard_work(route_backend.same_mask_numerical_guard_work_summary(), layers, label=f"M2 {name} Route-A")
    sources = source_coverage(route_backend.comparisons)
    if not sources["hot_observed"] or not sources["packed_observed"]:
        raise AssertionError(f"M2 {name}: required hot/packed source is absent")
    return {"admission_budget": budget, "online_same_mask_dense": {"answer_sha256": answer_hash(dense), "policy_decode_call_count_by_layer": dense_backend.policy_decode_calls, "policy_coverage": dense_coverage, "same_mask_numerical_guard_work": dense_backend.same_mask_numerical_guard_work_summary()}, "replayed_same_mask_route_a": {"answer_sha256": answer_hash(route), "policy_decode_call_count_by_layer": route_backend.policy_decode_calls, "policy_coverage": coverage, "same_mask_numerical_guard_work": route_backend.same_mask_numerical_guard_work_summary(), "source_coverage": sources, "final_lifecycle_state": final_states(route_backend, layers=layers, heads=heads), "page_witness": page_witness(coverage)}, "same_mask_pairing": {"mode": "replayed_online_dense_mask", "route_a_replay_consumption_complete": True, "original_mask_decision_count_by_layer": {str(row["layer"]): int(row["original_mask_decision_count"]) for row in dense_coverage["layers"]}}}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if (args.model_name, args.model_revision, args.threshold, args.window_size) != (DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION, -7.0, 128):
        raise ValueError("M2 is fixed to the M0/M1-reviewed model revision, threshold -7.0, and hot window 128")
    if args.predictor_repo_id_override != OFFICIAL_PREDICTOR_REPO:
        raise ValueError("M2 requires the exact M0/M1-reviewed explicit Linear predictor override")
    if (args.pending_admission_budget, args.packing_admission_budget) != (1, 512):
        raise ValueError("M2 requires functional-reference points --pending-admission-budget 1 and --packing-admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps) <= 0 or args.max_new_tokens < 2:
        raise ValueError("invalid M2 functional-reference dimensions")
    m0 = read_completed_m0(args.m0_manifest)
    m0_sha = sha256_file(args.m0_manifest)
    m1 = read_completed_m1(args.m1_manifest, m0_sha256=m0_sha)
    revision = str(m1["config"]["predictor_revision"])
    if args.page_tokens != int(m1["config"]["page_tokens"]):
        raise ValueError("M2 page_tokens must equal the completed M1 functional-reference page granularity")
    config = {key: (str(value) if isinstance(value, Path) else value) for key, value in vars(args).items() if key not in {"output_dir", "m0_manifest", "m1_manifest"}} | {"predictor_revision": revision, "predictor_model_type": "linear", "target_layers": "all", "target_kv_heads": "all"}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    started = {"schema_version": M2_SCHEMA, "status": "started", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "m0_manifest_sha256": m0_sha, "m1_manifest_sha256": sha256_file(args.m1_manifest), "boundaries": ["Started-record only: M2 is an untimed functional lifecycle gate, not a hardware benchmark.", "The declared page/admission points are state probes, not selected hardware values."]}
    (args.output_dir / "llama31_m2_lifecycle_started.json").write_text(json.dumps(started, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    snapshot = Path(snapshot_download(repo_id=OFFICIAL_PREDICTOR_REPO, revision=revision))
    if snapshot.name != revision:
        raise AssertionError("resolved Linear predictor snapshot differs from M1")
    print(f"Loading M2 base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise AssertionError("loaded base model revision differs from M0/M1")
    layers, heads = validate_runtime_structure(pipe.model)
    if (layers, heads) != (EXPECTED_STRUCTURE["layer_count"], EXPECTED_STRUCTURE["kv_head_count"]):
        raise AssertionError("loaded model dimensions differ from fixed M2 structure")
    tokens = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    if int(tokens["context_ids"].shape[1]) <= args.window_size:
        raise ValueError("request does not exceed protected hot window")
    print("M2 Full-KV bypass: zero Route-A lifecycle state...")
    full = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    pending = run_point(name="pending_budget_one", budget=1, pipe=pipe, request=request, args=args, revision=revision, layers=layers, heads=heads)
    if not pending["replayed_same_mask_route_a"]["source_coverage"]["pending_observed"]:
        raise AssertionError("M2 budget-one point did not observe pending retained cold staging")
    packed = run_point(name="packed_budget_512", budget=512, pipe=pipe, request=request, args=args, revision=revision, layers=layers, heads=heads)
    if not packed["replayed_same_mask_route_a"]["page_witness"]["covered"]:
        raise AssertionError("M2 budget-512 point lacks a sealed full page, multi-page state, and nonempty tail")
    manifest = {"schema_version": M2_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "functional Route-A lifecycle gate with trace-derived scalar state guards; not modeled or measured hardware evidence", "m0_provenance": {"manifest_path": str(args.m0_manifest), "manifest_sha256": m0_sha, "config_hash": m0.get("config_hash")}, "m1_provenance": {"manifest_path": str(args.m1_manifest), "manifest_sha256": sha256_file(args.m1_manifest), "config_hash": m1.get("config_hash")}, "predictor_snapshot": {"repo_id": OFFICIAL_PREDICTOR_REPO, "resolved_revision": revision, "snapshot_path": str(snapshot), "model_type": "linear", "explicit_default_off_override": args.predictor_repo_id_override}, "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "context_tokens": int(tokens["context_ids"].shape[1])}, "outcomes": {"full_kv_bypass": {"answer_sha256": answer_hash(full), "zero_route_a_admission": True}, "pending_budget_one": pending, "packed_budget_512": packed}, "observational_guards": {"m0_complete_explicit_override_bound": True, "m1_completed_semantic_prerequisite": True, "all_32_layers_and_all_8_kv_heads_covered_at_both_points": True, "online_dense_events_replayed_exactly_once_at_both_points": True, "same_mask_fp32_and_executed_dtype_guards_executed_at_both_points": True, "budget_one_hot_pending_packed_observed": all(pending["replayed_same_mask_route_a"]["source_coverage"].values()), "budget_512_hot_packed_observed": packed["replayed_same_mask_route_a"]["source_coverage"]["hot_observed"] and packed["replayed_same_mask_route_a"]["source_coverage"]["packed_observed"], "budget_512_full_multi_tail_page_witness": packed["replayed_same_mask_route_a"]["page_witness"]["covered"], "dms_press_used": False, "fake_key_attention_used": False, "masked_key_indices_created": False, "model_cache_mutated_by_backend": False, "route_a_predictor_scored_online": False, "full_kv_bypass_zero_route_a_admission": True}, "boundaries": ["M2 validates one fixed Nous Llama request and two declared reference-state points; it is not a Meta-official reproduction or an accuracy result.", "Dense is the only online mask source; Route-A replays it exactly once and M2 does not claim independent post-substitution re-scoring equivalence.", "This gate owns Route-A reference state only; it does not replace/free native Llama cache, establish external ownership, allocator reduction, or physical capacity.", "page_tokens and admission budgets are lifecycle probes, not FIFO/PTE/bank/burst/precision/PE/scheduler/controller selections.", "No field is HBM traffic, true hardware latency, throughput, energy, area, hardware acceleration, architecture specification, or RTL evidence."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / "llama31_m2_lifecycle_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M2 lifecycle gate passed: {path}")


if __name__ == "__main__":
    main()
