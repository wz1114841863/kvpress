#!/usr/bin/env python3
"""No-model structural preflight for RTL3.9-C1 demand activation."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED = {
    "analysis/rtl3_9_c1_post_publication_demand_activation_contract.md": (
        "post-R6",
        "C2--C4",
        "registry allocation",
    ),
    "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala": (
        "packed_association_owner.io.demand_in <> packed_activation_binder.io.demand_out",
        "packed_association_owner.io.publication_authorization_in <>",
        "packed_association_owner.io.descriptor_grant_in <> packed_activation_binder.io.descriptor_grant_out",
        "packed_association_owner.io.s2_fill_lease_in <> packed_activation_binder.io.s2_fill_lease_out",
    ),
    "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala": (
        "c1_demand_activation_mode",
        "c1_page_ready_fire",
        "c1_registry_allocate",
        "without entering C2 read transport",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    args = parser.parse_args()
    for relative, required in REQUIRED.items():
        text = (args.root / relative).read_text(encoding="utf-8")
        for token in required:
            assert token in text, f"missing {token!r} in {relative}"
    print("RTL3.9-C1 post-publication demand activation preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
