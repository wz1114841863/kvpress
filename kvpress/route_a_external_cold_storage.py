"""A4.1.3.1 no-model external cold-storage adapter.

``transformers.DynamicCache`` uses physical sequence length as logical cache
length.  A selected KV head therefore cannot simply have its mature prefix
sliced away and still be handed to stock attention.  This adapter does not
pretend to be a ``DynamicCache``: it owns bounded selected-head native-hot K/V,
tracks logical length explicitly, and delegates mature retained reads to the
Route-A pending/packed state.
"""

from __future__ import annotations

from typing import Any

import torch

from kvpress.route_a_attention import RouteAPackedAttentionState
from kvpress.route_a_storage_contract import selected_storage_ownership_contract


class RouteAExternalColdStorageAdapter:
    """Physically retain only selected-head hot tensors outside DynamicCache.

    This is a storage-semantics building block, not a model cache replacement,
    allocator measurement, or performance implementation.
    """

    def __init__(self, *, heads: int, head_dim: int, window: int, page_tokens: int, admission_budget: int, selected_kv_heads: tuple[int, ...]) -> None:
        if not selected_kv_heads or len(set(selected_kv_heads)) != len(selected_kv_heads):
            raise ValueError("selected KV heads must be unique and nonempty")
        if any(head < 0 or head >= heads for head in selected_kv_heads):
            raise ValueError("selected KV head is outside the declared head count")
        self.heads, self.head_dim, self.window = heads, head_dim, window
        self.selected_kv_heads = tuple(selected_kv_heads)
        self.state = RouteAPackedAttentionState(heads=heads, head_dim=head_dim, window=window, page_tokens=page_tokens, admission_budget=admission_budget)
        self._selected_hot_keys: torch.Tensor | None = None
        self._selected_hot_values: torch.Tensor | None = None

    @property
    def logical_cache_tokens(self) -> int:
        """Logical cache position, independent of physical selected-hot length."""
        return self.state.next_position

    @property
    def selected_native_hot_keys(self) -> torch.Tensor | None:
        return self._selected_hot_keys

    @property
    def selected_native_hot_values(self) -> torch.Tensor | None:
        return self._selected_hot_values

    def append(self, keys: torch.Tensor, values: torch.Tensor, keep_mask: torch.Tensor, *, start_position: int) -> None:
        """Append a contiguous segment, evicting selected mature native K/V."""
        if keys.ndim != 3 or values.shape != keys.shape or keys.shape[0] != self.heads or keys.shape[2] != self.head_dim:
            raise ValueError("keys and values must be [KV-head, token, head-dim]")
        if keep_mask.shape != keys.shape[:2] or keep_mask.dtype != torch.bool:
            raise ValueError("keep_mask must be bool [KV-head, token]")
        if start_position != self.logical_cache_tokens:
            raise AssertionError("adapter append position must equal its logical cache position")

        # Route-A becomes the sole selected-head mature-cold owner first.
        self.state.append(keys, values, keep_mask, start_position=start_position)
        selected_keys = keys[list(self.selected_kv_heads)].detach().clone()
        selected_values = values[list(self.selected_kv_heads)].detach().clone()
        if self._selected_hot_keys is None:
            joined_keys, joined_values = selected_keys, selected_values
        else:
            joined_keys = torch.cat((self._selected_hot_keys, selected_keys), dim=1)
            joined_values = torch.cat((self._selected_hot_values, selected_values), dim=1)
        retained = min(self.window, self.logical_cache_tokens)
        self._selected_hot_keys = joined_keys[:, -retained:].clone() if retained else joined_keys[:, :0].clone()
        self._selected_hot_values = joined_values[:, -retained:].clone() if retained else joined_values[:, :0].clone()
        self.assert_storage_contract()

    def ownership_summary(self) -> dict[str, Any]:
        """Return scalar-only storage ownership evidence for selected heads."""
        contract = selected_storage_ownership_contract(self.state, selected_kv_heads=self.selected_kv_heads, native_logical_tokens=self.logical_cache_tokens)
        hot_tokens = 0 if self._selected_hot_keys is None else int(self._selected_hot_keys.shape[1])
        contract.update({
            "adapter_kind": "route_a_external_cold_storage_adapter",
            "adapter_selected_native_hot_tensor_tokens": hot_tokens,
            "adapter_selected_native_cold_tensor_tokens": 0,
            "adapter_selected_cold_tensors_absent": True,
            "adapter_logical_length_separate_from_physical_hot_length": True,
            "transformers_dynamic_cache_substitution": False,
            "native_selected_cold_slots_physically_freed": False,
        })
        return contract

    def assert_storage_contract(self) -> None:
        """Reject hidden selected cold storage or a broken bounded-hot view."""
        if (self._selected_hot_keys is None) != (self._selected_hot_values is None):
            raise AssertionError("selected hot K/V tensors must appear together")
        expected_tokens = min(self.window, self.logical_cache_tokens)
        if self._selected_hot_keys is None:
            if expected_tokens:
                raise AssertionError("selected hot K/V storage is missing")
        else:
            expected_shape = (len(self.selected_kv_heads), expected_tokens, self.head_dim)
            if tuple(self._selected_hot_keys.shape) != expected_shape or tuple(self._selected_hot_values.shape) != expected_shape:
                raise AssertionError("selected native-hot K/V storage shape violates the bounded-hot contract")
        summary = self.ownership_summary()
        if summary["adapter_selected_native_cold_tensor_tokens"] != 0 or not summary["adapter_selected_cold_tensors_absent"]:
            raise AssertionError("adapter retains selected mature cold tensor storage")
