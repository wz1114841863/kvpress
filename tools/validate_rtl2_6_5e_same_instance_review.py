#!/usr/bin/env python3
"""Validate RTL2.6.5e's testbench-only same-instance completion record."""
from __future__ import annotations
import argparse
from pathlib import Path
from kvpress.rtl2_6_5e_same_instance_review import load_and_validate

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl2_6_5e_same_instance_witness_manifest.json"))
    parser.add_argument("--capture", type=Path, default=Path("analysis/rtl2_6_5c_event_capture_replay_manifest.json"))
    parser.add_argument("--prior-review", type=Path, default=Path("analysis/rtl2_6_5d_completion_review.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_and_validate(root / args.manifest, root / args.capture, root / args.prior_review, root)
    print("RTL2.6.5e same-instance witness/re-review passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
