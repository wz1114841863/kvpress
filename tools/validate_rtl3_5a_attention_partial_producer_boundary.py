#!/usr/bin/env python3
"""Validate the hash-bound RTL3.5-A partial-producer boundary manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_SOURCE_KINDS = ["hot", "pending", "packed"]
REQUIRED_OWNERS = {
    "query_context": "common_frontend_attention_context_provider",
    "partial_producer": "route_a_functional_attention_partial_provider",
    "hot": "route_a_hot_source_path",
    "pending": "route_a_direct_pending_endpoint_v1",
    "packed": "route_a_s2_gqa_source_wrapper",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(manifest_path: Path, repository_root: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "complete_interface_owner_freeze_pre_functional_partial_provider":
        raise ValueError("RTL3.5-A manifest status is not the frozen boundary status")
    if manifest["canonical_source_order"] != REQUIRED_SOURCE_KINDS:
        raise ValueError("RTL3.5-A source order must remain hot/pending/packed")
    if manifest["owners"] != REQUIRED_OWNERS:
        raise ValueError("RTL3.5-A owner map differs from the frozen unique-owner map")
    association = manifest["qwen_anchor_association"]
    if association["query_heads_per_kv_head_group"] != 4:
        raise ValueError("Qwen anchor must retain four query heads per KV group")
    if association["query_head_mapping"] != "query_head = 4 * kv_head + consumer_id":
        raise ValueError("Qwen anchor query-head mapping differs from the frozen rule")
    rope = manifest["rope_and_position_semantics"]
    if rope["query_rope_state"] != "already_applied_by_common_frontend":
        raise ValueError("partial producer must not own query RoPE application")
    if rope["key_rope_state"] != "already_applied_at_kv_creation":
        raise ValueError("partial producer must not re-apply key RoPE")
    if manifest["partial_packet_producer"] != "route_a_functional_attention_partial_provider":
        raise ValueError("partial packet producer is not unique")
    prohibited = set(manifest["forbidden"])
    required_prohibited = {
        "storage_owner_attention_partial_computation",
        "production_top_activation",
        "attention_mac_or_rope_rtl",
        "physical_performance_or_ppa_claim",
    }
    if not required_prohibited <= prohibited:
        raise ValueError("RTL3.5-A forbidden boundary is incomplete")
    for relative_path, expected in manifest["source_sha256"].items():
        actual = _sha256(repository_root / relative_path)
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("analysis/rtl3_5a_attention_partial_producer_boundary_manifest.json"),
        help="hash-bound RTL3.5-A manifest path",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path("."),
        help="repository root containing manifest source paths",
    )
    args = parser.parse_args()
    validate(args.manifest, args.repository_root)
    print("PASS: RTL3.5-A partial-producer boundary manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
