# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

import torch

from kvpress import DMSPress
from kvpress.presses.scorer_press import ScorerPress


class FixedScorer(ScorerPress):
    def score(self, module, hidden_states, keys, values, attentions, kwargs):
        return self.fixed_scores.to(device=keys.device, dtype=keys.dtype)


def run_prefill(monkeypatch, trace_callback=None, cache_position=None):
    fixed_scores = torch.tensor([[[-1.0, 0.0, 1.0], [0.0, -2.0, 2.0]]])
    keys = torch.zeros(1, 2, 3, 4)
    values = torch.zeros_like(keys)
    monkeypatch.setattr(
        "kvpress.presses.dms_press.extract_keys_and_values",
        lambda cache, layer_idx: (keys, values),
    )
    scorer = FixedScorer()
    scorer.fixed_scores = fixed_scores
    press = DMSPress(
        press=scorer,
        threshold=0.0,
        sliding_window_size=0,
        decoding=True,
        trace_callback=trace_callback,
    )
    module = SimpleNamespace(layer_idx=0, masked_key_indices=None)
    output = [torch.tensor([123.0])]
    returned = press.forward_hook(
        module,
        [],
        {
            "hidden_states": torch.zeros(1, 3, 4),
            "past_key_values": object(),
            "cache_position": torch.arange(3) if cache_position is None else cache_position,
        },
        output,
    )
    assert returned is output
    indices = tuple(index.clone() for index in module.masked_key_indices)
    return returned[0].clone(), indices, dict(press.compression_ratios)


def test_dms_trace_callback_does_not_change_mask_or_output(monkeypatch):
    without_trace = run_prefill(monkeypatch)
    events = []
    with_trace = run_prefill(monkeypatch, lambda **event: events.append(event))

    assert torch.equal(without_trace[0], with_trace[0])
    assert without_trace[2] == with_trace[2] == {0: 2 / 6}
    for expected, actual in zip(without_trace[1], with_trace[1]):
        assert torch.equal(expected, actual)

    assert len(events) == 1
    event = events[0]
    assert event["scores"].shape == (1, 2, 3)
    assert event["matured_drop_mask"].sum().item() == 2
    assert event["matured_start"] == 0
    # Scores equal to the threshold are kept: DMS uses a strict less-than comparison.
    assert event["matured_drop_mask"][0, 0].tolist() == [True, False, False]
    assert torch.equal(event["predicted_drop_mask"], event["matured_drop_mask"])


def test_dms_recognizes_new_dense_cache_with_absolute_positions(monkeypatch):
    _, indices, ratios = run_prefill(monkeypatch, cache_position=torch.arange(100, 103))
    assert ratios == {0: 2 / 6}
    assert indices[-1].tolist() == [0, 1]


def test_dms_reports_missing_prefill_state_before_decode(monkeypatch):
    keys = torch.zeros(1, 2, 4, 4)
    values = torch.zeros_like(keys)
    monkeypatch.setattr(
        "kvpress.presses.dms_press.extract_keys_and_values",
        lambda cache, layer_idx: (keys, values),
    )
    scorer = FixedScorer()
    scorer.fixed_scores = torch.zeros(1, 2, 1)
    press = DMSPress(press=scorer, threshold=0.0, decoding=True)
    module = SimpleNamespace(layer_idx=0, masked_key_indices=None)

    try:
        press.forward_hook(
            module,
            [],
            {
                "hidden_states": torch.zeros(1, 1, 4),
                "past_key_values": object(),
                "cache_position": torch.tensor([3]),
            },
            [torch.tensor([123.0])],
        )
    except RuntimeError as error:
        assert "missing before decoding" in str(error)
    else:
        raise AssertionError("Decoding without prefill state should fail explicitly")
