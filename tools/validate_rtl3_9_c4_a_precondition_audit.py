#!/usr/bin/env python3
"""Validate the fail-closed RTL3.9-C4-A event-capture precondition audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit", type=Path,
        default=ROOT / "analysis/rtl3_9_c4_a_precondition_audit.json",
        help="C4-A precondition-audit record",
    )
    args = parser.parse_args(argv)
    data = json.loads(args.audit.read_text(encoding="utf-8"))
    assert data["schema_version"] == "kvzap-route-a-rtl3-9-c4-a-precondition-audit-1.0"
    assert data["status"] == "complete_audit_no_rtl_capture_change"
    rows = {row["name"]: row for row in data["candidates"]}
    assert list(rows) == ["attention_terminal", "descriptor_invalidate", "page_free", "retire_ack"]
    assert rows["attention_terminal"]["c4_a_capture_eligible"] is True
    assert rows["page_free"]["acceptance"] == "r5.allocator_release_out.fire"
    assert rows["page_free"]["c4_a_capture_eligible"] is True
    assert rows["retire_ack"]["c4_a_capture_eligible"] is True
    assert rows["descriptor_invalidate"]["c4_a_capture_eligible"] is False
    assert "not fields of one accepted C3b owner carrier" in rows["descriptor_invalidate"]["fail_closed_reason"]
    assert data["r5_old_page_ref_release"]["classification"].startswith("exact owner-produced")
    disposition = data["disposition"]
    assert disposition["c4_a_precondition_audit_complete"] is True
    assert disposition["c4_a_capture_complete"] is False
    assert disposition["eligible_event_names"] == ["attention_terminal", "page_free", "retire_ack"]
    assert disposition["ineligible_event_names"] == ["descriptor_invalidate"]
    assert not disposition["c4_b_replay_authorized"]
    adapter = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteAReclaimScoreboardAdapterSpec.scala").read_text(encoding="utf-8")
    for token in [
        "val allocator_release_in = Flipped(RouteAChannels.allocator_release)",
        "val descriptor_invalidate_event_out", "val page_free_event_out",
        "descriptor_operation := RouteADescriptorOperationKind.Invalidate.U",
        "delivery_context_ref := RouteARTL2WriteDeliveryContext.R5Reclaim.U",
    ]:
        assert token in adapter
    print("PASS: RTL3.9-C4-A audit authorizes only complete terminal/page-free/retire carriers and rejects descriptor-invalidate field inference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
