#!/usr/bin/env python3
"""No-model structural preflight for RTL3.9-C3a packed source service."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED = {
    "analysis/rtl3_9_c3a_packed_source_service_terminal_contract.md": (
        "S2 is `READY`", "four consumer commits", "C3b",
    ),
    "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala": (
        "s2.io.service_req_in <> lifecycle.io.s2_service_req",
        "source_commit_demultiplexer.io.commit_in <> merge.io.consumer_partial_commit",
        "lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault",
    ),
    "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala": (
        "c3_terminal_activation_mode", "c3_packed_offer", "c3_merge_work",
        "continues the first post-R6 packed read through source service and four R4 completions to one terminal",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    args = parser.parse_args()
    for relative, tokens in REQUIRED.items():
        text = (args.root / relative).read_text(encoding="utf-8")
        for token in tokens:
            assert token in text, f"missing {token!r} in {relative}"
    print("RTL3.9-C3a packed source-service terminal preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
