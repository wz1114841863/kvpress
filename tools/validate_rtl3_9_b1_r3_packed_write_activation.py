#!/usr/bin/env python3
"""Validate the RTL3.9-B1 R3 packed-write activation manifest."""
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
        default=ROOT / "analysis/rtl3_9_b1_r3_packed_write_activation_manifest.json",
        help="RTL3.9-B1 manifest to validate",
    )
    manifest = json.loads(parser.parse_args().manifest.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kvzap-route-a-rtl3-9-b1-r3-packed-write-activation-1.0"
    assert manifest["status"] == "complete_functional_p3_packed_write_activation"
    assert manifest["owners"]["top"] == "composition_only"
    assert manifest["activation"]["candidate_path_reachable_after_rtl3_9_a"] is True
    assert manifest["activation"]["legacy_direct_issue_terminal_carriers_active"] is False
    assert manifest["activation"]["payload_durable_is_publication_or_authority"] is False
    for relative, expected in manifest["source_sha256"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, f"hash mismatch: {relative}: {actual} != {expected}"
    print(f"PASS: RTL3.9-B1 R3 packed-write activation manifest verified ({len(manifest['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
