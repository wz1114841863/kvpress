#!/usr/bin/env python3
"""Validate the bounded RTL3.9-C4-D functional completion-review record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "analysis/rtl3_9_c4_d_functional_completion_review_manifest.json",
        help="C4-D completion-review manifest",
    )
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert data["schema_version"] == "kvzap-route-a-rtl3-9-c4-d-functional-completion-review-1.0"
    assert data["status"] == "complete_functional_subsystem_review"
    assert len(data["required_prior_contracts"]) == 9
    for path in data["required_prior_contracts"]:
        assert (ROOT / path).is_file(), path
    assert data["directed_chisel_validation"]["test_class"] == "kvpress.routea.rtl2.RouteARTL265a2PackReadPublicationSpec"
    assert data["directed_chisel_validation"]["required_test_filters"] == [
        "retires the first post-R6 packed read", "C4-C",
    ]
    assert data["directed_chisel_validation"]["result"].startswith("passed: C3b success/replay 1/1")
    assert len(data["completion_criteria"]) == 7
    assert {"RTL or owner change", "new event carrier or event FIFO", "production-top integration"} <= set(data["forbidden"])
    c4b = json.loads((ROOT / "analysis/rtl3_9_c4_b_event_replay_manifest.json").read_text(encoding="utf-8"))
    c4c = json.loads((ROOT / "analysis/rtl3_9_c4_c_negative_event_witness_manifest.json").read_text(encoding="utf-8"))
    assert c4b["status"] == "complete_directed_chisel_witness"
    assert c4c["status"] == "complete_directed_chisel_witness"
    witness = (ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteARTL265a2PackReadPublicationSpec.scala").read_text(encoding="utf-8")
    for token in [
        "retires the first post-R6 packed read only after final drain, durable R5 invalidation, and page reclaim",
        "C4-C retains only authority after a stale R1 packed-read response",
        "C4-C rejects stale R4 completions and confines matching numeric fault to one terminal",
        "C4-C reset clears a held authority event without replay",
    ]:
        assert token in witness
    disposition = data["disposition"]
    assert disposition["c4_d_implementation_complete"] is True
    assert disposition["c4_d_no_model_preflight_complete"] is True
    assert disposition["c4_d_directed_chisel_validation_complete"] is True
    assert disposition["rtl3_functional_subsystem_review_complete"] is True
    review = (ROOT / "analysis/rtl3_9_c4_d_functional_completion_review.md").read_text(encoding="utf-8")
    for token in [
        "Complete at the declared functional-subsystem scope.",
        "C3b success/replay witness (one", "all C4-C negative witnesses (three tests)",
        "functional external-memory responder", "synthesis-realization partition",
    ]:
        assert token in review
    print("PASS: RTL3.9-C4-D completes the bounded functional-subsystem review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
