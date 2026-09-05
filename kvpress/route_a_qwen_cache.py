"""A4.1.3.3 Qwen-compatible single-layer/head Route-A cache prototype.

The target layer persistently stores only unselected-head dense K/V.  Selected
head mature cold K/V belongs to the Route-A external adapter; selected hot K/V
is likewise owned there.  ``update`` returns a short-lived dense attention view
because current Qwen attention expects `[B,H,T,D]`; that view is not retained
by the cache and marks prior selected positions unreadable.  The policy-on
attention backend overwrites selected-head outputs from Route-A state.

This is a functional semantic prototype, not an allocator or performance
implementation.  It is deliberately restricted to batch one, layer zero, and
one selected KV head.
"""

from __future__ import annotations

from typing import Any

import torch
from transformers.cache_utils import Cache, CacheLayerMixin, DynamicLayer

from kvpress.route_a_external_cold_storage import RouteAExternalColdStorageAdapter


class RouteAQwenSelectedHeadCacheLayer(CacheLayerMixin):
    """Persistent unselected-head storage plus transient Qwen attention views."""

    is_sliding = False

    def __init__(self, *, selected_kv_head: int) -> None:
        super().__init__()
        self.selected_kv_head = selected_kv_head
        self.unselected_keys: torch.Tensor | None = None
        self.unselected_values: torch.Tensor | None = None
        self.logical_length = 0
        self.head_count: int | None = None
        self.head_dim: int | None = None
        self.batch_size: int | None = None
        self.dtype: torch.dtype | None = None
        self.device: torch.device | None = None
        self.transient_attention_view_count = 0

    def lazy_initialization(self, key_states: torch.Tensor) -> None:
        if key_states.ndim != 4 or key_states.shape[0] != 1:
            raise ValueError("Route-A Qwen cache prototype requires batch-one [B,H,T,D] K/V")
        if not 0 <= self.selected_kv_head < key_states.shape[1]:
            raise ValueError("selected KV head is outside cache K/V shape")
        self.batch_size, self.head_count, _tokens, self.head_dim = key_states.shape
        self.dtype, self.device = key_states.dtype, key_states.device
        unselected = [head for head in range(self.head_count) if head != self.selected_kv_head]
        self.unselected_keys = key_states[:, unselected, :0].detach().clone()
        self.unselected_values = key_states[:, unselected, :0].detach().clone()
        # CacheLayerMixin helpers expect ``keys``/``values``.  They expose only
        # the persistent unselected-head tensors, never a dense selected view.
        self.keys, self.values = self.unselected_keys, self.unselected_values
        self.is_initialized = True

    def _validate_new_states(self, key_states: torch.Tensor, value_states: torch.Tensor, cache_kwargs: dict[str, Any] | None) -> None:
        if key_states.ndim != 4 or value_states.shape != key_states.shape or key_states.shape[0] != 1:
            raise ValueError("Route-A Qwen cache prototype requires batch-one matching [B,H,T,D] K/V")
        if not self.is_initialized:
            self.lazy_initialization(key_states)
        if (key_states.shape[0], key_states.shape[1], key_states.shape[-1]) != (self.batch_size, self.head_count, self.head_dim):
            raise AssertionError("Qwen cache K/V shape changed after initialization")
        positions = None if cache_kwargs is None else cache_kwargs.get("cache_position")
        if positions is not None:
            positions = positions.detach().reshape(-1)
            expected = torch.arange(self.logical_length, self.logical_length + key_states.shape[-2], device=positions.device, dtype=positions.dtype)
            if not torch.equal(positions, expected):
                raise AssertionError("Qwen cache positions are not contiguous with Route-A logical length")

    def update(self, key_states: torch.Tensor, value_states: torch.Tensor, cache_kwargs: dict[str, Any] | None = None) -> tuple[torch.Tensor, torch.Tensor]:
        self._validate_new_states(key_states, value_states, cache_kwargs)
        if self.unselected_keys is None or self.unselected_values is None or self.head_count is None:
            raise AssertionError("Route-A Qwen cache layer failed initialization")
        old_length, new_tokens = self.logical_length, key_states.shape[-2]
        unselected = [head for head in range(self.head_count) if head != self.selected_kv_head]
        self.unselected_keys = torch.cat((self.unselected_keys, key_states[:, unselected].detach().clone()), dim=-2)
        self.unselected_values = torch.cat((self.unselected_values, value_states[:, unselected].detach().clone()), dim=-2)
        self.keys, self.values = self.unselected_keys, self.unselected_values
        self.logical_length += new_tokens

        # This full-shape object is an ephemeral Qwen attention input, not a
        # cache member.  Historic selected entries are unreadable; new selected
        # entries are available only so the current policy attention can append
        # them to Route-A state before computing its replacement output.
        attention_keys = torch.zeros((1, self.head_count, self.logical_length, self.head_dim), device=key_states.device, dtype=key_states.dtype)
        attention_values = torch.zeros_like(attention_keys)
        attention_keys[:, unselected] = self.unselected_keys
        attention_values[:, unselected] = self.unselected_values
        if old_length:
            attention_keys[:, self.selected_kv_head, :old_length].fill_(float("nan"))
            attention_values[:, self.selected_kv_head, :old_length].fill_(float("nan"))
        attention_keys[:, self.selected_kv_head, old_length:] = key_states[:, self.selected_kv_head]
        attention_values[:, self.selected_kv_head, old_length:] = value_states[:, self.selected_kv_head]
        self.transient_attention_view_count += 1
        return attention_keys, attention_values

    def get_mask_sizes(self, cache_position: torch.Tensor) -> tuple[int, int]:
        return self.logical_length + cache_position.shape[0], 0

    def get_seq_length(self) -> int:
        return self.logical_length

    def get_max_cache_shape(self) -> int:
        return -1

    def persistent_storage_summary(self, *, adapter: RouteAExternalColdStorageAdapter | None) -> dict[str, Any]:
        hot_tokens = 0 if adapter is None or adapter.selected_native_hot_keys is None else int(adapter.selected_native_hot_keys.shape[1])
        return {
            "cache_kind": "route_a_qwen_selected_head_external_cold_cache",
            "logical_cache_tokens": self.logical_length,
            "persistent_unselected_kv_heads": 0 if self.head_count is None else self.head_count - 1,
            "persistent_unselected_kv_tokens": 0 if self.unselected_keys is None else int(self.unselected_keys.shape[-2]),
            "persistent_selected_native_hot_tokens": hot_tokens,
            "persistent_selected_native_cold_tensor_tokens": 0,
            "persistent_selected_mature_cold_absent": True,
            "transient_attention_view_count": self.transient_attention_view_count,
            "transient_attention_view_is_not_persistent_cache": True,
        }


