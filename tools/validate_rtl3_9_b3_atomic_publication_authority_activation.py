#!/usr/bin/env python3
"""Validate the RTL3.9-B3 atomic-publication authority-activation manifest."""
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
        default=ROOT / "analysis/rtl3_9_b3_atomic_publication_authority_activation_manifest.json",
        help="RTL3.9-B3 manifest to validate",
    )
    manifest = json.loads(parser.parse_args().manifest.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kvzap-route-a-rtl3-9-b3-atomic-publication-authority-activation-1.0"
    assert manifest["status"] == "complete_functional_atomic_publication_authority_closure"
    assert manifest["owners"]["r3"] == "sole_publication_and_authority_transition_owner"
    assert manifest["owners"]["r5"] == "sole_visibility_ack_owner"
    assert manifest["owners"]["r6"] == "publication_observer_and_authority_acceptor_only"
    assert manifest["activation"]["r3_m2_provider_round_trip"] is True
    assert manifest["activation"]["r5_visibility_ack"] is True
    assert manifest["activation"]["r6_pending_to_packed_acceptance"] is True
    assert manifest["activation"]["legacy_duplicate_publication_ack_connection"] is False
    assert manifest["disposition"]["physical_memory_or_ppa_claim"] is False
    assert manifest["disposition"]["numeric_or_model_gpu_claim"] is False
    for relative, expected in manifest["source_sha256"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, f"hash mismatch: {relative}: {actual} != {expected}"
    print(f"PASS: RTL3.9-B3 atomic-publication authority manifest verified ({len(manifest['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
