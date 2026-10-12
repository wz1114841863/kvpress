#!/usr/bin/env python3
"""Validate the RTL3.9-A R3 pending-pack-read activation manifest."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "analysis/rtl3_9_a_r3_pending_pack_read_activation_manifest.json", help="RTL3.9-A manifest to validate")
    manifest = json.loads(parser.parse_args().manifest.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kvzap-route-a-rtl3-9-a-r3-pending-pack-read-activation-1.0"
    assert manifest["status"] == "complete_functional_pending_to_p3_fill_activation"
    assert manifest["owners"]["materializer"] == "route_a_m2_p3_wrapper"
    assert manifest["activation"]["active_members_per_live_stage"] == 1
    assert manifest["activation"]["permanent_architecture_schedule"] is False
    assert manifest["disposition"]["p3_pack_read_work_top_tieoff_removed"] is True
    assert manifest["disposition"]["p3_packed_write_top_still_inert"] is True
    for relative, expected in manifest["source_sha256"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, f"hash mismatch: {relative}: {actual} != {expected}"
    print(f"PASS: RTL3.9-A pending-pack-read activation manifest verified ({len(manifest['source_sha256'])} hashes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
