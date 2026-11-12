#!/usr/bin/env python3
"""Validate the RTL3.8.3 source/partial boundary record."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("analysis/rtl3_8_3_source_partial_boundary_isolation_manifest.json"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text())
    assert data["status"] == "complete_i5_i6_ingress_isolation_partial_boundary_i7_i8_open"
    assert data["implemented_retirement_boundaries"] == ["I5", "I6"]
    disposition = data["disposition"]
    assert disposition["verification_p3_and_direct_ingress_retired"] is True
    assert disposition["partial_provider_boundary_connected"] is True
    assert disposition["live_r3_direct_work_producers_complete"] is False
    assert disposition["source_payload_lease_export_complete"] is False
    assert disposition["numeric_or_physical_realization_complete"] is False
    print("PASS: rtl3_8_3_source_partial_boundary_isolation semantic record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
