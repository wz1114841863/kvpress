#!/usr/bin/env python3
"""No-model structural preflight for RTL3.9-C2 functional read-to-S2 closure."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED = {
    "analysis/rtl3_9_c2_functional_read_to_s2_contract.md": (
        "S2 `READY`",
        "terminal fault",
        "C3/C4",
    ),
    "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala": (
        "packed_terminal_bridge.io.work_in <> packed_association_owner.io.packed_s2_work_out",
        "packed_s2_read_producer.io.work_in <> packed_terminal_bridge.io.work_out",
        "packed_s2_read_endpoint.io.resolved_fragment_in <> read_endpoint_demultiplexer.io.packed_s2_out",
        "packed_s2_sidecar_endpoint.io.resolved_fragment_in <> read_endpoint_demultiplexer.io.packed_s2_sidecar_out",
    ),
    "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala": (
        "c2_read_activation_mode",
        "c2_s2_state",
        "delivers the first post-R6 packed payload and sidecar through R2/R1 to S2 READY",
        "payloadRequestId + 1",
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
    print("RTL3.9-C2 functional read-to-S2 preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
