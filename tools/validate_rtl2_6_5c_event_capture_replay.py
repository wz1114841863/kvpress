#!/usr/bin/env python3
"""Validate the RTL2.6.5c accepted-carrier capture/replay contract."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from kvpress.rtl2_6_5c_event_replay import load_manifest, validate_manifest, validate_source_hashes

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl2_6_5c_event_capture_replay_manifest.json"))
    parser.add_argument("--schema", type=Path, default=Path("analysis/rtl2_scoreboard_event_schema.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    validate_manifest(load_manifest(root / args.manifest), json.loads((root / args.schema).read_text(encoding="utf-8")))
    validate_source_hashes(load_manifest(root / args.manifest), root)
    print("RTL2.6.5c accepted-carrier capture/replay contract passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
