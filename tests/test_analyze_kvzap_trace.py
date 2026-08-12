# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import numpy as np

from tools.analyze_kvzap_trace import analyze_decoding_events, analyze_trace, jaccard, run_lengths


def test_run_lengths_and_jaccard():
    mask = np.asarray([[True, True, False, True, False, False]])
    assert run_lengths(mask, True).tolist() == [2, 1]
    assert run_lengths(mask, False).tolist() == [1, 2]
    assert jaccard(np.asarray([True, False, True]), np.asarray([True, True, False])) == 1 / 3


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
