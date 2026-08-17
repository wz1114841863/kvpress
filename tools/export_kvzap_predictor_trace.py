# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Export one read-only KVzap predictor trace after validating frozen gate-A evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any

import numpy as np
import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import DynamicCache, pipeline

from kvpress import KVzapPress
from tools.run_kvzap_trace import (
    DEFAULT_MODEL,
    DEFAULT_PREDICTOR,
    PRESETS,
    build_builtin_request,
    load_jsonl_request,
)


SCHEMA_VERSION = "kvzap-predictor-trace-1.1"
GATE_A_SCHEMA_VERSION = "kvzap-predictor-trace-1.0"
REFERENCE_CONTEXT_TOKENS = 987
REFERENCE_REQUEST_ID = "builtin_hardware_trace"
REFERENCE_PREFILL_REMOVED_FRACTION = 0.7434003152088259
REFERENCE_MANIFEST_SHA256 = "b528402ab9be70ea51be41e27dc452e41d68895290c4e9bc42d255d6562667f2"
REFERENCE_SCORE_MASK_SHA256 = "5b84c600f3eacdaf073405ea73c61c94080f8fa4aaa11f750cbcd1a8565ad1c3"
GATE_A_EXPERIMENT_ID = "kvzap-predictor-trace-20260817T080939Z"
GATE_A_GIT_COMMIT = "f97ccd8b60a388ae791607da6da28ff8d8616059"
GATE_A_CONFIG_HASH = "6a645914544d8f7a03319c1d836eeb2d7f4d5f178dcf0196b371e9af7e13a1a4"
GATE_A_PREDICTOR_REVISION = "bd5c5917846617da4311539859c137a262a6348b"
GATE_A_MANIFEST_SHA256 = "dae42264d5b71435e363f7514f776fb15ccb4291a421131a6cc17e027daee382"
GATE_A_SCORE_MASK_SHA256 = "a656a0d55c22517610546e724dbb65c6d276dbe0e551f5643e555526b74c9127"
GATE_A_COMPARISON_SHA256 = "2e0783342ef28e9636ce99ee85817c43deaab1155369d4a8b918c1abd48eb2fc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one normal context prefill, observe each attention-layer input, and apply the official "
            "KVzap MLP without DMS, masked indices, fake keys, decoding, or generation. Gate B accepts "
            "one built-in task or one selected JSONL request after verifying the frozen gate-A artifacts."
        )
    )
    request_group = parser.add_mutually_exclusive_group()
    request_group.add_argument(
        "--preset",
        choices=PRESETS,
        default="retrieval",
        help="Built-in single-request task (default: retrieval).",
    )
    request_group.add_argument("--input-jsonl", type=Path, help="JSONL containing request_id/context/question.")
    parser.add_argument("--request-id", help="Select exactly one request from --input-jsonl.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL, help="Base model Hugging Face ID.")
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR, help="Official KVzap predictor ID.")
    parser.add_argument("--threshold", type=float, default=-4.0, help="Offline drop threshold.")
    parser.add_argument("--window-size", type=int, default=128, help="Newest context tokens protected offline.")
    parser.add_argument("--seed", type=int, default=42, help="Seed for the single observational prefill.")
    parser.add_argument(
        "--context-repetitions",
        type=int,
        default=12,
        help="Paragraph repetitions for a built-in request.",
    )
    parser.add_argument(
        "--gate-a-evidence",
        type=Path,
        default=Path("traces/hardware_predictor_gate_a_01"),
        help="Frozen successful gate-A output; its exact hashes and metadata are verified before inference.",
    )
    parser.add_argument(
        "--reference-trace",
        type=Path,
        default=None,
        help="Optional original hardware trace. Valid only with --preset hardware for re-running gate A.",
    )
    parser.add_argument(
        "--score-atol",
        type=float,
        default=0.125,
        help="Maximum absolute score difference allowed against the BF16 reference.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("traces/retrieval_predictor_gate_b_01"),
        help="New diagnostic output directory; existing directories are never overwritten.",
    )
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def language_model_layers(model):
    language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
    return language_model.layers


def reconstruct_masks(scores: np.ndarray, threshold: float, window_size: int) -> tuple[np.ndarray, np.ndarray]:
    if scores.ndim != 3:
        raise ValueError(f"scores must use [layer, KV-head, token], got {scores.shape}")
    if window_size < 0:
        raise ValueError("window_size must be non-negative")
    predicted = scores < threshold
    final = predicted.copy()
    if window_size:
        final[..., max(0, scores.shape[-1] - window_size) :] = False
    return predicted, final


