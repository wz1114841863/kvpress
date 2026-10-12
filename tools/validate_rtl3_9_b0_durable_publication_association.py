#!/usr/bin/env python3
"""Validate the RTL3.9-B0 durable/publication association manifest."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "analysis/rtl3_9_b0_durable_publication_association_manifest.json", help="RTL3.9-B0 manifest to validate")
    manifest = json.loads(parser.parse_args().manifest.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kvzap-route-a-rtl3-9-b0-durable-publication-association-1.0"
    assert manifest["status"] == "complete_pre_activation_association_audit"
    assert manifest["association_key"] == ["layer", "stage_generation", "transaction_group_tag", "page_ref"]
    assert manifest["owners"]["top"] == "composition_only"
    assert not any(manifest["activation"].values())
    for relative, expected in manifest["source_sha256"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, f"hash mismatch: {relative}: {actual} != {expected}"
    print(f"PASS: RTL3.9-B0 durable/publication association manifest verified ({len(manifest['source_sha256'])} hashes)")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
