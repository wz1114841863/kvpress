import pytest
import torch

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
