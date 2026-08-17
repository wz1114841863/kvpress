# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from tools.export_kvzap_predictor_trace import (
    GATE_A_CONFIG_HASH,
    GATE_A_EXPERIMENT_ID,
    GATE_A_GIT_COMMIT,
    GATE_A_PREDICTOR_REVISION,
    PredictorScoreObserver,
    compare_with_reference,
    reconstruct_masks,
    stack_layer_scores,
    validate_gate_a_evidence,
)


class FixedPredictor:
    def score(self, module, hidden_states, keys, values, attentions, kwargs):
        del module, keys, values, attentions, kwargs
        return hidden_states[..., :2].transpose(1, 2)


def test_observer_reads_hidden_states_without_replacing_attention_output():
    observer = PredictorScoreObserver(model=None, predictor=FixedPredictor())
    hidden_states = torch.arange(12, dtype=torch.bfloat16).reshape(1, 3, 4)
    output = object()

    returned = observer._hook(
        SimpleNamespace(layer_idx=0),
        (),
        {"hidden_states": hidden_states},
        output,
    )

    assert returned is None
    assert observer.layer_scores[0].shape == (2, 3)
    assert observer.original_score_dtypes == {"torch.bfloat16"}

    with pytest.raises(AssertionError, match="more than once"):
        observer._hook(SimpleNamespace(layer_idx=0), (), {"hidden_states": hidden_states}, output)


def test_reconstruct_masks_protects_recent_window():
    scores = np.asarray([[[-5.0, -3.0, -6.0, -7.0]]], dtype=np.float32)

    predicted, final = reconstruct_masks(scores, threshold=-4.0, window_size=2)

    assert predicted.tolist() == [[[True, False, True, True]]]
    assert final.tolist() == [[[True, False, False, False]]]


def test_stack_layer_scores_requires_complete_uniform_layers():
    layer_scores = {
        0: np.zeros((2, 4), dtype=np.float32),
        1: np.ones((2, 4), dtype=np.float32),
    }
    stacked = stack_layer_scores(layer_scores, expected_layers=2)
    assert stacked.shape == (2, 2, 4)

    with pytest.raises(AssertionError, match="missing"):
        stack_layer_scores({0: layer_scores[0]}, expected_layers=2)


def write_reference(path, scores, threshold=-4.0, window=2):
    path.mkdir()
    manifest = {
        "trace_equivalence_verified": True,
        "model": "Qwen/Qwen3-8B",
        "predictor_checkpoint": "nvidia/KVzap-mlp-Qwen3-8B",
        "predictor_revision": GATE_A_PREDICTOR_REVISION,
        "threshold": threshold,
        "sliding_window": window,
        "config": {"request_id": "builtin_hardware_trace"},
    }
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    predicted = scores < threshold
    np.savez_compressed(
        path / "score_mask.npz",
        scores=scores,
        score_valid_mask=np.ones_like(scores, dtype=np.bool_),
        predicted_drop_mask=predicted,
        shape=np.asarray(scores.shape),
    )


def test_reference_comparison_accepts_matching_context_prefix(tmp_path, monkeypatch):
    scores = np.asarray(
        [
            [[-5.0, -3.0, -6.0, -2.0], [-1.0, -7.0, -3.0, -8.0]],
            [[-5.0, -5.0, -2.0, -2.0], [-6.0, -1.0, -7.0, -1.0]],
        ],
        dtype=np.float32,
    )
    reference_scores = np.concatenate([scores, np.zeros((*scores.shape[:2], 2), dtype=np.float32)], axis=-1)
    reference_dir = tmp_path / "reference"
    write_reference(reference_dir, reference_scores)
    predicted, final = reconstruct_masks(scores, threshold=-4.0, window_size=2)
    monkeypatch.setattr(
        "tools.export_kvzap_predictor_trace.REFERENCE_PREFILL_REMOVED_FRACTION",
        float(final.mean()),
    )

    report = compare_with_reference(
        scores,
        predicted,
        final,
        reference_dir=reference_dir,
        threshold=-4.0,
        window_size=2,
        score_atol=0.0,
        verify_frozen_hashes=False,
    )

    assert report["passed"] is True
    assert report["max_abs_score_difference"] == 0.0


