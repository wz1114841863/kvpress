#!/usr/bin/env python3
"""Validate the RTL3.8.2 functional-sidecar delivery evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "analysis/rtl3_8_2_functional_sidecar_delivery_manifest.json",
        help="RTL3.8.2 manifest to validate",
    )
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert data["status"] == "complete_i4_functional_sidecar_delivery_i5_i8_open"
    assert data["implemented_retirement_boundaries"] == ["I4"]
    disposition = data["disposition"]
    assert disposition["functional_sidecar_delivery_complete"] is True
    assert disposition["verification_sidecar_ingress_retired_from_functional_top"] is True
    assert disposition["sidecar_uses_existing_registry_r2_r1_path"] is True
    assert disposition["i5_i8_functional_replacement_complete"] is False
    assert disposition["physical_or_numeric_realization_complete"] is False
    print("PASS: RTL3.8.2 functional-sidecar semantic record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
