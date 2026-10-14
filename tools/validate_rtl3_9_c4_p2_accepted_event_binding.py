#!/usr/bin/env python3
"""Validate the narrow testbench-only RTL3.9-C4-P2 accepted-event binding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "analysis/rtl3_9_c4_p2_accepted_event_binding_manifest.json",
        help="C4-P2 binding manifest",
    )
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert data["schema_version"] == "kvzap-route-a-rtl3-9-c4-p2-accepted-event-binding-1.0"
    assert data["status"] == "complete_testbench_selected_accepted_event_binding"
    events = data["selected_events"]
    assert [item["event"] for item in events] == ["authority_transition", "attention_terminal", "retire_ack"]
    assert events[0]["actual_acceptance"] == "lifecycle.authority_transition_in.fire / io.r6_authority_transition_fire"
    assert events[0]["selection_predicate"] == "from_authority=Pending and to_authority=Packed"
    assert events[1]["existing_binding"] == "analysis/rtl2_4_3_attention_terminal_scoreboard_binding.json"
    assert events[2]["existing_binding"] == "analysis/rtl2_5_5_active_state_scoreboard_binding.json"
    assert set(data["excluded_events"]) == {
        "request_accept", "fragment_deliver", "write_commit", "descriptor_durable", "metadata_publish_commit",
        "source_deliverable", "consumer_partial_commit", "source_release", "merge_request",
        "descriptor_invalidate", "page_free",
    }
    forbidden = set(data["forbidden"])
    assert {"event from publication_commit", "event from S2 READY or availability", "event from external functional-memory traffic", "event from reclaim_complete", "second R6 authority owner or ordinal table", "page_free or descriptor_invalidate capture"} <= forbidden
    source = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteAC3bEventProvenanceObserver.scala").read_text(encoding="utf-8")
    harness = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala").read_text(encoding="utf-8")
    for token in [
        "final class RouteAC3bEventProvenanceObserver", "from_authority === RouteAAuthorityStateCode.Pending.U",
        "to_authority === RouteAAuthorityStateCode.Packed.U", "RouteAAttentionTerminalScoreboardAdapter",
        "RouteARetireAckScoreboardObserver", "assert(io.authority_transition_in.fire === io.authority_transition_out.fire)",
    ]:
        assert token in source
    for token in [
        "val c4_event_binding_mode = Input(Bool())", "c4_authority_transition_event",
        "c4_attention_terminal_event", "c4_retire_ack_event", "timed out waiting for the selected R3-to-R6 authority event",
        "timed out waiting for the selected C3 terminal event", "timed out waiting for the selected final R6 retire-ack event",
    ]:
        assert token in harness
    disposition = data["disposition"]
    assert disposition["c4_p2_complete"] is True
    assert disposition["c4_event_trace_or_oracle_replay_complete"] is False
    assert disposition["c4_stall_stale_fault_reset_coverage_complete"] is False
    assert disposition["rtl3_completion_review_authorized"] is False
    assert disposition["physical_or_numeric_claim"] is False
    print("PASS: RTL3.9-C4-P2 binds exactly three selected accepted events; all other schema events remain excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
