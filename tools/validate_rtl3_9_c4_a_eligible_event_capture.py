#!/usr/bin/env python3
"""Validate RTL3.9-C4-A's page-free-only accepted-event capture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "analysis/rtl3_9_c4_a_eligible_event_capture_manifest.json",
        help="C4-A eligible event-capture manifest",
    )
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert data["schema_version"] == "kvzap-route-a-rtl3-9-c4-a-eligible-event-capture-1.0"
    assert data["status"] == "complete_testbench_page_free_capture"
    event = data["selected_event"]
    assert event["event"] == "page_free"
    assert event["actual_acceptance"] == "r5.allocator_release_out.fire"
    assert event["field_map"] == ["page_ref.page_id", "page_ref.generation"]
    assert set(data["excluded_events"]) == {
        "descriptor_invalidate", "publication_commit", "reclaim_complete", "outer_functional_memory_traffic",
    }
    assert "descriptor-invalidate field inference" in data["forbidden"]
    source = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteAC3bEventProvenanceObserver.scala").read_text(encoding="utf-8")
    harness = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala").read_text(encoding="utf-8")
    for token in [
        "final class RouteAPageFreeScoreboardObserver", "val allocator_release_in = Flipped(RouteAChannels.allocator_release)",
        "val page_free_event_out = Decoupled(new PageFreeScoreboardEvent)",
        "assert(io.allocator_release_in.fire === io.allocator_release_out.fire)",
        "assert(io.allocator_release_out.fire === io.page_free_event_out.fire)",
    ]:
        assert token in source
    for token in [
        "val c4_page_free_event = Decoupled(new PageFreeScoreboardEvent)",
        "val c4PageFreeObserver = Module(new RouteAPageFreeScoreboardObserver)",
        "r5.io.allocator_release_out.ready := Mux(c4PageFreeBindingActive, c4PageFreeObserver.io.allocator_release_in.ready, true.B)",
        "timed out waiting for the selected R5 page-free event",
        "d.io.reclaim_complete.expect(true.B)",
    ]:
        assert token in harness
    disposition = data["disposition"]
    assert disposition["c4_a_eligible_event_capture_complete"] is True
    assert disposition["c4_b_replay_authorized"] is True
    assert disposition["c4_c_negative_coverage_complete"] is False
    assert disposition["c4_d_completion_review_authorized"] is False
    print("PASS: RTL3.9-C4-A binds only R5 page-free to its accepted old-PageRef release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