def stack_layer_scores(layer_scores: dict[int, np.ndarray], expected_layers: int) -> np.ndarray:
    expected = set(range(expected_layers))
    actual = set(layer_scores)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise AssertionError(f"Predictor trace layer coverage mismatch: missing={missing}, extra={extra}")
    shapes = {layer_scores[layer].shape for layer in range(expected_layers)}
    if len(shapes) != 1:
        raise AssertionError(f"Predictor score shapes differ across layers: {sorted(shapes)}")
    shape = next(iter(shapes))
    if len(shape) != 2:
        raise AssertionError(f"Per-layer predictor scores must use [KV-head, token], got {shape}")
    return np.stack([layer_scores[layer] for layer in range(expected_layers)], axis=0)


class PredictorScoreObserver(AbstractContextManager):
    """Read attention inputs and run the official predictor without changing attention output."""

    def __init__(self, model, predictor: KVzapPress):
        self.model = model
        self.predictor = predictor
        self.layer_scores: dict[int, np.ndarray] = {}
        self.original_score_dtypes: set[str] = set()
        self._hooks = []

    def _hook(self, module, _inputs, kwargs, _output) -> None:
        layer_idx = int(module.layer_idx)
        if layer_idx in self.layer_scores:
            raise AssertionError(f"Layer {layer_idx} was observed more than once in one prefill")
        hidden_states = kwargs.get("hidden_states")
        if hidden_states is None:
            raise AssertionError(f"Layer {layer_idx} attention call did not expose hidden_states in kwargs")
        if hidden_states.ndim != 3 or hidden_states.shape[0] != 1:
            raise AssertionError(
                f"Layer {layer_idx} hidden_states must use [1, token, hidden], got {tuple(hidden_states.shape)}"
            )
        scores = self.predictor.score(module, hidden_states, None, None, None, kwargs)
        if scores.ndim != 3 or scores.shape[0] != 1 or scores.shape[-1] != hidden_states.shape[1]:
            raise AssertionError(
                f"Layer {layer_idx} predictor returned {tuple(scores.shape)} for "
                f"hidden_states {tuple(hidden_states.shape)}"
            )
        self.original_score_dtypes.add(str(scores.dtype))
        self.layer_scores[layer_idx] = scores[0].detach().to(device="cpu", dtype=torch.float32).numpy().copy()

    def __enter__(self):
        self.predictor.post_init_from_model(self.model)
        for layer in language_model_layers(self.model):
            self._hooks.append(layer.self_attn.register_forward_hook(self._hook, with_kwargs=True))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        for hook in self._hooks:
            hook.remove()
        self._hooks.clear()
        return None


def assert_no_runtime_mask_state(model) -> None:
    contaminated = []
    for layer_idx, layer in enumerate(language_model_layers(model)):
        indices = getattr(layer.self_attn, "masked_key_indices", None)
        if indices is not None:
            contaminated.append(layer_idx)
    if contaminated:
        raise AssertionError(f"Observational prefill unexpectedly created masked_key_indices in layers {contaminated}")


