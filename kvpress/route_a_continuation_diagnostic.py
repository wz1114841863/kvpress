"""Small pure helpers for bounded Route-A continuation diagnostics."""

from __future__ import annotations

from typing import Any


def first_token_mismatch(reference: list[int], candidate: list[int]) -> dict[str, Any] | None:
    """Return the first bounded generated-token difference, if any."""
    for index, (left, right) in enumerate(zip(reference, candidate, strict=True)):
        if left != right:
            return {"generated_token_offset": index, "dense_token_id": left, "route_a_token_id": right}
    return None


def prefix_equal_before_step(reference: list[int], candidate: list[int], step: int) -> bool:
    """Whether both paths received equal generated-token inputs before a logit."""
    return reference[:step] == candidate[:step]
