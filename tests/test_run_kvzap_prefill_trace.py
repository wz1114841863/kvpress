# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pytest
import torch

from kvpress.trace import KVzapTraceRecorder
from tools.run_kvzap_prefill_trace import validate_prefill_recorder


def make_prefill_recorder() -> KVzapTraceRecorder:
    recorder = KVzapTraceRecorder("prefill-request")
    scores = torch.tensor([[[-5.0, -3.0, -6.0, -2.0], [-1.0, -7.0, -3.0, -8.0]]])
    matured_scores = scores[..., :2]
    matured_drop = matured_scores < -4.0
    recorder(
        layer_idx=0,
        prefilling=True,
        cache_len=4,
        q_len=4,
        score_start=0,
        scores=scores,
        predicted_drop_mask=scores < -4.0,
        threshold=-4.0,
        matured_start=0,
        matured_scores=matured_scores,
        matured_drop_mask=matured_drop,
        score_buffer_length=2,
        cumulative_masked_tokens=int(matured_drop.sum()),
        compression_ratio=float(matured_drop.sum() / 8),
    )
    return recorder


def test_validate_prefill_recorder_accepts_one_event_per_layer():
    arrays = validate_prefill_recorder(
        make_prefill_recorder(),
        expected_layers=1,
        context_tokens=4,
        sliding_window=2,
    )

    assert tuple(arrays["shape"]) == (1, 2, 4)
    assert np.all(arrays["score_valid_mask"])
    assert not arrays["final_drop_mask"][..., -2:].any()


def test_validate_prefill_recorder_rejects_decode_event():
    recorder = make_prefill_recorder()
    recorder.events[0]["phase"] = "decode"

    with pytest.raises(AssertionError, match="decode events"):
        validate_prefill_recorder(recorder, expected_layers=1, context_tokens=4, sliding_window=2)


def test_validate_prefill_recorder_rejects_missing_layer():
    with pytest.raises(AssertionError, match="one prefill event per layer"):
        validate_prefill_recorder(
            make_prefill_recorder(),
            expected_layers=2,
            context_tokens=4,
            sliding_window=2,
        )
