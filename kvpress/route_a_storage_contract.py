"""Logical cold-storage ownership contract for the next Route-A cache adapter.

This module intentionally does not mutate ``DynamicCache``.  It proves the
state-level precondition for a future adapter: once selected attention owns
all mature cold reads, native selected-head storage may retain only the recent
hot interval while its *logical* cache length remains unchanged.
"""

from __future__ import annotations

from typing import Any

from kvpress.route_a_attention import RouteAPackedAttentionState


def selected_storage_ownership_contract(
    state: RouteAPackedAttentionState,
    *,
    selected_kv_heads: tuple[int, ...] | None = None,
    native_logical_tokens: int | None = None,
) -> dict[str, Any]:
    """Return and verify a scalar-only release contract for selected KV heads.

    Mature positions are no longer required by selected native attention:
    retained positions are represented by pending/packed Route-A storage and
    dropped positions are intentionally absent.  The hot interval remains in
    native storage so its logical cache length stays ``state.next_position``.
    """
    state.assert_conservation()
    logical_tokens = state.next_position if native_logical_tokens is None else native_logical_tokens
    if logical_tokens != state.next_position:
        raise AssertionError(
            "native logical cache length must equal Route-A next_position: "
            f"native={logical_tokens}, route_a={state.next_position}"
        )
    heads = tuple(range(state.heads)) if selected_kv_heads is None else selected_kv_heads
    if not heads or len(set(heads)) != len(heads) or any(not 0 <= head < state.heads for head in heads):
        raise ValueError("selected KV heads must be unique valid nonempty indices")
    cold_end = max(0, state.next_position - state.window)
    hot_expected = set(range(cold_end, state.next_position))
    cold_expected = set(range(cold_end))
    rows: list[dict[str, Any]] = []
    for head in heads:
        sources = state.records(head)
        hot = {record.position for record in sources["hot"]}
        pending = {record.position for record in sources["pending"]}
        packed = {record.position for record in sources["packed"]}
        if hot != hot_expected:
            raise AssertionError(f"head {head} hot positions do not cover exactly the native-retained hot interval")
        if pending & packed or (pending | packed) & hot:
            raise AssertionError(f"head {head} Route-A storage overlaps hot/pending/packed ownership")
        retained_cold = pending | packed
        if not retained_cold <= cold_expected:
            raise AssertionError(f"head {head} cold retained position is outside the mature interval")
        dropped_cold = cold_expected - retained_cold
        if retained_cold | dropped_cold != cold_expected:
            raise AssertionError(f"head {head} mature interval is not partitioned by retained/drop ownership")
        state_summary = state.state_summary(head)
        rows.append(
            {
                "kv_head": head,
                "logical_cache_tokens": logical_tokens,
                "native_hot_tokens_required": len(hot_expected),
                "native_mature_cold_tokens_releasable": len(cold_expected),
                "route_a_pending_tokens": len(pending),
                "route_a_packed_tokens": len(packed),
                "route_a_retained_cold_tokens": len(retained_cold),
                "route_a_dropped_mature_tokens": len(dropped_cold),
                "packed_page_count": state_summary["packed_page_count"],
                "packed_full_page_count": state_summary["packed_full_page_count"],
                "packed_tail_tokens": state_summary["packed_tail_tokens"],
                "logical_length_preserved": logical_tokens == state.next_position,
                "native_selected_cold_slots_physically_freed": False,
            }
        )
    return {
        "logical_cache_tokens": logical_tokens,
        "selected_kv_heads": list(heads),
        "selected_attention_owns_mature_cold": True,
        "native_selected_cold_slots_physically_freed": False,
        "heads": rows,
    }


def assert_storage_contract_state(
    contract: dict[str, Any],
    *,
    require_pending: bool = False,
    require_multi_page: bool = False,
    require_full_page: bool = False,
    require_tail: bool = False,
) -> None:
    """Apply explicit aggregate state requirements without inventing a layout."""
    rows = contract["heads"]
    if not contract["selected_attention_owns_mature_cold"]:
        raise AssertionError("selected attention has not claimed mature cold ownership")
    if any(not row["logical_length_preserved"] for row in rows):
        raise AssertionError("cache logical length was not preserved")
    requirements = (
        (require_pending, "route_a_pending_tokens", "pending staging"),
        (require_multi_page, "packed_page_count", "multi-page packed state"),
        (require_full_page, "packed_full_page_count", "sealed full packed page"),
        (require_tail, "packed_tail_tokens", "packed tail"),
    )
    for required, field, label in requirements:
        minimum = 2 if field == "packed_page_count" else 1
        if required and not any(int(row[field]) >= minimum for row in rows):
            raise AssertionError(f"required {label} was not observed")
