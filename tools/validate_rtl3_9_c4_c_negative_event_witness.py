#!/usr/bin/env python3
"""Validate RTL3.9-C4-C's host-only negative accepted-event witness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "analysis/rtl3_9_c4_c_negative_event_witness_manifest.json",
        help="C4-C negative-event witness manifest",
    )
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert data["schema_version"] == "kvzap-route-a-rtl3-9-c4-c-negative-event-witness-1.0"
    assert data["status"] == "complete_directed_chisel_witness"
    assert data["trace_rule"].startswith("append only after an actual selected C4 event/output handshake")
    cases = data["cases"]
    assert cases["stale_r1_read_response"]["accepted_events"] == ["authority_transition"]
    assert cases["stale_or_mismatched_r4_completion"]["accepted_events"] == ["authority_transition"]
    assert cases["matching_r4_numeric_fault"]["accepted_events"] == [
        "authority_transition", "attention_terminal(status=FAULT)",
    ]
    assert cases["reset_while_selected_event_is_held"]["accepted_events"] == []
    assert {"RTL owner state", "authority table", "event FIFO", "event inference from valid"} <= set(data["forbidden"])
    oracle = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteAC4CNegativeReplayOracle.scala").read_text(encoding="utf-8")
    witness = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala").read_text(encoding="utf-8")
    for token in [
        "object RouteAC4CNegativeReplayOracle", "def staleOrMismatch", "def numericFault", "def reset",
        "stale/mismatch may retain only its earlier authority prefix",
        "numeric fault must terminate once without free/retire events",
        "reset must clear an unaccepted event rather than replay it",
    ]:
        assert token in oracle
    for token in [
        "C4-C retains only authority after a stale R1 packed-read response",
        "C4-C rejects stale R4 completions and confines matching numeric fault to one terminal",
        "C4-C reset clears a held authority event without replay",
        "RouteAC4CNegativeReplayOracle.staleOrMismatch(",
        "RouteAC4CNegativeReplayOracle.numericFault(",
        "RouteAC4CNegativeReplayOracle.reset(",
        "d.io.c3_r4_result.ready.expect(false.B)",
        "d.io.c3_r4_numeric_fault.ready.expect(false.B)",
        "d.io.c4_attention_terminal_event.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)",
    ]:
        assert token in witness
    disposition = data["disposition"]
    assert disposition["c4_c_implementation_complete"] is True
    assert disposition["c4_c_directed_chisel_witness_complete"] is True
    assert disposition["c4_d_completion_review_authorized"] is True
    print("PASS: RTL3.9-C4-C completes host-only stale/mismatch, numeric-fault, and reset event boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
