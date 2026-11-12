#!/usr/bin/env python3
"""Validate the fail-closed RTL3.9-C4-A event-capture precondition audit."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    adapter = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteAReclaimScoreboardAdapterSpec.scala").read_text(encoding="utf-8")
    for token in [
        "val allocator_release_in = Flipped(RouteAChannels.allocator_release)",
        "val descriptor_invalidate_event_out", "val page_free_event_out",
        "descriptor_operation := RouteADescriptorOperationKind.Invalidate.U",
        "delivery_context_ref := RouteARTL2WriteDeliveryContext.R5Reclaim.U",
    ]:
        assert token in adapter
    print("PASS: RTL3.9-C4-A audit source carrier structure checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
