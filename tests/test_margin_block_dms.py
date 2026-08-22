import pytest
import torch

from kvpress import DMSPress
from kvpress.presses.margin_block_dms import make_margin_block_drop_transform


def test_margin_block_transform_coalesces_full_blocks():
    transform = make_margin_block_drop_transform(block_size=4, margin=0.0)
    scores = torch.tensor([[[-5.0, -5.0, -5.0, -5.0, -5.0, -3.0, -5.0, -5.0]]])
    actual = transform(scores, threshold=-4.0, matured_start=0)
    expected = torch.tensor([[[True, True, True, True, False, False, False, False]]])
    assert torch.equal(actual, expected)


def test_margin_block_positive_margin_can_add_drops():
    scores = torch.full((1, 1, 4), -3.9)
    assert not make_margin_block_drop_transform(4, 0.0)(scores, -4.0, 0).any()
    assert make_margin_block_drop_transform(4, 0.25)(scores, -4.0, 0).all()


def test_margin_block_transform_rejects_decode_misalignment():
    with pytest.raises(ValueError, match="block-aligned"):
        make_margin_block_drop_transform(4, 0.0)(torch.zeros((1, 1, 4)), -4.0, 1)


def test_dms_supplies_matured_start_before_transform():
    class Scorer:
        def score(self, module, hidden_states, keys, values, attentions, kwargs):
            return torch.full((1, 1, hidden_states.shape[1]), -5.0)

    class Layer:
        keys = torch.zeros((1, 1, 6, 2))
        values = torch.zeros((1, 1, 6, 2))

    class Cache:
        layers = [Layer()]

    class Module:
        layer_idx = 0
        masked_key_indices = None

    press = DMSPress(
        press=Scorer(),
        threshold=-4.0,
        sliding_window_size=2,
        drop_mask_transform=make_margin_block_drop_transform(4, 0.0),
    )
    press.forward_hook(
        Module(),
        [],
        {"hidden_states": torch.zeros((1, 6, 1)), "past_key_values": Cache(), "cache_position": torch.arange(6)},
        [],
    )
    assert press.compression_ratios[0] == 4 / 6
