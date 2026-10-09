#!/usr/bin/env python3
"""Validate the RTL3.3 R4 functional-profile/oracle provenance manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_3_r4_functional_profile_manifest.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / args.manifest).read_text())
    assert manifest["status"] == "complete_functional_profile_oracle_binding_pre_rtl3_4"
    assert manifest["future_provider_owner"] == "route_a_functional_r4_merge_provider"
    assert manifest["activation"] == "deferred_to_rtl3_4"
    profile = manifest["profile"]
    assert profile["canonical_source_order"] == ["hot", "pending", "packed"]
    assert profile["source_ordinals"] == {"hot": 0, "pending": 1, "packed": 2}
    assert profile["normalized_value"] == {
        "width_bits": 4096,
        "lanes": 128,
        "lane_bits": 32,
        "packing": "lane i little-endian binary32 at bits [32*i+31:32*i]",
    }
    assert profile["fixture_header_word"] == "0x0000000000000228402000003fa00000"
    for relative, expected in manifest["source_sha256"].items():
        actual = _sha256(root / relative)
        assert actual == expected, f"SHA-256 mismatch for {relative}: {actual} != {expected}"
    print("RTL3.3 R4 functional-profile/oracle provenance passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
