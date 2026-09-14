#!/usr/bin/env python3
"""M1 semantic-portability gate for the fixed Nous Llama 3.1 8B snapshot.

This is deliberately a functional Route-A reference gate.  It does not use
``DMSPress`` or the fake-key path: a full-KV bypass, an online same-mask dense
control, and an online hot/pending/packed Route-A control are run separately.
The latter two must make identical original KVzap decisions for every layer
and KV head.  None of its scalar summaries is a hardware measurement.
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

from kvpress import KVzapPress
from kvpress.route_a_policy_backend import (
    DenseSameMaskAttentionBackendSet,
    RouteAPolicyAttentionBackendSet,
    compare_original_mask_events,
)
from tools.export_kvzap_predictor_trace import assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_trace import PRESETS, build_builtin_request, load_jsonl_request, seed_everything
from tools.validate_kvzap_llama31_m0_provenance import (
    DEFAULT_MODEL_REPO,
    DEFAULT_MODEL_REVISION,
    OFFICIAL_PREDICTOR_REPO,
)


M1_SCHEMA = "kvzap-llama31-m1-semantic-gate-1.0"
M0_SCHEMA = "kvzap-llama31-m0-provenance-1.0"
EXPECTED_STRUCTURE = {
    "hidden_size": 4096,
    "layer_count": 32,
    "query_head_count": 32,
    "kv_head_count": 8,
    "query_heads_per_kv_head_group": 4,
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "M1 functional semantic-portability gate for Nous Llama 3.1 8B: "
            "compare online same-mask dense and Route-A controls; not a benchmark."
        )
    )
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--m0-manifest", type=Path, required=True, help="Completed M0 provenance manifest to hash-bind.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_REPO)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument(
        "--predictor-repo-id-override",
        required=True,
        help=(
            "Explicit default-off KVzapPress override. It must exactly match the "
            "reviewed official Linear predictor recorded by M0."
        ),
    )
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--threshold", type=float, default=-7.0)
    parser.add_argument(
        "--page-tokens",
        type=int,
        required=True,
        help="Explicit functional-reference page granularity; this is not a hardware selection.",
    )
    parser.add_argument(
        "--admission-budget",
        type=int,
        required=True,
        help="Explicit functional-reference admission-service budget; this is not a hardware selection.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--require-any-pending", action="store_true")
    parser.add_argument("--require-any-packed", action="store_true")
    parser.add_argument("--mask-drift-example-limit", type=int, default=32)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def read_completed_m0(path: Path) -> dict[str, Any]:
    """Load only the completed explicit-override M0 contract required by M1."""
    if not path.is_file():
        raise FileNotFoundError(f"M0 manifest is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("M0 manifest must contain a JSON object")
    if report.get("schema_version") != M0_SCHEMA or report.get("status") != "complete":
        raise ValueError("M1 requires a completed kvzap-llama31-m0-provenance-1.0 manifest")
    config = report.get("config")
    adapter = report.get("adapter_contract")
    guards = report.get("observational_guards")
    if not isinstance(config, dict) or not isinstance(adapter, dict) or not isinstance(guards, dict):
        raise ValueError("M0 manifest lacks config, adapter_contract, or observational_guards")
    expected_config = {
        "model_repo_id": DEFAULT_MODEL_REPO,
        "model_revision": DEFAULT_MODEL_REVISION,
        "predictor_repo_id": OFFICIAL_PREDICTOR_REPO,
        "predictor_repo_id_override": OFFICIAL_PREDICTOR_REPO,
    }
    for key, expected in expected_config.items():
        if config.get(key) != expected:
            raise ValueError(f"M0 {key} differs from the fixed M1 contract: {config.get(key)!r}")
    if not adapter.get("explicit_nondefault_override_bound"):
        raise ValueError("M0 does not bind the required explicit predictor override")
    if adapter.get("kvzap_press_model_type") != "linear":
        raise ValueError("M1 requires the M0-reviewed Linear KVzap predictor")
    if adapter.get("threshold_for_later_M1") != -7.0 or adapter.get("hot_window_tokens_for_later_M1") != 128:
        raise ValueError("M0 does not carry the reviewed M1 threshold/window contract")
    if report.get("base_model_structure") != EXPECTED_STRUCTURE:
        raise ValueError("M0 Llama structure differs from the fixed M1 structure")
    required_guards = (
        "fixed_base_snapshot_present",
        "declared_safetensors_shards_present",
        "llama_structure_matches_expected",
        "official_predictor_linear_dimensions_match_base_structure",
        "direct_derivation_or_explicit_override_bound",
    )
    if not all(guards.get(name) is True for name in required_guards):
        raise ValueError("M0 prerequisite guard is absent or false")
    predictor_revision = config.get("predictor_revision_resolved")
    if not isinstance(predictor_revision, str) or len(predictor_revision) != 40:
        raise ValueError("M0 does not record a fixed 40-character predictor revision")
    return report


def validate_runtime_structure(model) -> tuple[int, int]:
    language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
    layer_count = len(language_model.layers)
    config = model.config
    values = {
        "hidden_size": int(config.hidden_size),
        "layer_count": layer_count,
        "query_head_count": int(config.num_attention_heads),
        "kv_head_count": int(config.num_key_value_heads),
        "query_heads_per_kv_head_group": int(config.num_attention_heads) // int(config.num_key_value_heads),
    }
    if values != EXPECTED_STRUCTURE:
        raise AssertionError(f"loaded Llama structure differs from M0 contract: {values}")
    return layer_count, int(config.num_key_value_heads)


def assert_all_layer_head_coverage(
    coverage: dict[str, Any],
    *,
    expected_layers: int,
    expected_kv_heads: int,
    label: str,
) -> None:
    rows = coverage.get("layers")
    if not isinstance(rows, list) or len(rows) != expected_layers:
        raise AssertionError(f"{label}: coverage lacks every Llama layer")
    observed_layers = [int(row.get("layer", -1)) for row in rows]
    if observed_layers != list(range(expected_layers)):
        raise AssertionError(f"{label}: coverage layer order/set is incomplete")
    expected_heads = list(range(expected_kv_heads))
    for row in rows:
        if row.get("selected_kv_heads") != expected_heads:
            raise AssertionError(f"{label}: layer {row['layer']} does not select every KV head")
        heads = row.get("heads")
        if not isinstance(heads, list) or [int(head.get("kv_head", -1)) for head in heads] != expected_heads:
            raise AssertionError(f"{label}: layer {row['layer']} head coverage is incomplete")
        if any(int(head.get("comparison_count", 0)) <= 0 for head in heads):
            raise AssertionError(f"{label}: layer {row['layer']} has a KV head without a policy comparison")


def source_coverage(comparisons: list[dict[str, Any]]) -> dict[str, bool]:
    return {
        "hot_observed": any(int(row.get("hot_tokens", 0)) > 0 for row in comparisons),
        "pending_observed": any(int(row.get("pending_tokens", 0)) > 0 for row in comparisons),
        "packed_observed": any(int(row.get("packed_tokens", 0)) > 0 for row in comparisons),
    }


def assert_numerical_guard_work(summary: dict[str, Any], expected_layers: int, *, label: str) -> None:
    rows = summary.get("layers")
    if not isinstance(rows, list) or len(rows) != expected_layers:
        raise AssertionError(f"{label}: missing numerical-guard work summary")
    for row in rows:
        if row.get("mode") != "enforce" or row.get("enforced") is not True or int(row.get("work_count", 0)) <= 0:
            raise AssertionError(f"{label}: numerical same-mask guard did not execute for layer {row.get('layer')}")


def make_predictor(*, predictor_revision: str, override: str) -> KVzapPress:
    return KVzapPress(
        model_type="linear",
        predictor_revision=predictor_revision,
        predictor_repo_id_override=override,
    )


def generate(pipe, request: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    seed_everything(args.seed)
    return pipe(
        str(request["context"]),
        question=str(request["question"]),
        max_new_tokens=args.max_new_tokens,
        enable_thinking=False,
    )


def compact_config(args: argparse.Namespace, *, predictor_revision: str) -> dict[str, Any]:
    return {
        key: (str(value) if isinstance(value, Path) else value)
        for key, value in vars(args).items()
        if key not in {"output_dir", "m0_manifest"}
    } | {"predictor_revision": predictor_revision, "predictor_model_type": "linear", "target_layers": "all", "target_kv_heads": "all"}


def write_mask_drift_diagnostic(
    *,
    args: argparse.Namespace,
    request: dict[str, Any],
    m0: dict[str, Any],
    predictor_revision: str,
    full: dict[str, Any],
    dense: dict[str, Any],
    route: dict[str, Any],
    dense_backend: DenseSameMaskAttentionBackendSet,
    route_backend: RouteAPolicyAttentionBackendSet,
    report: dict[str, Any],
) -> Path:
    """Write only a bounded failed-pair diagnostic into the requested new directory."""
    args.output_dir.mkdir(parents=True, exist_ok=False)
    payload = {
        "schema_version": "kvzap-llama31-m1-online-mask-drift-diagnostic-1.0",
        "status": "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": compact_config(args, predictor_revision=predictor_revision),
        "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "m0_manifest_sha256": sha256_file(args.m0_manifest),
        "m0_config_hash": m0.get("config_hash"),
        "answer_sha256": {
            "full_kv_bypass": answer_hash(full),
            "online_same_mask_dense": answer_hash(dense),
            "online_route_a": answer_hash(route),
        },
        "dense_policy_coverage": dense_backend.coverage(),
        "route_a_policy_coverage": route_backend.coverage(),
        "mask_drift": report,
        "boundaries": [
            "This is a failed M1 online-mask pairing diagnostic, not a successful portability result.",
            "The report contains bounded scalar score/decision examples only; no token text, K/V, activation, attention matrix, or logits are serialized.",
            "It is not timing, allocator, HBM traffic, throughput, energy, area, hardware, or RTL evidence.",
        ],
    }
    path = args.output_dir / "llama31_m1_online_mask_drift_diagnostic.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if (args.model_name, args.model_revision, args.threshold, args.window_size) != (
        DEFAULT_MODEL_REPO,
        DEFAULT_MODEL_REVISION,
        -7.0,
        128,
    ):
        raise ValueError("M1 is fixed to the M0-reviewed Nous model revision, threshold -7.0, and hot window 128")
    if args.predictor_repo_id_override != OFFICIAL_PREDICTOR_REPO:
        raise ValueError("M1 requires the exact M0-reviewed explicit Linear predictor override")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps, args.mask_drift_example_limit) <= 0:
        raise ValueError("invalid M1 functional-reference dimensions")
    if args.window_size < 0 or args.max_new_tokens < 2:
        raise ValueError("M1 requires a nonnegative window and at least two generated-token attempts")

    m0 = read_completed_m0(args.m0_manifest)
    predictor_revision = str(m0["config"]["predictor_revision_resolved"])
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)

    predictor_snapshot = Path(snapshot_download(repo_id=OFFICIAL_PREDICTOR_REPO, revision=predictor_revision))
    if predictor_snapshot.name != predictor_revision:
        raise AssertionError("resolved Linear predictor snapshot differs from the M0-bound revision")
    print(f"Loading M1 base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise AssertionError("loaded base model revision differs from M0")
    layer_count, kv_head_count = validate_runtime_structure(pipe.model)
    tokenized = pipe.preprocess(
        str(request["context"]),
        [str(request["question"])],
        answer_prefix="",
        max_context_length=pipe.tokenizer.model_max_length,
        enable_thinking=False,
    )
    if int(tokenized["context_ids"].shape[1]) <= args.window_size:
        raise ValueError("request does not exceed the protected hot window")
    selected_layers = tuple(range(layer_count))

    print("Pass 1/3: Full-KV bypass (zero Route-A admission)...")
    full = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)

    dense_predictor = make_predictor(predictor_revision=predictor_revision, override=args.predictor_repo_id_override)
    dense_backend = DenseSameMaskAttentionBackendSet(
        pipe.model,
        dense_predictor,
        layers=selected_layers,
        kv_head=None,
        threshold=args.threshold,
        window=args.window_size,
        page_tokens=args.page_tokens,
        admission_budget=args.admission_budget,
        rtol=args.rtol,
        atol=args.atol,
        max_executed_dtype_ulps=args.max_executed_dtype_ulps,
    )
    print("Pass 2/3: online same-mask dense control for all layers and KV heads...")
    with torch.no_grad(), dense_backend:
        dense = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    if dense_predictor.kvzap_model_name != OFFICIAL_PREDICTOR_REPO:
        raise AssertionError("same-mask dense control did not use the explicit official Linear predictor override")
    dense_coverage = dense_backend.coverage()
    assert_all_layer_head_coverage(dense_coverage, expected_layers=layer_count, expected_kv_heads=kv_head_count, label="same-mask dense")
    assert_numerical_guard_work(dense_backend.same_mask_numerical_guard_work_summary(), layer_count, label="same-mask dense")

    route_predictor = make_predictor(predictor_revision=predictor_revision, override=args.predictor_repo_id_override)
    route_backend = RouteAPolicyAttentionBackendSet(
        pipe.model,
        route_predictor,
        layers=selected_layers,
        kv_head=None,
        threshold=args.threshold,
        window=args.window_size,
        page_tokens=args.page_tokens,
        admission_budget=args.admission_budget,
        rtol=args.rtol,
        atol=args.atol,
        max_executed_dtype_ulps=args.max_executed_dtype_ulps,
    )
    print("Pass 3/3: online Route-A hot/pending/packed control for all layers and KV heads...")
    with torch.no_grad(), route_backend:
        route = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    if route_predictor.kvzap_model_name != OFFICIAL_PREDICTOR_REPO:
        raise AssertionError("Route-A control did not use the explicit official Linear predictor override")
    route_coverage = route_backend.coverage()
    assert_all_layer_head_coverage(route_coverage, expected_layers=layer_count, expected_kv_heads=kv_head_count, label="Route-A")
    assert_numerical_guard_work(route_backend.same_mask_numerical_guard_work_summary(), layer_count, label="Route-A")

    drift = compare_original_mask_events(
        dense_backend.mask_events(), route_backend.mask_events(), max_examples=args.mask_drift_example_limit
    )
    if not drift["matched"]:
        diagnostic = write_mask_drift_diagnostic(
            args=args,
            request=request,
            m0=m0,
            predictor_revision=predictor_revision,
            full=full,
            dense=dense,
            route=route,
            dense_backend=dense_backend,
            route_backend=route_backend,
            report=drift,
        )
        raise AssertionError(f"M1 online same-mask pairing failed; diagnostic={diagnostic}")

    sources = source_coverage(route_backend.comparisons)
    if not sources["hot_observed"]:
        raise AssertionError("Route-A policy comparisons did not observe hot-window service")
    if args.require_any_pending and not sources["pending_observed"]:
        raise AssertionError("required Route-A pending staging was not observed")
    if args.require_any_packed and not sources["packed_observed"]:
        raise AssertionError("required Route-A packed service was not observed")
    config = compact_config(args, predictor_revision=predictor_revision)
    manifest = {
        "schema_version": M1_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "functional semantic gate with trace-derived scalar guards; not modeled or measured hardware evidence",
        "m0_provenance": {
            "manifest_path": str(args.m0_manifest),
            "manifest_sha256": sha256_file(args.m0_manifest),
            "config_hash": m0.get("config_hash"),
            "base_snapshot": m0.get("base_model_snapshot", {}).get("revision"),
            "predictor_revision": predictor_revision,
        },
        "predictor_snapshot": {
            "repo_id": OFFICIAL_PREDICTOR_REPO,
            "resolved_revision": predictor_revision,
            "snapshot_path": str(predictor_snapshot),
            "model_type": "linear",
            "explicit_default_off_override": args.predictor_repo_id_override,
        },
        "request": {
            "request_id": request["request_id"],
            "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}),
            "context_tokens": int(tokenized["context_ids"].shape[1]),
        },
        "outcomes": {
            "full_kv_bypass": {
                "answer_sha256": answer_hash(full),
                "zero_route_a_admission": True,
            },
            "online_same_mask_dense": {
                "answer_sha256": answer_hash(dense),
                "policy_decode_call_count_by_layer": dense_backend.policy_decode_calls,
                "policy_coverage": dense_coverage,
                "same_mask_numerical_guard_work": dense_backend.same_mask_numerical_guard_work_summary(),
            },
            "online_route_a_hot_pending_packed": {
                "answer_sha256": answer_hash(route),
                "policy_decode_call_count_by_layer": route_backend.policy_decode_calls,
                "policy_coverage": route_coverage,
                "same_mask_numerical_guard_work": route_backend.same_mask_numerical_guard_work_summary(),
                "source_coverage": sources,
            },
            "online_original_mask_pairing": drift,
        },
        "observational_guards": {
            "m0_complete_explicit_override_bound": True,
            "all_32_layers_and_all_8_kv_heads_selected": True,
            "all_selected_groups_have_policy_comparisons": True,
            "same_mask_dense_and_route_a_online_masks_identical": True,
            "same_mask_fp32_and_executed_dtype_guards_executed": True,
            "route_a_hot_service_observed": sources["hot_observed"],
            "required_pending_observed": not args.require_any_pending or sources["pending_observed"],
            "required_packed_observed": not args.require_any_packed or sources["packed_observed"],
            "dms_press_used": False,
            "fake_key_attention_used": False,
            "masked_key_indices_created": False,
            "model_cache_mutated_by_backend": False,
            "full_kv_bypass_zero_route_a_admission": True,
        },
        "boundaries": [
            "M1 validates one fixed Nous Llama 3.1 8B request and the explicit Linear predictor override. It is not a Meta-official model reproduction or an accuracy result.",
            "The full-KV, online same-mask dense, and Route-A generated answers need not match; the semantic relation gated here is identical online original-mask decisions plus same-mask numerical attention guards.",
            "page_tokens and admission_budget are explicit functional-reference inputs. This run selects no FIFO, PTE width, bank/burst, merge precision, PE count, scheduler, controller timing, or hardware parameter.",
            "No field is HBM traffic, true hardware latency, throughput, energy, area, hardware acceleration, architecture specification, or RTL evidence.",
        ],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    path = args.output_dir / "llama31_m1_semantic_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M1 semantic gate passed: {path}")


if __name__ == "__main__":
    main()
