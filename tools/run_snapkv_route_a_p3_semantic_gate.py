#!/usr/bin/env python3
"""P3 same-mask semantic gate for one completed SnapKV P0/P1 Qwen source.

P3 deliberately does not install ``SnapKVPress`` or its native score-ranked
cache replacement.  It replays the immutable P0 terminal prefill decisions in
canonical original-position order into two independent functional states:
same-mask dense cold lists and Route-A hot/pending/packed lists.  At the final
prefill query of every layer, it compares their attention reductions without
replacing the model's prefill output.  This is a bounded functional probe, not
a native SnapKV decode, performance, or hardware experiment.
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
from transformers import DynamicCache, pipeline

from kvpress.route_a_attention import DenseSameMaskAttentionState, dense_same_mask_attention
from kvpress.route_a_frontend_contract import (
    FRONTEND_DECISION_STREAM_SCHEMA,
    SNAPKV_FRONTEND_NAME,
    SNAPKV_TERMINAL_EPOCH,
    FrontendDecision,
    sha256_file,
    snapkv_terminal_decisions_to_route_a_replay_masks,
)
from kvpress.route_a_policy_backend import (
    DenseSameMaskAttentionBackendSet,
    RouteAPolicyAttentionBackend,
    RouteAPolicyAttentionBackendSet,
    RouteANumericalGuardError,
)
from tools.analyze_kvzap_trace import get_git_commit, stable_hash
from tools.analyze_snapkv_route_a_p1_packed_opportunity import (
    P0_MANIFEST_NAME,
    P0_SCHEMA,
    P0_STREAM_NAME,
    P1_SCHEMA,
    load_p0_input,
)
from tools.export_kvzap_predictor_trace import GATE_B_MODEL_REVISION, assert_no_runtime_mask_state
from tools.run_kvzap_trace import DEFAULT_MODEL, build_builtin_request, seed_everything


P3_SCHEMA = "route-a-snapkv-p3-same-mask-semantic-gate-1.0"
P1_REPORT_NAME = "snapkv_p1_packed_opportunity_report.json"
P3_PAGE_TOKENS = 64
P3_ADMISSION_BUDGET = 4096


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "P3 functional SnapKV same-mask dense/Route-A gate bound to completed P0/P1 sources; "
            "not native SnapKV, timing, or hardware evidence."
        )
    )
    parser.add_argument("--p0-dir", type=Path, required=True, help="Completed P0 directory only.")
    parser.add_argument("--p1-report", type=Path, required=True, help="Completed P1 report JSON only.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    return parser.parse_args()


def _require(value: Any, expected: Any, *, label: str) -> None:
    if value != expected:
        raise ValueError(f"{label} differs from the fixed SnapKV P3 contract: {value!r}")


def load_p3_inputs(
    p0_dir: Path,
    p1_report_path: Path,
) -> tuple[dict[str, Any], list[FrontendDecision], dict[str, Any], dict[int, dict[tuple[int, int], tuple[bool, float]]]]:
    """Load the completed P0/P1 pair and reject any provenance or mapping drift."""
    p0, decisions, window_size, compression_ratio = load_p0_input(p0_dir)
    if not p1_report_path.is_file():
        raise FileNotFoundError("P3 requires the completed P1 report")
    p1 = json.loads(p1_report_path.read_text(encoding="utf-8"))
    if p1.get("schema_version") != P1_SCHEMA or p1.get("status") != "complete":
        raise ValueError("P3 requires a complete SnapKV P1 report")
    p0_manifest_path = p0_dir / P0_MANIFEST_NAME
    p0_stream_path = p0_dir / P0_STREAM_NAME
    p1_input = p1.get("input")
    if not isinstance(p1_input, dict):
        raise ValueError("P1 report lacks input provenance")
    _require(p1_input.get("p0_manifest_sha256"), sha256_file(p0_manifest_path), label="P1 P0 manifest SHA-256")
    _require(p1_input.get("p0_terminal_stream_sha256"), sha256_file(p0_stream_path), label="P1 P0 terminal stream SHA-256")
    mapping = p1.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("P1 report lacks the required compatibility mapping")
    expected_mapping = {
        "terminal_drop": "absent from Route-A stores",
        "terminal_keep_at_or_after_resident_window_start": "resident hot window",
        "terminal_keep_before_resident_window_start": "append-only per-(layer,kv_head) cold pages in original-position order",
        "native_score_ranked_gather_order_used": False,
        "resident_window_is_p0_snapkv_observation_window": True,
    }
    for key, expected in expected_mapping.items():
        _require(mapping.get(key), expected, label=f"P1 mapping {key}")
    p1_config = p1.get("config")
    if not isinstance(p1_config, dict):
        raise ValueError("P1 report lacks config")
    _require(p1_config.get("resident_window"), window_size, label="P1 resident window")
    if P3_PAGE_TOKENS not in p1_config.get("page_tokens", []):
        raise ValueError("P3 requires the P1 static P=64 row")
    rows = [row for row in p1.get("request_rows", []) if row.get("page_tokens") == P3_PAGE_TOKENS]
    if len(rows) != 1:
        raise ValueError("P1 must contain exactly one P=64 request row")
    p1_row = rows[0]
    for field in ("request_id", "resident_window", "hot_slots", "cold_logical_kept_slots", "cold_page_count"):
        if field not in p1_row:
            raise ValueError(f"P1 P=64 row lacks {field}")
    _require(p1_row["request_id"], p0.get("request_id"), label="P1 request ID")
    _require(p1_row["resident_window"], window_size, label="P1 P=64 resident window")

    config = p0.get("config")
    if p0.get("schema_version") != P0_SCHEMA or p0.get("decision_stream_schema") != FRONTEND_DECISION_STREAM_SCHEMA:
        raise ValueError("P3 P0 schema differs from the accepted SnapKV source")
    if not isinstance(config, dict):
        raise ValueError("P0 manifest lacks config")
    fixed = {
        "model_name": DEFAULT_MODEL,
        "model_revision": GATE_B_MODEL_REVISION,
        "preset": "summarization",
        "context_repetitions": 12,
        "compression_ratio": 0.5,
        "window_size": 64,
        "kernel_size": 5,
        "seed": 42,
        "max_new_tokens": 1,
        "input_jsonl": None,
        "request_id": None,
        "target_layers": ["all"],
    }
    for key, expected in fixed.items():
        _require(config.get(key), expected, label=f"P0 config {key}")
    if window_size != 64 or compression_ratio != 0.5:
        raise ValueError("P3 accepts only the P0 Qwen3-8B 64-token/0.5 terminal contract")
    if p0.get("request_id") != "builtin_summarization_trace":
        raise ValueError("P3 accepts only the fixed P0 built-in summarization request")
    replay_masks = snapkv_terminal_decisions_to_route_a_replay_masks(decisions)
    if {row.frontend_name for row in decisions} != {SNAPKV_FRONTEND_NAME} or {row.decision_epoch for row in decisions} != {SNAPKV_TERMINAL_EPOCH}:
        raise ValueError("P3 source is not a SnapKV terminal prefill stream")
    return p0, decisions, p1, replay_masks


class SnapKVP3RouteBackend(RouteAPolicyAttentionBackend):
    """Route-A state plus an independent same-mask dense prefill-tail probe.

    The model still receives its original dense prefill output.  This class
    only evaluates the final real prefill query against two separately built
    states after the terminal P0 sequence has been appended.  It purposely
    has no decision for a generated decode token.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.p3_dense_state: DenseSameMaskAttentionState | None = None
        self.prefill_tail_probe_calls = 0

    def _append_state(self, key: torch.Tensor, value: torch.Tensor, *, token_by_token: bool = False, after_token_append=None) -> None:
        if token_by_token or after_token_append is not None:
            raise AssertionError("P3 terminal prefill probe requires one unsplit append epoch")
        if self._keep_mask is None or self._score_start is None:
            raise AssertionError("P3 replay state is missing the captured terminal mask")
        keep_mask = self._keep_mask.detach().clone()
        start = self._score_start
        q_len = keep_mask.shape[-1]
        if self.p3_dense_state is None:
            self.p3_dense_state = DenseSameMaskAttentionState(
                heads=int(keep_mask.shape[1]), head_dim=int(key.shape[-1]), window=self.window
            )
        elif self.p3_dense_state.next_position != start:
            raise AssertionError("P3 dense control has non-contiguous terminal state")
        super()._append_state(key, value)
        self.p3_dense_state.append(
            key[0, :, start : start + q_len],
            value[0, :, start : start + q_len],
            keep_mask[0],
            start_position=start,
        )

    def _prefill_tail_probe(self, query: torch.Tensor, key: torch.Tensor, kwargs: dict[str, Any]) -> None:
        if self.state is None or self.p3_dense_state is None:
            raise AssertionError("P3 states are unavailable for the prefill-tail probe")
        if query.shape[0] != 1 or query.shape[2] <= 1 or key.ndim != 4:
            raise AssertionError("P3 prefill-tail probe requires batch-one multi-token attention")
        heads, kv_heads = query.shape[1], key.shape[1]
        if heads % kv_heads:
            raise AssertionError("P3 GQA query/KV head ratio is invalid")
        selected_heads = self.selected_kv_heads(kv_heads)
        groups = heads // kv_heads
        scaling = float(kwargs.get("scaling", getattr(self.module, "scaling", 1.0)))
        by_head: dict[int, list[tuple[torch.Tensor, torch.Tensor, float]]] = {head: [] for head in selected_heads}
        cache_position = int(key.shape[2] - 1)
        for query_head in range(heads):
            mapped = query_head // groups
            if mapped not in by_head:
                continue
            q = query[0, query_head, -1]
            route_fp32 = self.state.attention(q * scaling, head=mapped)
            dense_fp32 = self.p3_dense_state.attention(q * scaling, head=mapped)
            torch.testing.assert_close(route_fp32, dense_fp32, rtol=self.rtol, atol=self.atol)
            route = route_fp32.to(dtype=q.dtype)
            dense = dense_fp32.to(dtype=q.dtype)
            _difference, ulps = self._cast_difference_in_ulps(route, dense)
            if ulps > self.max_executed_dtype_ulps:
                self._handle_executed_dtype_ulp_breach(
                    self._executed_dtype_failure_details(
                        route=route,
                        dense=dense,
                        route_fp32=route_fp32,
                        dense_fp32=dense_fp32,
                        kv_head=mapped,
                        query_head=query_head,
                        cache_position=cache_position,
                    )
                )
            by_head[mapped].append((route_fp32, dense_fp32, ulps))
        if any(not rows for rows in by_head.values()):
            raise AssertionError("P3 prefill-tail probe missed a selected KV head")
        for head, rows in by_head.items():
            record: dict[str, float | int | bool | str] = self.state.state_summary(head)
            record.update(
                {
                    "layer": self.layer,
                    "kv_head": head,
                    "cache_position": cache_position,
                    "query_head_count": len(rows),
                    "max_abs_difference_fp32": max(float((route - dense).abs().max().item()) for route, dense, _ulps in rows),
                    "max_abs_difference": max(
                        float((route.to(dtype=query.dtype) - dense.to(dtype=query.dtype)).abs().max().item())
                        for route, dense, _ulps in rows
                    ),
                    "max_executed_dtype_ulps": max(ulps for _route, _dense, ulps in rows),
                    "executed_dtype_ulp_limit": self.max_executed_dtype_ulps,
                    "same_mask_numerical_guard_enforced": True,
                    "probe_kind": "prefill_tail_same_mask_dense_vs_route_a",
                }
            )
            self.comparisons.append(record)
        self.prefill_tail_probe_calls += 1

    def attention(self, original, module, query, key, value, attention_mask, dropout, **kwargs):
        result = super().attention(original, module, query, key, value, attention_mask, dropout, **kwargs)
        if query.shape[2] > 1:
            self._prefill_tail_probe(query, key, kwargs)
        return result


