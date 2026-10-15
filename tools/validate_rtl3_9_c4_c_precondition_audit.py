#!/usr/bin/env python3
"""Validate the fail-closed RTL3.9-C4-C negative-event precondition audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit", type=Path,
        default=ROOT / "analysis/rtl3_9_c4_c_precondition_audit.json",
        help="C4-C precondition-audit record",
    )
    args = parser.parse_args(argv)
    data = json.loads(args.audit.read_text(encoding="utf-8"))
    assert data["schema_version"] == "kvzap-route-a-rtl3-9-c4-c-precondition-audit-1.0"
    assert data["status"] == "complete_audit_c4_c_implementation_authorized"
    assert data["selected_event_outputs"] == [
        "io.c4_authority_transition_event", "io.c4_attention_terminal_event",
        "io.c4_page_free_event", "io.c4_retire_ack_event",
    ]
    cases = {case["name"]: case for case in data["cases"]}
    assert list(cases) == [
        "stale_r1_read_response", "stale_or_mismatched_r4_completion",
        "matching_r4_numeric_fault", "reset_while_selected_event_is_held",
    ]
    assert cases["stale_r1_read_response"]["allowed_event_prefix"] == ["authority_transition"]
    assert cases["stale_or_mismatched_r4_completion"]["forbidden_event_suffix"] == [
        "attention_terminal", "page_free", "retire_ack",
    ]
    assert cases["matching_r4_numeric_fault"]["allowed_event_prefix"] == [
        "authority_transition", "attention_terminal(status=FAULT)",
    ]
    assert cases["matching_r4_numeric_fault"]["forbidden_event_suffix"] == ["page_free", "retire_ack"]
    assert cases["reset_while_selected_event_is_held"]["allowed_event_prefix"] == []
    assert "treat a valid-only signal as an accepted event" in data["forbidden"]
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
    disposition = data["disposition"]
    assert disposition["c4_c_precondition_audit_complete"] is True
    assert disposition["c4_c_implementation_authorized"] is True
    assert disposition["c4_c_negative_witness_complete"] is False
    assert disposition["c4_d_completion_review_authorized"] is False
    print("PASS: RTL3.9-C4-C has exact negative ingress and allowed-prefix/forbidden-suffix event criteria")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
