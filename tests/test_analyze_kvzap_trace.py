# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import csv
import json

import numpy as np

from tools.analyze_kvzap_trace import (
    analyze_decoding_events,
    analyze_groups,
    analyze_request_pairs,
    analyze_trace,
    independent_jaccard,
    jaccard,
    load_pilot_metadata,
    run_lengths,
    validate_trace,
)


def test_run_lengths_and_jaccard():
    mask = np.asarray([[True, True, False, True, False, False]])
    assert run_lengths(mask, True).tolist() == [2, 1]
    assert run_lengths(mask, False).tolist() == [1, 2]
    assert jaccard(np.asarray([True, False, True]), np.asarray([True, True, False])) == 1 / 3
    assert independent_jaccard(0.5, 0.5) == 1 / 3


def make_event(step, cache_tokens, newly_dropped, newly_admitted, cumulative_dropped):
    return {
        "request_id": "r0",
        "step": str(step),
        "phase": "prefill" if step == 0 else "decode",
        "layer": "0",
        "kv_head": "0",
        "cache_tokens": str(cache_tokens),
        "hot_tokens": "2",
        "cold_tokens": "0",
        "newly_admitted_tokens": str(newly_admitted),
        "newly_dropped_tokens": str(newly_dropped),
        "logical_kept_tokens": str(cache_tokens - cumulative_dropped),
        "cumulative_dropped_tokens": str(cumulative_dropped),
    }


def test_decode_prompt_chunk_is_separate_from_generation():
    trace = {
        "trace_dir": "trace",
        "trace_id": "e0::r0",
        "manifest": {"experiment_id": "e0"},
        "request": {"request_id": "r0"},
        "events": [
            make_event(0, 4, 2, 0, 2),
            make_event(1, 7, 2, 1, 4),
            make_event(2, 8, 1, 0, 5),
        ],
        "predictor_only": False,
    }
    rows, summary = analyze_decoding_events(trace, expected_layer_heads=1)
    assert [row["event_kind"] for row in rows] == ["context_prefill", "prompt_chunk", "generation"]
    assert summary["context_prefill_tokens"] == 4
    assert summary["prompt_chunk_tokens"] == 3
    assert summary["generation_steps"] == 1
    assert summary["generation_newly_dropped_mean"] == 1


def test_analyze_trace_block_and_window_metrics():
    # One layer, two heads, six tokens. The final two tokens are the protected window.
    scores = np.asarray(
        [[[-2.0, 1.0, -3.0, -4.0, -5.0, 2.0], [-2.0, -3.0, 1.0, 2.0, -1.0, -2.0]]],
        dtype=np.float32,
    )
    predicted = scores < 0
    final = predicted.copy()
    final[..., -2:] = False
    trace = {
        "trace_dir": "trace",
        "trace_id": "e0::r0",
        "manifest": {
            "experiment_id": "e0",
            "model": "model",
            "dataset": "builtin",
            "subset": "test",
            "predictor_checkpoint": "predictor",
            "threshold": 0.0,
            "sliding_window": 2,
        },
        "request": {
            "request_id": "r0",
            "prompt_tokens": "4",
            "generated_tokens_retokenized": "2",
        },
        "scores": scores,
        "valid": np.ones_like(scores, dtype=np.bool_),
        "predicted": predicted,
        "final": final,
        "events": [
            make_event(0, 6, int(final[0, 0].sum()), int((~final[0, 0, :4]).sum()), int(final[0, 0].sum())),
            make_event(0, 6, int(final[0, 1].sum()), int((~final[0, 1, :4]).sum()), int(final[0, 1].sum())),
        ],
    }
    # Give the second event the other KV-head identity so the event count is 1 layer x 2 heads.
    trace["events"][1] = dict(trace["events"][1], kv_head="1")
    result = analyze_trace(trace, block_sizes=[2], threshold_deltas=[0.0])
    summary = result["summary"]
    assert summary["logical_total_kv"] == 12
    assert summary["protected_recent_final_drops"] == 0
    assert summary["protected_recent_predicted_drops"] == 3
    block = result["block"][0]
    assert block["block_size"] == 2
    assert 0 <= block["mixed_block_fraction"] <= 1
    assert block["physical_compression_factor_padded"] <= summary["logical_compression_factor"]


