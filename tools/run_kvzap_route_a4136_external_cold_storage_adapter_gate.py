"""No-model A4.1.3.1 external selected-head cold-storage adapter gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch

from kvpress.route_a_attention import dense_same_mask_attention
from kvpress.route_a_external_cold_storage import RouteAExternalColdStorageAdapter
from kvpress.route_a_storage_contract import assert_storage_contract_state
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A4136_SCHEMA = "kvzap-route-a4136-external-cold-storage-adapter-gate-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="No-model Route-A external selected-head cold-storage adapter gate; no DynamicCache substitution or measurement claim.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window", type=int, default=2)
    parser.add_argument("--page-tokens", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def inputs(*, seed: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    generator = torch.Generator().manual_seed(seed)
    keys = torch.randn(2, 7, 4, generator=generator)
    values = torch.randn(2, 7, 4, generator=generator)
    keep = torch.tensor([[True, False, True, True, False, True, True], [False, True, True, False, True, True, False]])
    query = torch.randn(4, generator=generator)
    return keys, values, keep, query


def run_case(*, budget: int, seed: int, window: int, page_tokens: int) -> dict[str, object]:
    keys, values, keep, query = inputs(seed=seed)
    adapter = RouteAExternalColdStorageAdapter(heads=2, head_dim=4, window=window, page_tokens=page_tokens, admission_budget=budget, selected_kv_heads=(1,))
    # Two segments prove hot eviction survives separate appends.
    adapter.append(keys[:, :4], values[:, :4], keep[:, :4], start_position=0)
    adapter.append(keys[:, 4:], values[:, 4:], keep[:, 4:], start_position=4)
    adapter.assert_storage_contract()
    summary = adapter.ownership_summary()
    route = adapter.state.attention(query, head=1)
    dense = dense_same_mask_attention(query, adapter.state.same_mask_records(1))
    torch.testing.assert_close(route, dense, rtol=1e-6, atol=1e-6)
    return {
        "admission_budget": budget,
        "selected_kv_head": 1,
        "storage_contract": summary,
        "same_mask_attention_max_abs_difference": float((route - dense).abs().max().item()),
        "selected_native_hot_shape": list(adapter.selected_native_hot_keys.shape) if adapter.selected_native_hot_keys is not None else None,
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if min(args.window, args.page_tokens) <= 0:
        raise ValueError("window and page tokens must be positive")
    pending = run_case(budget=1, seed=args.seed, window=args.window, page_tokens=args.page_tokens)
    packed = run_case(budget=512, seed=args.seed, window=args.window, page_tokens=args.page_tokens)
    assert_storage_contract_state(pending["storage_contract"], require_pending=True)  # type: ignore[arg-type]
    assert_storage_contract_state(packed["storage_contract"], require_multi_page=True, require_full_page=True, require_tail=True)  # type: ignore[arg-type]
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    payload = {
        "schema_version": A4136_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "cases": {"pending_budget_1": pending, "packed_budget_512": packed},
        "boundaries": [
            "No-model external adapter gate only. It is not a transformers DynamicCache replacement and is not attached to a model.",
            "The adapter physically materializes only selected-head hot K/V; mature retained K/V are in Route-A pending/packed state and mature dropped K/V are absent from the adapter.",
            "native_selected_cold_slots_physically_freed remains false because native DynamicCache is untouched. No allocator, HBM, latency, throughput, energy, hardware, or RTL claim follows.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a4136_external_cold_storage_adapter_manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.3.1 external cold-storage adapter gate passed: {path}")


if __name__ == "__main__":
    main()
