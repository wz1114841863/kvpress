#!/usr/bin/env python3
"""Validate RTL3.9-C4-B's host-only event replay and bounded-stall contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "analysis/rtl3_9_c4_b_event_replay_manifest.json",
        help="C4-B event-replay manifest",
    )
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert data["schema_version"] == "kvzap-route-a-rtl3-9-c4-b-event-replay-1.0"
    assert data["status"] == "complete_directed_chisel_witness"
    assert data["trace"]["events_in_exact_order"] == [
        "authority_transition", "attention_terminal", "page_free", "retire_ack",
    ]
    assert data["bounded_legal_backpressure"]["cycles_per_event"] == 2
    assert data["bounded_legal_backpressure"]["events"] == data["trace"]["events_in_exact_order"]
    assert {"event FIFO", "owner state", "event from reclaim_complete", "descriptor-invalidate field inference"} <= set(data["trace"]["forbidden"])
    oracle = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteAC4BEventReplayOracle.scala").read_text(encoding="utf-8")
    witness = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala").read_text(encoding="utf-8")
    for token in [
        "sealed trait RouteAC4BAcceptedEvent", "final case class RouteAC4BAuthorityAccepted",
        "final case class RouteAC4BTerminalAccepted", "final case class RouteAC4BPageFreeAccepted",
        "final case class RouteAC4BRetireAckAccepted", "object RouteAC4BEventReplayOracle",
        "expected one accepted C4 event in order", "accepted C4 event trace replayed an event",
    ]:
        assert token in oracle
    for token in [
        "val c4AcceptedTrace = ArrayBuffer.empty[RouteAC4BAcceptedEvent]",
        "(0 until 2).foreach", "RouteAC4BAuthorityAccepted(", "RouteAC4BTerminalAccepted(",
        "RouteAC4BPageFreeAccepted(", "RouteAC4BRetireAckAccepted(",
        "RouteAC4BEventReplayOracle.replay(", "d.io.r6_authority_transition_fire.expect(false.B)",
    ]:
        assert token in witness
    disposition = data["disposition"]
    assert disposition["c4_b_implementation_complete"] is True
    assert disposition["c4_b_directed_chisel_witness_complete"] is True
    assert not disposition["c4_c_negative_coverage_complete"]
    print("PASS: RTL3.9-C4-B records and replays four accepted events with two-cycle legal stalls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