class SnapKVP3RouteBackendSet(RouteAPolicyAttentionBackendSet):
    backend_class = SnapKVP3RouteBackend

    def prefill_tail_probe_summary(self) -> dict[str, Any]:
        return {
            "layers": [
                {
                    "layer": layer,
                    "probe_calls": backend.prefill_tail_probe_calls,
                    "dense_control_mask": None if backend.p3_dense_state is None else backend.p3_dense_state.mask_summary(),
                }
                for layer, backend in self.backends.items()
            ]
        }


def assert_all_layer_head_coverage(coverage: dict[str, Any], *, expected_layers: int, expected_heads: int) -> None:
    rows = coverage.get("layers")
    if not isinstance(rows, list) or [row.get("layer") for row in rows] != list(range(expected_layers)):
        raise AssertionError("P3 coverage does not contain every Qwen layer")
    expected = list(range(expected_heads))
    for row in rows:
        if row.get("selected_kv_heads") != expected:
            raise AssertionError(f"P3 layer {row['layer']} does not select every KV head")
        heads = row.get("heads")
        if not isinstance(heads, list) or [item.get("kv_head") for item in heads] != expected:
            raise AssertionError(f"P3 layer {row['layer']} does not cover every KV head")
        if any(int(item.get("comparison_count", 0)) <= 0 for item in heads):
            raise AssertionError(f"P3 layer {row['layer']} lacks a same-mask tail comparison")


