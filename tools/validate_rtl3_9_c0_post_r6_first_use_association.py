#!/usr/bin/env python3
"""No-model structural preflight for the RTL3.9-C0 first-use contract."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED = {
    "analysis/rtl3_9_c0_post_r6_first_use_association_contract.md": (
        "PostR6PackedPageReadyObservation",
        "authority_transition_out.fire",
        "no descriptor",
    ),
    "hardware/route_a/chisel/src/main/scala/kvpress/routea/interfaces/RouteAInterfaces.scala": (
        "PostR6PackedPageReadyObservation",
        "post_r6_packed_page_ready_observation",
    ),
    "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala": (
        "postR6PageReadyActive",
        "post_r6_packed_page_ready_observation",
    ),
    "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAPackedReadActivationBinder.scala": (
        "publication_member_in",
        "post_r6_page_ready_in",
        "memberStreamMatchesReady",
    ),
    "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala": (
        "publication_member_in <> m2_p3.io.publication_member_observation",
        "post_r6_page_ready_in <> m2_p3.io.post_r6_packed_page_ready_observation",
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
    print("RTL3.9-C0 post-R6 first-use association preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