class RouteAQwenSingleLayerExternalColdCache(Cache):
    """Qwen Cache interface with one Route-A target layer/head and native others."""

    def __init__(self, *, target_layer: int, selected_kv_head: int) -> None:
        if target_layer != 0:
            raise ValueError("A4.1.3.3 prototype is intentionally restricted to target layer 0")
        super().__init__(layer_class_to_replicate=DynamicLayer)
        self.target_layer = target_layer
        self.selected_kv_head = selected_kv_head

    def _ensure_target_layer(self) -> RouteAQwenSelectedHeadCacheLayer:
        while len(self.layers) <= self.target_layer:
            self.layers.append(DynamicLayer())
        if not isinstance(self.layers[self.target_layer], RouteAQwenSelectedHeadCacheLayer):
            self.layers[self.target_layer] = RouteAQwenSelectedHeadCacheLayer(selected_kv_head=self.selected_kv_head)
        return self.layers[self.target_layer]

    def update(self, key_states: torch.Tensor, value_states: torch.Tensor, layer_idx: int, cache_kwargs: dict[str, Any] | None = None) -> tuple[torch.Tensor, torch.Tensor]:
        if layer_idx == self.target_layer:
            return self._ensure_target_layer().update(key_states, value_states, cache_kwargs)
        return super().update(key_states, value_states, layer_idx, cache_kwargs)

    def target_storage_summary(self, *, adapter: RouteAExternalColdStorageAdapter | None) -> dict[str, Any]:
        layer = self._ensure_target_layer()
        return layer.persistent_storage_summary(adapter=adapter)

    def assert_target_storage_contract(self, *, adapter: RouteAExternalColdStorageAdapter | None) -> None:
        if adapter is None:
            raise AssertionError("Route-A external adapter was not initialized")
        summary = self.target_storage_summary(adapter=adapter)
        if summary["logical_cache_tokens"] != adapter.logical_cache_tokens:
            raise AssertionError("Qwen cache logical length differs from Route-A external adapter")
        if summary["persistent_selected_native_cold_tensor_tokens"] != 0 or not summary["persistent_selected_mature_cold_absent"]:
            raise AssertionError("Qwen cache persistently retained selected mature cold K/V")
        if summary["persistent_selected_native_hot_tokens"] != min(adapter.window, adapter.logical_cache_tokens):
            raise AssertionError("Qwen cache selected hot ownership differs from Route-A adapter")
