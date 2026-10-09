#!/usr/bin/env python3
"""Validate the hash-bound RTL3.5-B functional partial-provider manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(manifest_path: Path, repository_root: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "implemented_pure_software_functional_partial_provider_pre_numeric_rtl":
        raise ValueError("RTL3.5-B manifest has an unexpected status")
    if manifest["partial_owner"] != "route_a_functional_attention_partial_provider":
        raise ValueError("RTL3.5-B partial owner is not unique")
    if manifest["existing_output_carriers"] != ["SourceServicePartialOffer", "SourceServiceValueFragment"]:
        raise ValueError("RTL3.5-B output carrier mapping differs from the frozen boundary")
    if manifest["input_profiles"] != {
        "rope": "qwen3_rope_applied_at_q_and_k_creation_v1",
        "attention": "qwen3_gqa_scaled_causal_attention_v1",
    }:
        raise ValueError("RTL3.5-B input profiles differ from RTL3.5-A")
    if manifest["forbidden"] != [
        "Chisel_attention_MAC_or_RoPE_RTL",
        "production_top_activation",
        "source_owner_partial_computation",
        "scheduler_or_authority_change",
        "timing_throughput_or_PPA_claim",
        "new_A4_DSE",
    ]:
        raise ValueError("RTL3.5-B forbidden boundary differs from the approved scope")
    for relative_path, expected in manifest["source_sha256"].items():
        actual = _sha256(repository_root / relative_path)
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("analysis/rtl3_5b_functional_attention_partial_provider_manifest.json"),
        help="hash-bound RTL3.5-B manifest path",
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."), help="repository root containing source paths")
    args = parser.parse_args()
    validate(args.manifest, args.repository_root)
    print("PASS: RTL3.5-B functional partial-provider manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