def assert_state_matches_p1(
    backend: SnapKVP3RouteBackendSet,
    p1: dict[str, Any],
    *,
    expected_layers: int,
    expected_heads: int,
) -> dict[str, Any]:
    row = next(item for item in p1["request_rows"] if item["page_tokens"] == P3_PAGE_TOKENS)
    per_head_hot = int(row["hot_slots"]) // (expected_layers * expected_heads)
    per_head_cold = int(row["cold_logical_kept_slots"]) // (expected_layers * expected_heads)
    per_head_pages = int(row["cold_page_count"]) // (expected_layers * expected_heads)
    if any(int(row[name]) % (expected_layers * expected_heads) for name in ("hot_slots", "cold_logical_kept_slots", "cold_page_count")):
        raise AssertionError("P1 P=64 aggregate state is not divisible across the canonical layer-head grid")
    expected_tail = per_head_cold % P3_PAGE_TOKENS
    expected_full_pages = per_head_cold // P3_PAGE_TOKENS
    layers = []
    for layer in range(expected_layers):
        route = backend.backends[layer]
        if route.state is None or route.p3_dense_state is None:
            raise AssertionError("P3 state was not constructed for a selected layer")
        heads = []
        for head in range(expected_heads):
            route_state = route.state.state_summary(head)
            dense_state = route.p3_dense_state.state_summary(head)
            expected_route = {
                "hot_tokens": per_head_hot,
                "pending_tokens": 0,
                "packed_tokens": per_head_cold,
                "packed_page_count": per_head_pages,
                "packed_full_page_count": expected_full_pages,
                "packed_tail_tokens": expected_tail,
            }
            expected_dense = {"hot_tokens": per_head_hot, "dense_cold_tokens": per_head_cold}
            if route_state != expected_route or dense_state != expected_dense:
                raise AssertionError(f"P3 layer/head state differs from P1 P=64 mapping at ({layer}, {head})")
            heads.append({"kv_head": head, "route_a": route_state, "same_mask_dense": dense_state})
        layers.append({"layer": layer, "heads": heads})
    return {"page_tokens": P3_PAGE_TOKENS, "admission_budget": P3_ADMISSION_BUDGET, "layers": layers}


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def resolve_language_model(model):
    """Resolve Qwen's inner language-model container without guessing layers."""
    model_core = model.model
    return model_core.language_model if hasattr(model_core, "language_model") else model_core


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"P3 output directory already exists: {args.output_dir}")
    if min(args.rtol, args.atol, args.max_executed_dtype_ulps) <= 0:
        raise ValueError("P3 numerical guard dimensions must be positive")
    p0, decisions, p1, replay_masks = load_p3_inputs(args.p0_dir, args.p1_report)
    request = build_builtin_request("summarization", 12)
    if stable_hash({"context": request["context"], "question": request["question"]}) != p0.get("request_content_hash"):
        raise AssertionError("reconstructed P3 request differs from the P0 content hash")

    print(f"Loading fixed P3 base model: {DEFAULT_MODEL}")
    pipe = pipeline("kv-press-text-generation", model=DEFAULT_MODEL, revision=GATE_B_MODEL_REVISION, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != GATE_B_MODEL_REVISION:
        raise AssertionError("P3 loaded model revision differs from P0")
    language_model = resolve_language_model(pipe.model)
    layer_count = len(language_model.layers)
    kv_head_count = int(pipe.model.config.num_key_value_heads)
    if set(replay_masks) != set(range(layer_count)):
        raise AssertionError("P0 replay layers differ from the loaded Qwen model")
    if any(sorted({head for head, _position in events}) != list(range(kv_head_count)) for events in replay_masks.values()):
        raise AssertionError("P0 replay KV-head count differs from the loaded Qwen model")

    print("P3 functional pass: replaying frozen P0 terminal masks into same-mask dense and Route-A states...")
    backend = SnapKVP3RouteBackendSet(
        pipe.model,
        None,
        layers=tuple(range(layer_count)),
        kv_head=None,
        threshold=0.0,
        window=64,
        page_tokens=P3_PAGE_TOKENS,
        admission_budget=P3_ADMISSION_BUDGET,
        rtol=args.rtol,
        atol=args.atol,
        max_executed_dtype_ulps=args.max_executed_dtype_ulps,
        replay_mask_events=replay_masks,
    )
    seed_everything(42)
    with torch.no_grad(), backend:
        output = pipe(
            str(request["context"]),
            question=str(request["question"]),
            cache=DynamicCache(),
            max_new_tokens=1,
            enable_thinking=False,
        )
    assert_no_runtime_mask_state(pipe.model)
    backend.assert_replay_complete()
    if backend.mask_events() != replay_masks:
        raise AssertionError("P3 backend replay differs from the canonical P0 terminal decision stream")
    coverage = backend.coverage()
    assert_all_layer_head_coverage(coverage, expected_layers=layer_count, expected_heads=kv_head_count)
    state = assert_state_matches_p1(backend, p1, expected_layers=layer_count, expected_heads=kv_head_count)
    probe_summary = backend.prefill_tail_probe_summary()
    if any(int(row["probe_calls"]) != 1 for row in probe_summary["layers"]):
        raise AssertionError("P3 did not execute exactly one terminal prefill-tail probe per layer")
    if any(row["dense_control_mask"] != backend.backends[int(row["layer"])].state.mask_summary() for row in probe_summary["layers"]):
        raise AssertionError("P3 dense and Route-A states disagree on their terminal mask digest")

    config = {
        "model_name": DEFAULT_MODEL,
        "model_revision": GATE_B_MODEL_REVISION,
        "preset": "summarization",
        "context_repetitions": 12,
        "source_epoch": SNAPKV_TERMINAL_EPOCH,
        "source_frontend": SNAPKV_FRONTEND_NAME,
        "resident_window": 64,
        "page_tokens_functional_probe": P3_PAGE_TOKENS,
        "admission_budget_functional_probe": P3_ADMISSION_BUDGET,
        "max_new_tokens": 1,
        "seed": 42,
        "rtol": args.rtol,
        "atol": args.atol,
        "max_executed_dtype_ulps": args.max_executed_dtype_ulps,
    }
    manifest = {
        "schema_version": P3_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "functional same-mask prefill-tail attention probe with trace-derived SnapKV terminal decisions; not modeled or measured hardware evidence",
        "input_provenance": {
            "p0_manifest_path": str(args.p0_dir / P0_MANIFEST_NAME),
            "p0_manifest_sha256": sha256_file(args.p0_dir / P0_MANIFEST_NAME),
            "p0_terminal_stream_path": str(args.p0_dir / P0_STREAM_NAME),
            "p0_terminal_stream_sha256": sha256_file(args.p0_dir / P0_STREAM_NAME),
            "p1_report_path": str(args.p1_report),
            "p1_report_sha256": sha256_file(args.p1_report),
            "p0_event_count": len(decisions),
            "p0_request_content_sha256": p0["request_content_hash"],
        },
        "request": {
            "request_id": request["request_id"],
            "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}),
        },
        "outcomes": {
            "dense_full_prefill_output_answer_sha256": answer_hash(output),
            "canonical_p0_terminal_replay_consumed_exactly_once": True,
            "same_mask_dense_vs_route_a_prefill_tail_probe": {
                "coverage": coverage,
                "probe_summary": probe_summary,
                "p1_p64_state_cross_check": state,
            },
        },
        "observational_guards": {
            "p0_and_p1_sha256_bound_and_revalidated": True,
            "p1_native_score_ranked_gather_order_not_used": True,
            "all_qwen_layers_and_kv_heads_covered": True,
            "terminal_replay_consumed_exactly_once": True,
            "same_mask_dense_and_route_a_mask_digests_match": True,
            "p1_p64_hot_packed_state_matches_functional_route_a": True,
            "p3_preffill_tail_probes_do_not_replace_model_prefill_attention": True,
            "snapkv_native_cache_replacement_used": False,
            "route_a_predictor_scored_online": False,
            "full_kv_bypass_or_native_cache_mutation_used": False,
        },
        "boundaries": [
            "P3 is one fixed Qwen3-8B request. P0 terminal decisions are trace-derived; P3 same-mask dense/Route-A tail comparisons are functional reference evidence.",
            "P3 evaluates the final real prefill query after appending P0 state, but leaves the model's multi-token prefill output dense. It has no source decision for a generated decode position and therefore is not native SnapKV decode validation or an end-to-end generation-equivalence result.",
            "The P=64 and admission-budget=4096 values fully materialize the accepted P1 P=64 state for this probe. They select no FIFO depth, PTE width, bank/burst, merge precision, PE count, scheduler, controller timing, or hardware parameter.",
            "P3 establishes no quality/accuracy, allocator behavior, physical capacity, HBM traffic, true hardware latency, throughput, energy, area, hardware acceleration, architecture specification, or RTL result.",
        ],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    path = args.output_dir / "snapkv_p3_semantic_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SnapKV P3 same-mask semantic gate passed: {path}")


if __name__ == "__main__":
    main()
