"""A4.0 functional Route-A packed-attention reference.

This is intentionally a small, policy-on *semantic* reference.  It owns no
model cache and does not install attention hooks.  A caller supplies K/V and
the already-decided original KVzap keep mask; the reference preserves that
mask while moving mature retained tokens through a pending FIFO into sealed,
append-only packed pages.  It is not an allocator, kernel, or timing model.
"""

from __future__ import annotations

import heapq
import hashlib
import struct
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

import torch


class RouteAPolicy(str, Enum):
    """The caller-visible request-start policy; no implicit length decision."""

    FULL_KV_BYPASS = "full_kv_bypass"
    ROUTE_A_FAST_PATH = "route_a_fast_path"


@dataclass
class _Record:
    position: int
    key: torch.Tensor
    value: torch.Tensor
    keep: bool = True


@dataclass
class _PackedPages:
    page_tokens: int
    keys: list[list[torch.Tensor]] = field(default_factory=list)
    values: list[list[torch.Tensor]] = field(default_factory=list)
    positions: list[list[int]] = field(default_factory=list)

    def append(self, record: _Record) -> None:
        if not self.keys or len(self.keys[-1]) == self.page_tokens:
            self.keys.append([]); self.values.append([]); self.positions.append([])
        self.keys[-1].append(record.key.clone())
        self.values[-1].append(record.value.clone())
        self.positions[-1].append(record.position)

    def records(self) -> list[_Record]:
        return [
            _Record(position, key, value)
            for page_k, page_v, page_p in zip(self.keys, self.values, self.positions, strict=True)
            for key, value, position in zip(page_k, page_v, page_p, strict=True)
        ]

    @property
    def logical_tokens(self) -> int:
        return sum(map(len, self.keys))

    @property
    def page_count(self) -> int:
        return len(self.keys)

    @property
    def full_page_count(self) -> int:
        """Number of immutable full pages; a full append-only page is sealed."""
        return sum(len(page) == self.page_tokens for page in self.keys)

    @property
    def tail_tokens(self) -> int:
        """Occupancy of the sole mutable tail page, or zero when absent/full."""
        if not self.keys or len(self.keys[-1]) == self.page_tokens:
            return 0
        return len(self.keys[-1])