def write_predictor_trace(path, request_id="r0"):
    path.mkdir()
    scores = np.asarray(
        [[[-2.0, 1.0, -3.0, -4.0, -5.0, 2.0], [-2.0, -3.0, 1.0, 2.0, -1.0, -2.0]]],
        dtype=np.float32,
    )
    predicted = scores < 0
    final = predicted.copy()
    final[..., -2:] = False
    evidence = {"passed": True, "checks": {"frozen_hashes": True}}
    manifest = {
        "schema_version": "kvzap-predictor-trace-1.1",
        "experiment_id": "e0",
        "git_commit": "abc",
        "config_hash": "config",
        "capture_status": "valid",
        "valid_for_structural_analysis": True,
        "tensor_layout": "L,H,T",
        "threshold": 0.0,
        "sliding_window": 2,
        "model": "model",
        "model_revision": "model-revision",
        "predictor_checkpoint": "predictor",
        "predictor_revision": "predictor-revision",
        "gate_a_evidence": evidence,
        "generation_performed": False,
        "dms_press_used": False,
        "masked_key_indices_created": False,
        "fake_key_attention_used": False,
    }
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "gate_a_evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    np.savez_compressed(
        path / "score_mask.npz",
        scores=scores,
        score_valid_mask=np.ones_like(scores, dtype=np.bool_),
        predicted_drop_mask=predicted,
        reconstructed_final_drop_mask=final,
        context_token_ids=np.arange(6, dtype=np.int64).reshape(1, 6),
        shape=np.asarray(scores.shape, dtype=np.int64),
    )
    total = final.size
    removed = int(final.sum())
    with (path / "request_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "request_id",
                "dataset",
                "subset",
                "context_tokens_scored",
                "question_tokens_not_scored",
                "logical_kept_kv",
                "logical_total_kv",
                "removed_fraction",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "request_id": request_id,
                "dataset": "builtin",
                "subset": "test",
                "context_tokens_scored": 6,
                "question_tokens_not_scored": 2,
                "logical_kept_kv": total - removed,
                "logical_total_kv": total,
                "removed_fraction": removed / total,
            }
        )
    (path / "layer_head_summary.csv").write_text("request_id,layer,kv_head\n", encoding="utf-8")


def test_predictor_only_trace_validation_and_analysis(tmp_path):
    trace_dir = tmp_path / "predictor"
    write_predictor_trace(trace_dir)

    trace = validate_trace(trace_dir)
    result = analyze_trace(trace, block_sizes=[2], threshold_deltas=[0.0])

    assert trace["predictor_only"] is True
    assert trace["events"] == []
    assert result["decoding"] == []
    assert result["summary"]["decoding_trace_available"] is False
    assert result["summary"]["context_tokens_scored"] == 6
    assert result["summary"]["question_tokens_not_scored"] == 2
    assert result["summary"]["cold_removed_fraction"] == 5 / 8
    head_pair = result["head_similarity"][0]
    assert np.isclose(
        head_pair["keep_jaccard_excess"],
        head_pair["keep_jaccard"] - head_pair["expected_keep_jaccard_independent"],
    )


def test_request_pair_similarity_uses_retention_profiles(tmp_path):
    left_dir = tmp_path / "left"
    right_dir = tmp_path / "right"
    write_predictor_trace(left_dir, "left")
    write_predictor_trace(right_dir, "right")
    results = [
        analyze_trace(validate_trace(path), block_sizes=[2], threshold_deltas=[0.0])
        for path in (left_dir, right_dir)
    ]

    rows = analyze_request_pairs(results)

    assert len(rows) == 1
    assert rows[0]["layer_head_retention_pearson"] == 1.0


def test_pilot_metadata_enables_group_summaries(tmp_path):
    trace_dir = tmp_path / "trace"
    write_predictor_trace(trace_dir, "r0")
    result = analyze_trace(validate_trace(trace_dir), block_sizes=[2], threshold_deltas=[0.0])
    manifest_path = tmp_path / "pilot.manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "kvzap-real-pilot-1.1",
                "selected_request_count": 1,
                "selected_requests": [
                    {
                        "request_id": "r0",
                        "category": "retrieval",
                        "task": "qasper",
                        "length_bucket": [0, 10],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    _, metadata = load_pilot_metadata(manifest_path)
    rows = analyze_groups([result], metadata)

    assert {(row["group_type"], row["group_value"]) for row in rows} == {
        ("all", "all"),
        ("category", "retrieval"),
        ("task", "retrieval/qasper"),
        ("length_bucket", "[0,10)"),
    }
    assert all(row["request_count"] == 1 for row in rows)
