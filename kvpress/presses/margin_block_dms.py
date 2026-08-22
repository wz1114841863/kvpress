# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

"""Cold-region B-token score coalescing for explicit DMS accuracy experiments."""

from __future__ import annotations

import torch


def make_margin_block_drop_transform(block_size: int, margin: float):
    """Return a DMS drop-mask transform aligned to absolute token block boundaries.

    A block drops only when all its scores are below ``threshold + margin``.
    The transform is deliberately state-free and rejects a misaligned mature
    range: decode-time coalescing would require a separate lifecycle design.
    """
    if block_size <= 0:
        raise ValueError(f"block_size must be positive, got {block_size}")

    def transform(scores: torch.Tensor, threshold: float, matured_start: int) -> torch.Tensor:
        if matured_start % block_size:
            raise ValueError(
                "Margin block coalescing requires an absolute block-aligned mature range; "
                "use prefill-only DMS for this experiment."
            )
        token_count = scores.shape[-1]
        padding = (-token_count) % block_size
        padded = torch.nn.functional.pad(scores, (0, padding), value=float("inf"))
        blocks = padded.reshape(*scores.shape[:-1], -1, block_size)
        block_drop = (blocks < threshold + margin).all(dim=-1)
        return block_drop.repeat_interleave(block_size, dim=-1)[..., :token_count]

    return transform
