"""Bounded activation-difference summaries for untimed Route-A diagnostics."""

from __future__ import annotations

from typing import Any

import torch


def summarize_activation_relation(dense: torch.Tensor, route: torch.Tensor) -> dict[str, Any]:
    """Summarize one [batch, token, hidden] pair without serializing tensors."""
    if dense.shape != route.shape or dense.ndim != 3:
        raise ValueError(f"activation tensors must have equal [B,T,H] shape, got {tuple(dense.shape)} and {tuple(route.shape)}")
    dense = dense.detach().float()
    route = route.detach().float()
    finite = bool(torch.isfinite(dense).all().item() and torch.isfinite(route).all().item())
    summary: dict[str, Any] = {"shape": list(dense.shape), "both_all_finite": finite}
    if not finite:
        summary.update({"max_abs_difference": None, "mean_abs_difference": None, "relative_l2_difference": None, "maximum": None, "per_question_token": None})
        return summary
    difference = (dense - route).abs()
    maximum, flat_index = difference.reshape(-1).max(dim=0)
    batch_size, token_count, hidden_size = dense.shape
    flat = int(flat_index.item())
    batch = flat // (token_count * hidden_size)
    remaining = flat % (token_count * hidden_size)
    token = remaining // hidden_size
    hidden = remaining % hidden_size
    dense_norm = torch.linalg.vector_norm(dense)
    relative_l2 = torch.linalg.vector_norm(dense - route) / dense_norm if float(dense_norm) != 0.0 else torch.linalg.vector_norm(dense - route)
    per_token = []
    for index in range(token_count):
        dense_token = dense[:, index]
        route_token = route[:, index]
        delta = (dense_token - route_token).abs()
        token_norm = torch.linalg.vector_norm(dense_token)
        token_relative_l2 = torch.linalg.vector_norm(dense_token - route_token) / token_norm if float(token_norm) != 0.0 else torch.linalg.vector_norm(dense_token - route_token)
        per_token.append({
            "question_token_offset": index,
            "max_abs_difference": float(delta.max().item()),
            "mean_abs_difference": float(delta.mean().item()),
            "relative_l2_difference": float(token_relative_l2.item()),
        })
    summary.update({
        "max_abs_difference": float(maximum.item()),
        "mean_abs_difference": float(difference.mean().item()),
        "relative_l2_difference": float(relative_l2.item()),
        "maximum": {
            "batch": batch,
            "question_token_offset": token,
            "hidden_index": hidden,
            "dense_value": float(dense[batch, token, hidden].item()),
            "route_a_value": float(route[batch, token, hidden].item()),
        },
        "per_question_token": per_token,
    })
    return summary


def summarize_layer_activation_relations(dense_layers: dict[int, torch.Tensor], route_layers: dict[int, torch.Tensor]) -> dict[str, Any]:
    """Compare every captured layer and locate the first non-bitwise-equal one."""
    if set(dense_layers) != set(route_layers):
        raise ValueError(f"paired layer capture sets differ: dense={sorted(dense_layers)}, route={sorted(route_layers)}")
    layers = []
    for layer in sorted(dense_layers):
        summary = summarize_activation_relation(dense_layers[layer], route_layers[layer])
        summary["layer"] = layer
        layers.append(summary)
    first_difference = next((row["layer"] for row in layers if row["max_abs_difference"] not in (None, 0.0)), None)
    return {"layers": layers, "first_layer_with_nonzero_difference": first_difference}
