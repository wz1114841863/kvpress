#!/usr/bin/env python3
"""Validate the RTL3.9-B2 descriptor-durability activation manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "analysis/rtl3_9_b2_descriptor_durability_activation_manifest.json",
        help="RTL3.9-B2 manifest to validate",
    )
    manifest = json.loads(parser.parse_args().manifest.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kvzap-route-a-rtl3-9-b2-descriptor-durability-activation-1.0"
    assert manifest["status"] == "complete_functional_descriptor_durability_activation"
    assert manifest["owners"]["top"] == "composition_only"
    assert manifest["activation"]["r3_materializer_feedback"] is True
    assert manifest["activation"]["typed_r5_append_terminal"] is True
    assert manifest["activation"]["legacy_direct_descriptor_terminal_active"] is False
    assert manifest["disposition"]["metadata_publication_or_authority_activated"] is False
    for relative, expected in manifest["source_sha256"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, f"hash mismatch: {relative}: {actual} != {expected}"
    print(f"PASS: RTL3.9-B2 descriptor-durability activation manifest verified ({len(manifest['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
