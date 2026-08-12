# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import csv
import json

import numpy as np
import torch

from kvpress.trace import KVzapTraceRecorder


def test_kvzap_trace_recorder_roundtrip(tmp_path):
    recorder = KVzapTraceRecorder("request-0", near_threshold_epsilon=0.2)
    prefill_scores = torch.tensor(
        [[[-1.0, 1.0, -2.0, 2.0, -0.1], [1.0, -3.0, 2.0, -4.0, 3.0]]]
    )
    prefill_matured = prefill_scores[..., :3] < 0.0
    recorder(
        layer_idx=0,
        prefilling=True,
        cache_len=5,
        q_len=5,
        score_start=0,
        scores=prefill_scores,
        predicted_drop_mask=prefill_scores < 0.0,
        threshold=0.0,
        matured_start=0,
        matured_scores=prefill_scores[..., :3],
        matured_drop_mask=prefill_matured,
        cumulative_drop_mask=torch.nn.functional.pad(prefill_matured, (0, 2)),
        score_buffer_length=2,
        cumulative_masked_tokens=int(prefill_matured.sum()),
        compression_ratio=float(prefill_matured.sum() / 10),
    )

    decode_scores = torch.tensor([[[-0.5], [0.5]]])
    decode_matured = torch.tensor([[[False], [True]]])
    recorder(
        layer_idx=0,
        prefilling=False,
        cache_len=6,
        q_len=1,
        score_start=5,
        scores=decode_scores,
        predicted_drop_mask=decode_scores < 0.0,
        threshold=0.0,
        matured_start=3,
        matured_scores=prefill_scores[..., 3:4],
        matured_drop_mask=decode_matured,
        cumulative_drop_mask=torch.cat(
            [prefill_matured, decode_matured, torch.zeros(1, 2, 2, dtype=torch.bool)], dim=-1
        ),
        score_buffer_length=2,
        cumulative_masked_tokens=int(prefill_matured.sum() + decode_matured.sum()),
        compression_ratio=float((prefill_matured.sum() + decode_matured.sum()) / 12),
    )

    arrays = recorder.validate(sliding_window=2)
    assert tuple(arrays["shape"]) == (1, 2, 6)
    assert arrays["score_valid_mask"].all()
    assert np.array_equal(arrays["predicted_drop_mask"][0, :, :5], prefill_scores.numpy()[0] < 0.0)
    assert np.array_equal(arrays["final_drop_mask"][0, :, :3], prefill_matured.numpy()[0])
    assert np.array_equal(arrays["final_drop_mask"][0, :, 3:4], decode_matured.numpy()[0])
    assert not arrays["final_drop_mask"][..., -2:].any()

    output_dir = tmp_path / "trace"
    paths = recorder.write(
        output_dir,
        manifest={"threshold": 0.0, "sliding_window": 2},
        request_metadata={"prompt_tokens": 5, "generated_tokens_retokenized": 1},
        sliding_window=2,
    )
    with paths["manifest"].open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    assert manifest["schema_version"] == "1.0"
    assert manifest["tensor_layout"] == "L,H,T"
    assert manifest["contains_attention_matrix"] is False

    with np.load(paths["score_mask"]) as saved:
        assert np.array_equal(saved["final_drop_mask"], arrays["final_drop_mask"])
        assert np.allclose(saved["scores"], arrays["scores"], equal_nan=True)

    with paths["request_summary"].open(encoding="utf-8", newline="") as stream:
        request_row = next(csv.DictReader(stream))
    assert int(request_row["logical_total_kv"]) == 12
    assert int(request_row["logical_kept_kv"]) == 8
    assert float(request_row["removed_fraction"]) == 4 / 12
    assert float(request_row["compression_factor"]) == 12 / 8


def test_kvzap_trace_rejects_batch_greater_than_one():
    recorder = KVzapTraceRecorder("request-0")
    scores = torch.zeros(2, 1, 3)
    try:
        recorder(
            layer_idx=0,
            prefilling=True,
            cache_len=3,
            q_len=3,
            score_start=0,
            scores=scores,
            predicted_drop_mask=scores < -4.0,
            threshold=-4.0,
            matured_start=None,
            matured_scores=None,
            matured_drop_mask=None,
            cumulative_drop_mask=torch.zeros(2, 1, 3, dtype=torch.bool),
            score_buffer_length=3,
            cumulative_masked_tokens=0,
            compression_ratio=0.0,
        )
    except ValueError as error:
        assert "[1,H,T]" in str(error)
    else:
        raise AssertionError("batch-size-two trace should fail")