def test_reference_comparison_rejects_score_or_mask_mismatch(tmp_path, monkeypatch):
    reference_scores = np.full((1, 1, 4), -5.0, dtype=np.float32)
    reference_dir = tmp_path / "reference"
    write_reference(reference_dir, reference_scores)
    observed_scores = reference_scores.copy()
    observed_scores[..., 0] = -3.0
    predicted, final = reconstruct_masks(observed_scores, threshold=-4.0, window_size=2)
    monkeypatch.setattr(
        "tools.export_kvzap_predictor_trace.REFERENCE_PREFILL_REMOVED_FRACTION",
        0.5,
    )

    report = compare_with_reference(
        observed_scores,
        predicted,
        final,
        reference_dir=reference_dir,
        threshold=-4.0,
        window_size=2,
        score_atol=0.0,
        verify_frozen_hashes=False,
    )

    assert report["passed"] is False
    assert report["checks"]["scores_within_atol"] is False
    assert report["checks"]["predicted_mask_matches"] is False


def write_gate_a_evidence(path):
    path.mkdir()
    scores = np.full((36, 8, 987), -5.0, dtype=np.float32)
    predicted, final = reconstruct_masks(scores, threshold=-4.0, window_size=128)
    manifest = {
        "schema_version": "kvzap-predictor-trace-1.0",
        "experiment_id": GATE_A_EXPERIMENT_ID,
        "git_commit": GATE_A_GIT_COMMIT,
        "config_hash": GATE_A_CONFIG_HASH,
        "capture_status": "valid",
        "valid_for_structural_analysis": True,
        "model": "Qwen/Qwen3-8B",
        "predictor_checkpoint": "nvidia/KVzap-mlp-Qwen3-8B",
        "predictor_revision": GATE_A_PREDICTOR_REVISION,
        "threshold": -4.0,
        "sliding_window": 128,
        "generation_performed": False,
        "dms_press_used": False,
        "masked_key_indices_created": False,
        "fake_key_attention_used": False,
    }
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "reference_comparison.json").write_text(
        json.dumps({"passed": True, "max_abs_score_difference": 0.0}), encoding="utf-8"
    )
    np.savez_compressed(
        path / "score_mask.npz",
        scores=scores,
        score_valid_mask=np.ones_like(scores, dtype=np.bool_),
        predicted_drop_mask=predicted,
        reconstructed_final_drop_mask=final,
        shape=np.asarray(scores.shape),
    )
    return final


def test_gate_a_evidence_checks_structure_and_semantics(tmp_path, monkeypatch):
    evidence_dir = tmp_path / "gate_a"
    final = write_gate_a_evidence(evidence_dir)
    monkeypatch.setattr(
        "tools.export_kvzap_predictor_trace.REFERENCE_PREFILL_REMOVED_FRACTION",
        float(final.mean()),
    )

    report = validate_gate_a_evidence(
        evidence_dir,
        model_name="Qwen/Qwen3-8B",
        predictor_name="nvidia/KVzap-mlp-Qwen3-8B",
        threshold=-4.0,
        window_size=128,
        verify_frozen_hashes=False,
    )

    assert report["passed"] is True
    assert report["score_shape"] == [36, 8, 987]


def test_gate_a_evidence_rejects_mask_inconsistency(tmp_path, monkeypatch):
    evidence_dir = tmp_path / "gate_a"
    final = write_gate_a_evidence(evidence_dir)
    with np.load(evidence_dir / "score_mask.npz") as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    arrays["predicted_drop_mask"][0, 0, 0] = False
    np.savez_compressed(evidence_dir / "score_mask.npz", **arrays)
    monkeypatch.setattr(
        "tools.export_kvzap_predictor_trace.REFERENCE_PREFILL_REMOVED_FRACTION",
        float(final.mean()),
    )

    report = validate_gate_a_evidence(
        evidence_dir,
        model_name="Qwen/Qwen3-8B",
        predictor_name="nvidia/KVzap-mlp-Qwen3-8B",
        threshold=-4.0,
        window_size=128,
        verify_frozen_hashes=False,
    )

    assert report["passed"] is False
    assert report["checks"]["predicted_mask_consistent"] is False
