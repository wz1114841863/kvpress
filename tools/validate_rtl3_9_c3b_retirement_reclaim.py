#!/usr/bin/env python3
"""No-model structural preflight for RTL3.9-C3b retirement and reclaim."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED = {
    "analysis/rtl3_9_c3b_retirement_reclaim_contract.md": (
        "one matching R6 attention terminal", "R6 reclaim permit",
        "one matching R6 session-retire acknowledgement", "functional outer environment",
    ),
    "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala": (
        "status_collector.io.reclaim_drain_restart := lifecycle.io.reclaim_drain_restart",
        "page_manager.io.reclaim_permit_in <> lifecycle.io.reclaim_permit_out",
        "lifecycle.io.r5_reclaim_complete_in := page_manager.io.reclaim_complete",
    ),
    "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala": (
        "c3b_retire_reclaim_mode", "c3bStatusCollector", "c3b_runtime_retire",
        "retires the first post-R6 packed read only after final drain, durable R5 invalidation, and page reclaim",
        "c3bStatusCollector.io.status_sources(0).valid := io.c3b_retire_reclaim_mode",
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
    print("RTL3.9-C3b retirement/reclaim preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
