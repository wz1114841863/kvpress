# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

import pytest
import torch

from kvpress.attention_patch import rebuild_dms_masked_key_indices, validate_masked_key_indices


def test_mask_validation_is_disabled_by_default():
    module = SimpleNamespace(
        layer_idx=3,
        masked_key_indices=(torch.tensor([0]), torch.tensor([0]), torch.tensor([9])),
    )
    validate_masked_key_indices(module, torch.zeros(1, 2, 4, 8))


def test_mask_validation_reports_context_and_bounds():
    module = SimpleNamespace(
        layer_idx=3,
        masked_key_indices=(torch.tensor([0]), torch.tensor([1]), torch.tensor([4])),
        _kvpress_validate_mask_indices=True,
        _kvpress_diagnostic_context="trace-on",
    )
    with pytest.raises(IndexError) as caught:
        validate_masked_key_indices(module, torch.zeros(1, 2, 4, 8))

    message = str(caught.value)
    assert "context=trace-on" in message
    assert "layer=3" in message
    assert "key_shape=(1, 2, 4, 8)" in message
    assert "token=[4,4] limit=4" in message


def test_mask_validation_accepts_in_bounds_indices():
    module = SimpleNamespace(
        layer_idx=3,
        masked_key_indices=(torch.tensor([0]), torch.tensor([1]), torch.tensor([3])),
        _kvpress_validate_mask_indices=True,
        _kvpress_diagnostic_context="trace-off",
    )
    validate_masked_key_indices(module, torch.zeros(1, 2, 4, 8))


def test_dms_indices_are_rebuilt_from_boolean_mask():
    mask = torch.zeros(1, 2, 3, dtype=torch.bool)
    mask[0, 1, 2] = True
    module = SimpleNamespace(
        layer_idx=3,
        _dms_masked_key_mask=mask,
        masked_key_indices=(torch.tensor([0]), torch.tensor([999]), torch.tensor([2])),
    )

    rebuild_dms_masked_key_indices(module, torch.zeros(1, 2, 4, 8))

    batch, head, token = module.masked_key_indices
    assert batch.tolist() == [0]
    assert head.tolist() == [1]
    assert token.tolist() == [2]
    assert module._dms_masked_key_mask.shape == (1, 2, 4)
