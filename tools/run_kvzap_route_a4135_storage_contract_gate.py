"""No-model A4.1.3.0 Route-A cold-storage ownership contract gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch

from kvpress.route_a_attention import RouteAPackedAttentionState
from kvpress.route_a_storage_contract import assert_storage_contract_state, selected_storage_ownership_contract
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A4135_SCHEMA = "kvzap-route-a4135-storage-ownership-contract-gate-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="No-model Route-A logical cold-storage ownership gate; no DynamicCache mutation, allocator, or timing claim.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window", type=int, default=2)
    parser.add_argument("--page-tokens", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def make_state(*, admission_budget: int, seed: int, window: int, page_tokens: int) -> RouteAPackedAttentionState:
    generator = torch.Generator().manual_seed(seed)
    state = RouteAPackedAttentionState(heads=2, head_dim=4, window=window, page_tokens=page_tokens, admission_budget=admission_budget)
    keys = torch.randn(2, 7, 4, generator=generator)
    values = torch.randn(2, 7, 4, generator=generator)
    keep = torch.tensor([[True, False, True, True, False, True, True], [False, True, True, False, True, True, False]])
    state.append(keys, values, keep, start_position=0)
    return state


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if min(args.window, args.page_tokens) <= 0:
        raise ValueError("window and page tokens must be positive")
    cases = {}
    for name, budget, requirements in (
        ("pending_budget_1", 1, {"require_pending": True}),
        ("packed_budget_512", 512, {"require_multi_page": True, "require_full_page": True, "require_tail": True}),
    ):
        state = make_state(admission_budget=budget, seed=args.seed, window=args.window, page_tokens=args.page_tokens)
        contract = selected_storage_ownership_contract(state)
        assert_storage_contract_state(contract, **requirements)
        cases[name] = {"admission_budget": budget, "contract": contract}
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    payload = {
        "schema_version": A4135_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "cases": cases,
        "boundaries": [
            "No-model logical ownership contract only; it does not mutate or truncate transformers DynamicCache.",
            "native_selected_cold_slots_physically_freed is false in every case; no allocator, HBM, latency, throughput, energy, hardware, or RTL claim.",
            "This validates the state-level precondition for a later cache adapter: selected native storage can retain the hot interval while Route-A owns mature cold reads and logical cache length remains unchanged.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a4135_storage_contract_manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.3.0 storage ownership contract gate passed: {path}")


if __name__ == "__main__":
    main()
