# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field
from typing import Callable, Optional

import torch
import torch.nn as nn

from kvpress.presses.base_press import BasePress
from kvpress.presses.scorer_press import ScorerPress
from kvpress.utils import extract_keys_and_values


@dataclass
class DMSPress(BasePress):
    """
    Based on Dynamic Memory Sparsification (DMS, https://arxiv.org/abs/2506.05345) inference.
    Wraps a ScorerPress and evicts keys/values with scores below a given threshold.
    This press implements a dense-prefill version of DMS, not the sparse-prefill version,
    and does not include the trained evictors from the paper.
    For a faithful implementation, please refer to https://huggingface.co/nvidia/Qwen3-8B-DMS-8x or
    https://github.com/NVIDIA/Model-Optimizer/tree/main/experimental/dms

    Unlike most presses that use a fixed compression_ratio, DMSPress uses a score threshold
    to determine which KV pairs to evict. This allows for adaptive compression where the actual
    compression ratio depends on the input content.

    Importantly, this press can be used both during prefilling and during decoding (if decoding=True).

    A sliding window protects the most recent tokens from eviction, ensuring that recently
    generated tokens are always available for attention.

    Parameters
    ----------
    press : ScorerPress
        The underlying scorer press used to compute importance scores for each token.
    threshold : float, optional
        Tokens with scores below this threshold are evicted. The optimal threshold
        depends on the scorer press being used.
    sliding_window_size : int, default=128
        Number of recent tokens protected from eviction.
    decoding : bool, default=False
        If True, compression is also applied during the decoding phase (token generation).
        If False, compression only occurs during prefill.
    trace_callback : callable, optional
        Debug/instrumentation callback invoked after each scored layer call. It is disabled
        by default. Tensor copies and serialization are the callback's responsibility.
    """

    press: ScorerPress
    threshold: Optional[float] = None
    sliding_window_size: int = 128
    decoding: bool = False
    trace_callback: Optional[Callable[..., None]] = field(default=None, repr=False, compare=False)
    scores_buffer: dict[int, torch.Tensor] = field(default_factory=dict, init=False, repr=False)
    compression_ratios: dict[int, float] = field(default_factory=dict, init=False, repr=False)

    def post_init_from_model(self, model):
        self.press.post_init_from_model(model)

    @property
    def compression_ratio(self):
        """Average compression ratio across all layers (computed after forward pass)."""
        assert len(self.compression_ratios) > 0, "Forward pass must be run to compute the compression ratio"
        return sum(self.compression_ratios.values()) / len(self.compression_ratios)

    @compression_ratio.setter
    def compression_ratio(self, value):
        """Compression ratio is read-only since it depends on threshold and input content."""
        raise AttributeError(f"compression ratio cannot be set for {type(self).__name__}")

    def forward_hook(self, module: nn.Module, input: list[torch.Tensor], kwargs: dict, output: list):
        hidden_states = kwargs["hidden_states"]
        cache = kwargs["past_key_values"]
        q_len = hidden_states.shape[1]

        # Extract layer index as int for type safety
        layer_idx: int = module.layer_idx  # type: ignore[assignment]

        # DMS must use the actual per-layer dense KV length to identify a new
        # cache. cache_position can be absolute, offset, or inconsistent across
        # layers in some pipeline/Transformers paths.
        keys, values = extract_keys_and_values(cache, layer_idx)
        cache_len = keys.shape[2]
        prefilling = cache_len == q_len

        # Reset the scores buffer and compression ratios if we are in prefilling
        if prefilling and (layer_idx == 0):
            self.scores_buffer.clear()
            self.compression_ratios.clear()

        # Skip compression during decoding if not enabled
        if not prefilling and not self.decoding:
            return output

        if not prefilling and layer_idx not in self.scores_buffer:
            raise RuntimeError(
                f"DMS score buffer for layer {layer_idx} is missing before decoding "
                f"(q_len={q_len}, cache_len={int(cache_len)}). Run context prefill with the same DMSPress state."
            )

        # Compute importance scores for the new tokens using the underlying scorer press
        scores = self.press.score(module, hidden_states, keys[:, :, -q_len:], values[:, :, -q_len:], None, kwargs)

        # Keep a boolean mask as the canonical DMS state. Integer indices are
        # rebuilt from it before attention instead of being retained across
        # forwards, because long-lived CUDA index tensors can become stale.
        bsz, num_key_value_heads = keys.shape[:2]
        masked_key_mask = getattr(module, "_dms_masked_key_mask", None)
        if prefilling or masked_key_mask is None:
            masked_key_mask = torch.zeros(
                (bsz, num_key_value_heads, cache_len),
                dtype=torch.bool,
                device=keys.device,
            )
        elif masked_key_mask.shape[2] < cache_len:
            padding = torch.zeros(
                (bsz, num_key_value_heads, cache_len - masked_key_mask.shape[2]),
                dtype=torch.bool,
                device=keys.device,
            )
            masked_key_mask = torch.cat([masked_key_mask, padding], dim=-1)
        elif masked_key_mask.shape != (bsz, num_key_value_heads, cache_len):
            raise RuntimeError(
                f"DMS mask/cache shape mismatch at layer {layer_idx}: "
                f"mask_shape={tuple(masked_key_mask.shape)}, "
                f"expected={(bsz, num_key_value_heads, cache_len)}"
            )

        # Accumulate scores in the buffer: reset during prefill, append during decoding
        if prefilling:
            self.scores_buffer[layer_idx] = scores
        else:
            self.scores_buffer[layer_idx] = torch.cat([self.scores_buffer[layer_idx], scores], dim=-1)

        matured_scores = None
        matured_drop_mask = None
        matured_start = None

        # Once the buffer exceeds the sliding window, evict tokens with low scores
        if self.scores_buffer[layer_idx].shape[-1] > self.sliding_window_size:
            # Determine how many tokens have left the sliding window and can be evicted
            n_to_evict = self.scores_buffer[layer_idx].shape[-1] - self.sliding_window_size
            scores_to_evict = self.scores_buffer[layer_idx][..., :n_to_evict]
            self.scores_buffer[layer_idx] = self.scores_buffer[layer_idx][..., n_to_evict:]
            matured_scores = scores_to_evict
            matured_drop_mask = scores_to_evict < self.threshold
            matured_start = cache_len - scores_to_evict.shape[2] - self.sliding_window_size
            if matured_start < 0:
                raise RuntimeError(
                    f"DMS buffer/cache mismatch at layer {layer_idx}: "
                    f"matured_start={matured_start}, cache_len={cache_len}, "
                    f"matured_tokens={scores_to_evict.shape[2]}, window={self.sliding_window_size}"
                )

            matured_end = matured_start + matured_drop_mask.shape[2]
            masked_key_mask[..., matured_start:matured_end] |= matured_drop_mask

        module._dms_masked_key_mask = masked_key_mask
        module.masked_key_indices = tuple(torch.where(masked_key_mask))

        # Track compression ratio as the fraction of masked tokens
        n_masked = len(module.masked_key_indices[0])
        self.compression_ratios[layer_idx] = n_masked / (bsz * num_key_value_heads * cache_len)

        if self.trace_callback is not None:
            cache_len_int = int(cache_len.item() if isinstance(cache_len, torch.Tensor) else cache_len)
            matured_start_int = (
                None
                if matured_start is None
                else int(matured_start.item() if isinstance(matured_start, torch.Tensor) else matured_start)
            )
            self.trace_callback(
                layer_idx=layer_idx,
                prefilling=prefilling,
                cache_len=cache_len_int,
                q_len=q_len,
                score_start=cache_len_int - q_len,
                scores=scores,
                predicted_drop_mask=scores < self.threshold,
                threshold=float(self.threshold),
                matured_start=matured_start_int,
                matured_scores=matured_scores,
                matured_drop_mask=matured_drop_mask,
                score_buffer_length=self.scores_buffer[layer_idx].shape[-1],
                cumulative_masked_tokens=n_masked,
                compression_ratio=self.compression_ratios[layer_idx],
            )

        return output