def load_reference(reference_dir: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    manifest_path = reference_dir / "manifest.json"
    score_path = reference_dir / "score_mask.npz"
    if not manifest_path.is_file() or not score_path.is_file():
        raise FileNotFoundError(f"Reference trace requires manifest.json and score_mask.npz: {reference_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with np.load(score_path) as archive:
        required = {"scores", "score_valid_mask", "predicted_drop_mask", "shape"}
        missing = sorted(required - set(archive.files))
        if missing:
            raise ValueError(f"Reference score_mask.npz is missing arrays: {missing}")
        arrays = {name: archive[name].copy() for name in required}
    return manifest, arrays


def validate_gate_a_evidence(
    evidence_dir: Path,
    *,
    model_name: str,
    predictor_name: str,
    threshold: float,
    window_size: int,
    verify_frozen_hashes: bool = True,
) -> dict[str, Any]:
    """Validate the frozen matched-reference run that authorizes gate-B collection."""

    required_paths = {
        "manifest": evidence_dir / "manifest.json",
        "score_mask": evidence_dir / "score_mask.npz",
        "reference_comparison": evidence_dir / "reference_comparison.json",
    }
    missing = [name for name, path in required_paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Gate-A evidence {evidence_dir} is missing: {missing}")

    manifest = json.loads(required_paths["manifest"].read_text(encoding="utf-8"))
    comparison = json.loads(required_paths["reference_comparison"].read_text(encoding="utf-8"))
    with np.load(required_paths["score_mask"]) as archive:
        required_arrays = {
            "scores",
            "score_valid_mask",
            "predicted_drop_mask",
            "reconstructed_final_drop_mask",
            "shape",
        }
        missing_arrays = sorted(required_arrays - set(archive.files))
        if missing_arrays:
            raise ValueError(f"Gate-A score_mask.npz is missing arrays: {missing_arrays}")
        scores = archive["scores"]
        valid = archive["score_valid_mask"]
        predicted = archive["predicted_drop_mask"]
        final = archive["reconstructed_final_drop_mask"]
        stored_shape = tuple(int(value) for value in archive["shape"].tolist())

    checks: dict[str, bool] = {}
    if verify_frozen_hashes:
        checks["manifest_sha256_matches"] = file_sha256(required_paths["manifest"]) == GATE_A_MANIFEST_SHA256
        checks["score_mask_sha256_matches"] = file_sha256(required_paths["score_mask"]) == GATE_A_SCORE_MASK_SHA256
        checks["comparison_sha256_matches"] = (
            file_sha256(required_paths["reference_comparison"]) == GATE_A_COMPARISON_SHA256
        )
    checks["schema_matches"] = manifest.get("schema_version") == GATE_A_SCHEMA_VERSION
    checks["experiment_matches"] = manifest.get("experiment_id") == GATE_A_EXPERIMENT_ID
    checks["implementation_commit_matches"] = manifest.get("git_commit") == GATE_A_GIT_COMMIT
    checks["config_hash_matches"] = manifest.get("config_hash") == GATE_A_CONFIG_HASH
    checks["capture_valid"] = manifest.get("capture_status") == "valid"
    checks["structural_analysis_authorized"] = manifest.get("valid_for_structural_analysis") is True
    checks["model_matches"] = manifest.get("model") == model_name
    checks["predictor_matches"] = manifest.get("predictor_checkpoint") == predictor_name
    checks["predictor_revision_matches"] = manifest.get("predictor_revision") == GATE_A_PREDICTOR_REVISION
    checks["threshold_matches"] = float(manifest.get("threshold")) == threshold
    checks["window_matches"] = int(manifest.get("sliding_window")) == window_size
    checks["no_generation_or_dms"] = manifest.get("generation_performed") is False and (
        manifest.get("dms_press_used") is False
    )
    checks["no_runtime_masking"] = manifest.get("masked_key_indices_created") is False and (
        manifest.get("fake_key_attention_used") is False
    )
    checks["reference_gate_passed"] = comparison.get("passed") is True
    checks["reference_scores_exact"] = comparison.get("max_abs_score_difference") == 0.0
    checks["shape_matches"] = scores.shape == (36, 8, REFERENCE_CONTEXT_TOKENS) and stored_shape == scores.shape
    checks["all_scores_valid"] = bool(np.asarray(valid, dtype=np.bool_).all()) and bool(np.isfinite(scores).all())
    checks["predicted_mask_consistent"] = bool(np.array_equal(predicted, scores < threshold))
    _, reconstructed = reconstruct_masks(scores, threshold, window_size)
    checks["final_mask_consistent"] = bool(np.array_equal(final, reconstructed))
    removed_fraction = float(np.asarray(final, dtype=np.bool_).mean())
    checks["removed_fraction_matches"] = bool(
        np.isclose(removed_fraction, REFERENCE_PREFILL_REMOVED_FRACTION, atol=1e-12, rtol=0.0)
    )

    return {
        "passed": all(checks.values()),
        "evidence_dir": str(evidence_dir),
        "experiment_id": manifest.get("experiment_id"),
        "implementation_git_commit": manifest.get("git_commit"),
        "config_hash": manifest.get("config_hash"),
        "predictor_revision": manifest.get("predictor_revision"),
        "score_shape": list(scores.shape),
        "removed_fraction": removed_fraction,
        "artifact_sha256": {name: file_sha256(path) for name, path in required_paths.items()},
        "checks": checks,
    }


def compare_with_reference(
    scores: np.ndarray,
    predicted: np.ndarray,
    final: np.ndarray,
    *,
    reference_dir: Path,
    threshold: float,
    window_size: int,
    score_atol: float,
    verify_frozen_hashes: bool = True,
) -> dict[str, Any]:
    manifest, reference = load_reference(reference_dir)
    checks: dict[str, bool] = {}
    if verify_frozen_hashes:
        checks["reference_manifest_sha256_matches"] = (
            file_sha256(reference_dir / "manifest.json") == REFERENCE_MANIFEST_SHA256
        )
        checks["reference_score_mask_sha256_matches"] = (
            file_sha256(reference_dir / "score_mask.npz") == REFERENCE_SCORE_MASK_SHA256
        )
    checks["reference_equivalence_verified"] = manifest.get("trace_equivalence_verified") is True
    checks["model_matches"] = manifest.get("model") == DEFAULT_MODEL
    checks["predictor_matches"] = manifest.get("predictor_checkpoint") == DEFAULT_PREDICTOR
    checks["threshold_matches"] = float(manifest.get("threshold")) == threshold
    checks["window_matches"] = int(manifest.get("sliding_window")) == window_size
    checks["request_matches"] = manifest.get("config", {}).get("request_id") == REFERENCE_REQUEST_ID

    reference_scores_all = reference["scores"]
    checks["reference_covers_context"] = reference_scores_all.shape[:2] == scores.shape[:2] and (
        reference_scores_all.shape[-1] >= scores.shape[-1]
    )
    if checks["reference_covers_context"]:
        reference_scores = reference_scores_all[..., : scores.shape[-1]]
        reference_valid = reference["score_valid_mask"][..., : scores.shape[-1]].astype(np.bool_, copy=False)
        reference_predicted_stored = reference["predicted_drop_mask"][..., : scores.shape[-1]].astype(
            np.bool_, copy=False
        )
        score_difference = np.abs(scores - reference_scores)
        max_abs_score_difference = float(score_difference.max(initial=0.0))
        mean_abs_score_difference = float(score_difference.mean())
        checks["reference_scores_all_valid"] = bool(reference_valid.all())
        checks["scores_within_atol"] = bool(np.all(score_difference <= score_atol))
        reference_predicted = reference_scores < threshold
        checks["reference_stored_predicted_consistent"] = bool(
            np.array_equal(reference_predicted, reference_predicted_stored)
        )
        checks["predicted_mask_matches"] = bool(np.array_equal(predicted, reference_predicted))
        _, reference_final = reconstruct_masks(reference_scores, threshold, window_size)
        checks["reconstructed_final_mask_matches"] = bool(np.array_equal(final, reference_final))
        reference_removed_fraction = float(reference_final.mean())
        checks["reference_prefill_fraction_matches_record"] = bool(
            np.isclose(reference_removed_fraction, REFERENCE_PREFILL_REMOVED_FRACTION, atol=1e-12, rtol=0.0)
        )
    else:
        max_abs_score_difference = None
        mean_abs_score_difference = None
        reference_removed_fraction = None
        for name in (
            "reference_scores_all_valid",
            "scores_within_atol",
            "reference_stored_predicted_consistent",
            "predicted_mask_matches",
            "reconstructed_final_mask_matches",
            "reference_prefill_fraction_matches_record",
        ):
            checks[name] = False

    return {
        "passed": all(checks.values()),
        "reference_dir": str(reference_dir),
        "score_atol": score_atol,
        "max_abs_score_difference": max_abs_score_difference,
        "mean_abs_score_difference": mean_abs_score_difference,
        "observed_removed_fraction": float(final.mean()),
        "reference_removed_fraction": reference_removed_fraction,
        "checks": checks,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(
    output_dir: Path,
    *,
    manifest: dict[str, Any],
    scores: np.ndarray,
    predicted: np.ndarray,
    final: np.ndarray,
    context_ids: torch.Tensor,
    request: dict[str, Any],
    question_tokens: int,
    gate_a_evidence: dict[str, Any],
    comparison: dict[str, Any] | None,
    threshold: float,
    window_size: int,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=False)
    paths = {
        "manifest": output_dir / "manifest.json",
        "score_mask": output_dir / "score_mask.npz",
        "request_summary": output_dir / "request_summary.csv",
        "layer_head_summary": output_dir / "layer_head_summary.csv",
        "gate_a_evidence": output_dir / "gate_a_evidence.json",
    }
    if comparison is not None:
        paths["reference_comparison"] = output_dir / "reference_comparison.json"
    paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    np.savez_compressed(
        paths["score_mask"],
        scores=scores,
        score_valid_mask=np.ones_like(scores, dtype=np.bool_),
        predicted_drop_mask=predicted,
        reconstructed_final_drop_mask=final,
        context_token_ids=context_ids.detach().cpu().numpy().astype(np.int64, copy=False),
        shape=np.asarray(scores.shape, dtype=np.int64),
    )
    logical_total = int(final.size)
    logical_removed = int(final.sum())
    logical_kept = logical_total - logical_removed
    write_csv(
        paths["request_summary"],
        [
            {
                "request_id": request["request_id"],
                "dataset": request["dataset"],
                "subset": request["subset"],
                "context_tokens_scored": scores.shape[-1],
                "question_tokens_not_scored": question_tokens,
                "threshold": threshold,
                "window": window_size,
                "logical_kept_kv": logical_kept,
                "logical_total_kv": logical_total,
                "removed_fraction": logical_removed / logical_total,
                "compression_factor": logical_total / logical_kept if logical_kept else float("inf"),
                "gate_a_evidence_verified": gate_a_evidence["passed"],
                "matched_reference_verified": comparison["passed"] if comparison is not None else "",
            }
        ],
    )
    layer_head_rows = []
    for layer in range(scores.shape[0]):
        for head in range(scores.shape[1]):
            head_scores = scores[layer, head]
            removed = int(final[layer, head].sum())
            layer_head_rows.append(
                {
                    "request_id": request["request_id"],
                    "layer": layer,
                    "kv_head": head,
                    "sequence_tokens": scores.shape[-1],
                    "kept_tokens": scores.shape[-1] - removed,
                    "removed_tokens": removed,
                    "retention_ratio": (scores.shape[-1] - removed) / scores.shape[-1],
                    "score_mean": float(head_scores.mean()),
                    "score_std": float(head_scores.std()),
                    "score_min": float(head_scores.min()),
                    "score_max": float(head_scores.max()),
                }
            )
    write_csv(paths["layer_head_summary"], layer_head_rows)
    paths["gate_a_evidence"].write_text(
        json.dumps(gate_a_evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if comparison is not None:
        paths["reference_comparison"].write_text(
            json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return paths


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if args.window_size < 0 or args.score_atol < 0:
        raise ValueError("--window-size and --score-atol must be non-negative")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.reference_trace is not None and (args.input_jsonl is not None or args.preset != "hardware"):
        raise ValueError("--reference-trace is valid only with --preset hardware")
    expected_predictor = f"nvidia/KVzap-mlp-{args.model_name.split('/')[-1]}"
    if args.model_name != DEFAULT_MODEL or args.predictor_name != expected_predictor:
        raise ValueError("The verified gate-A boundary supports only Qwen/Qwen3-8B with its official MLP predictor")

    gate_a_evidence = validate_gate_a_evidence(
        args.gate_a_evidence,
        model_name=args.model_name,
        predictor_name=args.predictor_name,
        threshold=args.threshold,
        window_size=args.window_size,
    )
    if not gate_a_evidence["passed"]:
        failed = [name for name, passed in gate_a_evidence["checks"].items() if not passed]
        raise ValueError(f"Frozen gate-A evidence failed validation: {failed}")
    print(
        f"Gate-A evidence verified: {gate_a_evidence['experiment_id']} "
        f"({gate_a_evidence['implementation_git_commit']})"
    )

    if args.input_jsonl is not None:
        request = load_jsonl_request(args.input_jsonl, args.request_id)
        request_source = str(args.input_jsonl)
        preset = None
    else:
        request = build_builtin_request(args.preset, args.context_repetitions)
        request_source = f"builtin/{args.preset}"
        preset = args.preset
    predictor_snapshot = Path(snapshot_download(repo_id=args.predictor_name))
    predictor_revision = predictor_snapshot.name
    if predictor_revision != gate_a_evidence["predictor_revision"]:
        raise ValueError(
            "Predictor revision differs from frozen gate A: "
            f"expected {gate_a_evidence['predictor_revision']}, got {predictor_revision}"
        )
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, device_map="auto", dtype="auto")
    model_revision = getattr(pipe.model.config, "_commit_hash", None)
    tokenized = pipe.preprocess(
        request["context"],
        [request["question"]],
        answer_prefix="",
        max_context_length=pipe.tokenizer.model_max_length,
        enable_thinking=False,
    )
    context_ids = tokenized["context_ids"]
    context_tokens = int(context_ids.shape[1])
    question_tokens = int(tokenized["questions_ids"][0].shape[1])
    if context_tokens <= args.window_size:
        raise ValueError(
            f"Context has {context_tokens} tokens, which does not exceed the protected window {args.window_size}"
        )
    if args.reference_trace is not None and context_tokens != REFERENCE_CONTEXT_TOKENS:
        raise AssertionError(
            f"Hardware reference context changed: expected {REFERENCE_CONTEXT_TOKENS} tokens, got {context_tokens}"
        )

    predictor = KVzapPress(model_type="mlp")
    seed_everything(args.seed)
    print(f"Running one read-only predictor prefill with {context_tokens} context tokens...")
    cache = DynamicCache()
    with torch.no_grad(), PredictorScoreObserver(pipe.model, predictor) as observer:
        pipe.model.model(input_ids=context_ids.to(pipe.model.device), past_key_values=cache)
    assert_no_runtime_mask_state(pipe.model)
    scores = stack_layer_scores(observer.layer_scores, len(language_model_layers(pipe.model)))
    if len(observer.original_score_dtypes) != 1:
        raise AssertionError(f"Predictor score dtype changed across layers: {sorted(observer.original_score_dtypes)}")
    if not np.isfinite(scores).all():
        raise AssertionError("Predictor trace contains NaN or infinity")
    original_score_dtype = next(iter(observer.original_score_dtypes))
    predicted, final = reconstruct_masks(scores, args.threshold, args.window_size)
    comparison = None
    if args.reference_trace is not None:
        comparison = compare_with_reference(
            scores,
            predicted,
            final,
            reference_dir=args.reference_trace,
            threshold=args.threshold,
            window_size=args.window_size,
            score_atol=args.score_atol,
        )
    capture_valid = gate_a_evidence["passed"] and (comparison is None or comparison["passed"])

    config = {
        "model": args.model_name,
        "model_revision": model_revision,
        "predictor": args.predictor_name,
        "predictor_revision": predictor_revision,
        "threshold": args.threshold,
        "sliding_window": args.window_size,
        "seed": args.seed,
        "preset": preset,
        "request_source": request_source,
        "context_repetitions": args.context_repetitions if args.input_jsonl is None else None,
        "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "context_tokens": context_tokens,
        "question_tokens": question_tokens,
        "score_atol": args.score_atol if args.reference_trace is not None else None,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": datetime.now(timezone.utc).strftime("kvzap-predictor-trace-%Y%m%dT%H%M%SZ"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config_hash": stable_hash(config),
        "capture_scope": "context_prefill_predictor_only",
        "capture_status": "valid" if capture_valid else "invalid_reference_mismatch",
        "valid_for_structural_analysis": capture_valid,
        "model": args.model_name,
        "model_revision": model_revision,
        "predictor_checkpoint": args.predictor_name,
        "predictor_revision": predictor_revision,
        "threshold": args.threshold,
        "sliding_window": args.window_size,
        "tensor_layout": "L,H,T",
        "score_dtype": "float32",
        "original_score_dtype": original_score_dtype,
        "mask_provenance": "offline_threshold_and_prefill_window_reconstruction",
        "generation_performed": False,
        "dms_press_used": False,
        "masked_key_indices_created": False,
        "fake_key_attention_used": False,
        "physical_compression_measured": False,
        "contains_attention_matrix": False,
        "gate_a_evidence": gate_a_evidence,
        "reference_validation": comparison,
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
        "cuda_available": bool(torch.cuda.is_available()),
        "gpu": str(torch.cuda.get_device_name(0)) if torch.cuda.is_available() else None,
        "config": config,
    }
    paths = write_outputs(
        args.output_dir,
        manifest=manifest,
        scores=scores,
        predicted=predicted,
        final=final,
        context_ids=context_ids,
        request=request,
        question_tokens=question_tokens,
        gate_a_evidence=gate_a_evidence,
        comparison=comparison,
        threshold=args.threshold,
        window_size=args.window_size,
    )
    print(f"Observed score shape: {scores.shape}")
    print(f"Reconstructed prefill removed fraction: {final.mean():.2%}")
    if comparison is not None:
        print(f"Reference max absolute score difference: {comparison['max_abs_score_difference']}")
        print(f"Matched-reference check passed: {comparison['passed']}")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    if comparison is not None and not comparison["passed"]:
        failed = [name for name, passed in comparison["checks"].items() if not passed]
        print(f"Matched-reference failed checks: {failed}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
