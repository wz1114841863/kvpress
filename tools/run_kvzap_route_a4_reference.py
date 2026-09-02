"""Run a deterministic, no-model A4.0 packed-attention semantic gate."""

from __future__ import annotations

import argparse

import torch

from kvpress.route_a_attention import RouteAPackedAttentionState, RouteAPolicy, dense_same_mask_attention


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="No-model A4.0 Route-A packed-attention semantic harness; no timing or hardware claim.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window", type=int, default=2)
    parser.add_argument("--page-tokens", type=int, default=2)
    parser.add_argument("--admission-budget", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    state = RouteAPackedAttentionState(heads=1, head_dim=4, window=args.window, page_tokens=args.page_tokens, admission_budget=args.admission_budget)
    keys, values = torch.randn(1, 6, 4), torch.randn(1, 6, 4)
    keep = torch.tensor([[True, False, True, True, False, True]])
    state.append(keys, values, keep, start_position=0)
    query = torch.randn(4)
    packed = state.attention(query, head=0)
    dense = dense_same_mask_attention(query, state.same_mask_records(0))
    torch.testing.assert_close(packed, dense, rtol=1e-5, atol=1e-6)
    print({"schema_version": "kvzap-route-a40-packed-attention-reference-1.0", "policy": RouteAPolicy.ROUTE_A_FAST_PATH.value, "state": state.state_summary(0), "same_mask_attention_matches": True, "measurement": "none"})


if __name__ == "__main__":
    main()
