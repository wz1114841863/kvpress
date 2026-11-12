"""Run a deterministic, no-model A4.0 packed-attention semantic gate."""

from __future__ import annotations

import argparse

from kvpress.research.route_a import RouteAPackedAttentionState, RouteAPolicy, dense_same_mask_attention, run_reference


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="No-model A4.0 Route-A packed-attention semantic harness; no timing or hardware claim.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window", type=int, default=2)
    parser.add_argument("--page-tokens", type=int, default=2)
    parser.add_argument("--admission-budget", type=int, default=1)
    return parser.parse_args()




def main() -> None:
    args = parse_args()
    print(run_reference(seed=args.seed, window=args.window, page_tokens=args.page_tokens, admission_budget=args.admission_budget))


if __name__ == "__main__":
    main()
