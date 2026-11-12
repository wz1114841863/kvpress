#!/usr/bin/env python3
"""Validate the fail-closed RTL3.9-C4-C negative-event precondition audit."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    harness = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala").read_text(encoding="utf-8")
    r4_boundary = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl3/RouteAFunctionalR4ReferenceBoundarySpec.scala").read_text(encoding="utf-8")
    for token in [
        "val c3_r4_numeric_fault = Flipped(RouteAChannels.r4_numeric_fault)",
        "c3R4Reference.io.functional_numeric_fault_in <> io.c3_r4_numeric_fault",
        "response(d, payloadRequestId + 1, 0, last = false, incarnation = payloadIncarnation)",
        "d.reset.poke(true.B)", "val c4_page_free_event = Decoupled(new PageFreeScoreboardEvent)",
    ]:
        assert token in harness
    for token in [
        "A stale response cannot become an R4 terminal after work issue.",
        "maps only a matching issued work item to numeric fault and rejects simultaneous terminal kinds",
    ]:
        assert token in r4_boundary
    print("PASS: RTL3.9-C4-C negative ingress source structure checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