def _attention(query: torch.Tensor, records: list[_Record]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return stable partial attention as ``(max_logit, exp_sum, weighted_v)``."""
    if query.ndim != 1:
        raise ValueError("query must be [head_dim]")
    if not records:
        empty = torch.zeros((), dtype=torch.float32, device=query.device)
        return torch.tensor(float("-inf"), dtype=torch.float32, device=query.device), empty, torch.zeros_like(query, dtype=torch.float32)
    keys = torch.stack([item.key for item in records]).to(device=query.device, dtype=torch.float32)
    values = torch.stack([item.value for item in records]).to(device=query.device, dtype=torch.float32)
    logits = keys @ query.to(dtype=torch.float32)
    maximum = logits.max()
    weights = torch.exp(logits - maximum)
    return maximum, weights.sum(), (weights[:, None] * values).sum(dim=0)


def online_softmax_merge(partials: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]) -> torch.Tensor:
    """Numerically stable merge of independently computed partial attentions."""
    nonempty = [item for item in partials if float(item[1]) > 0.0]
    if not nonempty:
        if not partials:
            raise ValueError("at least one partial is required")
        return torch.zeros_like(partials[0][2])
    maximum = torch.stack([item[0] for item in nonempty]).max()
    scales = [torch.exp(item[0] - maximum) for item in nonempty]
    denominator = sum(scale * item[1] for scale, item in zip(scales, nonempty, strict=True))
    numerator = sum((scale * item[2] for scale, item in zip(scales, nonempty, strict=True)))
    return numerator / denominator


def dense_same_mask_attention(query: torch.Tensor, records: list[_Record]) -> torch.Tensor:
    """Reference attention over the exact same retained records."""
    return online_softmax_merge([_attention(query, records)])


def policy_attention(
    policy: RouteAPolicy, query: torch.Tensor, *, state: "RouteAPackedAttentionState | None" = None,
    head: int = 0, full_kv_records: list[_Record] | None = None,
) -> torch.Tensor:
    """Select the explicit bypass or Route-A data path without hidden fallback.

    ``FULL_KV_BYPASS`` neither reads nor evolves Route-A state.  The caller must
    supply its regular Full-KV records.  ``ROUTE_A_FAST_PATH`` reads only the
    packed/pending/hot stores exposed by ``state``.
    """
    if policy is RouteAPolicy.FULL_KV_BYPASS:
        if full_kv_records is None:
            raise ValueError("Full-KV bypass requires explicit full_kv_records")
        return dense_same_mask_attention(query, full_kv_records)
    if policy is RouteAPolicy.ROUTE_A_FAST_PATH:
        if state is None:
            raise ValueError("Route-A fast path requires Route-A state")
        return state.attention(query, head=head)
    raise ValueError(f"unsupported Route-A policy: {policy}")


class RouteAPackedAttentionState:
    """One layer's exact-mask Route-A state for a small functional harness.

    The admission budget is shared across KV heads and drains globally oldest
    pending positions first.  The caller may use a distinct instance per layer.
    """

    def __init__(self, *, heads: int, head_dim: int, window: int, page_tokens: int, admission_budget: int) -> None:
        if min(heads, head_dim, page_tokens, admission_budget) <= 0 or window < 0:
            raise ValueError("invalid Route-A reference dimensions")
        self.heads, self.head_dim, self.window = heads, head_dim, window
        self.admission_budget = admission_budget
        self._hot: list[deque[_Record]] = [deque() for _ in range(heads)]
        self._pending: list[deque[_Record]] = [deque() for _ in range(heads)]
        self._pages = [_PackedPages(page_tokens) for _ in range(heads)]
        self._next_position = 0
        self._decided_kept: list[list[int]] = [[] for _ in range(heads)]
        self._decided_dropped: list[list[int]] = [[] for _ in range(heads)]
        self._mask_digest = hashlib.sha256()
        self._mask_count = 0

    def _record_mask_decision(self, *, head: int, position: int, keep: bool) -> None:
        """Hash every original predictor decision, including protected-hot ones."""
        self._mask_digest.update(struct.pack("<II?", head, position, keep))
        self._mask_count += 1

    def mask_summary(self) -> dict[str, int | str]:
        return {"original_mask_sha256": self._mask_digest.hexdigest(), "original_mask_decision_count": self._mask_count}

    @property
    def next_position(self) -> int:
        """Exclusive next cache position, exposed for ownership guards."""
        return self._next_position

    def append(self, keys: torch.Tensor, values: torch.Tensor, keep_mask: torch.Tensor, *, start_position: int, component_measure=None) -> None:
        """Append contiguous [KV-head, token, head-dim] K/V under the original mask."""
        if keys.ndim != 3 or values.shape != keys.shape or keys.shape[:1] != (self.heads,) or keys.shape[2] != self.head_dim:
            raise ValueError("keys and values must be [KV-head, token, head-dim]")
        if keep_mask.shape != keys.shape[:2] or keep_mask.dtype != torch.bool:
            raise ValueError("keep_mask must be bool [KV-head, token]")
        if start_position != self._next_position:
            raise AssertionError(f"non-contiguous position: expected {self._next_position}, got {start_position}")
        def mature_to_pending() -> None:
            for offset in range(keys.shape[1]):
                position = start_position + offset
                for head in range(self.heads):
                    record = _Record(position, keys[head, offset].detach().clone(), values[head, offset].detach().clone(), bool(keep_mask[head, offset]))
                    self._record_mask_decision(head=head, position=position, keep=record.keep)
                    self._hot[head].append(record)
                    if len(self._hot[head]) > self.window:
                        mature = self._hot[head].popleft()
                        if mature.keep:
                            self._pending[head].append(mature)
                            self._decided_kept[head].append(mature.position)
                        else:
                            self._decided_dropped[head].append(mature.position)
            self._next_position += keys.shape[1]

        def measure(name, operation):
            return operation() if component_measure is None else component_measure(name, operation)

        measure("route_a_maturity_pending_staging", mature_to_pending)
        measure("route_a_admission_page_append_table", self._service_oldest_first)
        self.assert_conservation()

    def _service_oldest_first(self) -> None:
        queue: list[tuple[int, int]] = [(items[0].position, head) for head, items in enumerate(self._pending) if items]
        heapq.heapify(queue)
        for _ in range(self.admission_budget):
            if not queue:
                break
            _position, head = heapq.heappop(queue)
            self._pages[head].append(self._pending[head].popleft())
            if self._pending[head]:
                heapq.heappush(queue, (self._pending[head][0].position, head))

    def records(self, head: int) -> dict[str, list[_Record]]:
        if not 0 <= head < self.heads:
            raise ValueError("invalid KV head")
        return {"hot": list(self._hot[head]), "pending": list(self._pending[head]), "packed": self._pages[head].records()}

    def attention(self, query: torch.Tensor, *, head: int, component_measure=None) -> torch.Tensor:
        sources = self.records(head)
        def measure(name, operation):
            return operation() if component_measure is None else component_measure(name, operation)
        partials = [measure(f"route_a_attention_{name}", lambda name=name: _attention(query, sources[name])) for name in ("hot", "pending", "packed")]
        return measure("route_a_online_softmax_merge", lambda: online_softmax_merge(partials))

    def same_mask_records(self, head: int) -> list[_Record]:
        sources = self.records(head)
        return sources["hot"] + sources["pending"] + sources["packed"]

    def state_summary(self, head: int) -> dict[str, int]:
        sources = self.records(head)
        pages = self._pages[head]
        return {
            "hot_tokens": len(sources["hot"]),
            "pending_tokens": len(sources["pending"]),
            "packed_tokens": len(sources["packed"]),
            "packed_page_count": pages.page_count,
            "packed_full_page_count": pages.full_page_count,
            "packed_tail_tokens": pages.tail_tokens,
        }

    def assert_conservation(self) -> None:
        for head in range(self.heads):
            sources = self.records(head)
            positions = [item.position for name in ("hot", "pending", "packed") for item in sources[name]]
            if len(positions) != len(set(positions)):
                raise AssertionError("a retained/hot token appears in more than one Route-A store")
            if any(record.position >= self._next_position - self.window for record in sources["pending"] + sources["packed"]):
                raise AssertionError("hot-window token entered pending or packed cold state")
            decided = set(self._decided_kept[head]) | set(self._decided_dropped[head])
            matured = set(range(max(0, self._next_position - self.window)))
            if decided != matured:
                raise AssertionError("matured positions are not exactly partitioned by the original mask")


class DenseSameMaskAttentionState:
    """Functional dense KVzap state with the same mask and hot-window contract.

    Mature retained entries append directly to one dense cold list per KV head.
    It deliberately has no Route-A pending FIFO, admission service, or packed
    pages, so it is an independent same-mask dense control rather than a view
    of a Route-A state.
    """

    def __init__(self, *, heads: int, head_dim: int, window: int) -> None:
        if min(heads, head_dim) <= 0 or window < 0:
            raise ValueError("invalid same-mask dense reference dimensions")
        self.heads, self.head_dim, self.window = heads, head_dim, window
        self._hot: list[deque[_Record]] = [deque() for _ in range(heads)]
        self._cold: list[list[_Record]] = [[] for _ in range(heads)]
        self._next_position = 0
        self._decided_kept: list[list[int]] = [[] for _ in range(heads)]
        self._decided_dropped: list[list[int]] = [[] for _ in range(heads)]
        self._mask_digest = hashlib.sha256()
        self._mask_count = 0

    def _record_mask_decision(self, *, head: int, position: int, keep: bool) -> None:
        self._mask_digest.update(struct.pack("<II?", head, position, keep))
        self._mask_count += 1

    def mask_summary(self) -> dict[str, int | str]:
        return {"original_mask_sha256": self._mask_digest.hexdigest(), "original_mask_decision_count": self._mask_count}

    @property
    def next_position(self) -> int:
        """Exclusive next cache position, used by multi-token control gates."""
        return self._next_position

    def append(self, keys: torch.Tensor, values: torch.Tensor, keep_mask: torch.Tensor, *, start_position: int, component_measure=None) -> None:
        if keys.ndim != 3 or values.shape != keys.shape or keys.shape[:1] != (self.heads,) or keys.shape[2] != self.head_dim:
            raise ValueError("keys and values must be [KV-head, token, head-dim]")
        if keep_mask.shape != keys.shape[:2] or keep_mask.dtype != torch.bool:
            raise ValueError("keep_mask must be bool [KV-head, token]")
        if start_position != self._next_position:
            raise AssertionError(f"non-contiguous position: expected {self._next_position}, got {start_position}")
        def mature_to_dense_cold() -> None:
            for offset in range(keys.shape[1]):
                position = start_position + offset
                for head in range(self.heads):
                    record = _Record(position, keys[head, offset].detach().clone(), values[head, offset].detach().clone(), bool(keep_mask[head, offset]))
                    self._record_mask_decision(head=head, position=position, keep=record.keep)
                    self._hot[head].append(record)
                    if len(self._hot[head]) > self.window:
                        mature = self._hot[head].popleft()
                        if mature.keep:
                            self._cold[head].append(mature)
                            self._decided_kept[head].append(mature.position)
                        else:
                            self._decided_dropped[head].append(mature.position)
            self._next_position += keys.shape[1]

        if component_measure is None:
            mature_to_dense_cold()
        else:
            component_measure("dense_maturity_dense_cold_append", mature_to_dense_cold)
        self.assert_conservation()

    def records(self, head: int) -> dict[str, list[_Record]]:
        if not 0 <= head < self.heads:
            raise ValueError("invalid KV head")
        return {"hot": list(self._hot[head]), "dense_cold": list(self._cold[head])}

    def same_mask_records(self, head: int) -> list[_Record]:
        sources = self.records(head)
        return sources["hot"] + sources["dense_cold"]

    def attention(self, query: torch.Tensor, *, head: int, component_measure=None) -> torch.Tensor:
        operation = lambda: dense_same_mask_attention(query, self.same_mask_records(head))
        return operation() if component_measure is None else component_measure("dense_same_mask_attention", operation)

    def state_summary(self, head: int) -> dict[str, int]:
        sources = self.records(head)
        return {"hot_tokens": len(sources["hot"]), "dense_cold_tokens": len(sources["dense_cold"])}

    def assert_conservation(self) -> None:
        for head in range(self.heads):
            sources = self.records(head)
            positions = [item.position for name in ("hot", "dense_cold") for item in sources[name]]
            if len(positions) != len(set(positions)):
                raise AssertionError("a retained/hot token appears in more than one same-mask dense store")
            if any(record.position >= self._next_position - self.window for record in sources["dense_cold"]):
                raise AssertionError("hot-window token entered dense cold state")
            decided = set(self._decided_kept[head]) | set(self._decided_dropped[head])
            matured = set(range(max(0, self._next_position - self.window)))
            if decided != matured:
                raise AssertionError("matured positions are not exactly partitioned by the original mask")
