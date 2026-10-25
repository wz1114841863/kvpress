from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "analysis/mr2_completion_review.md"
HANDOFF = ROOT / "analysis/route_a_current_handoff.md"


def test_mr2_review_preserves_array_only_and_nonphysical_boundary() -> None:
    text = REVIEW.read_text(encoding="utf-8")
    for required in (
        "functional_measurement_boundary_passed",
        "P3 stage payload and sidecar arrays",
        "S2 payload and sidecar arrays",
        "M2 head/span entry arrays",
        "R5 availability/generation vectors",
        "Array-only rule holds",
        "Common versus differential treatment remains intact",
        "does **not** authorize synthesis, DC/CACTI, PPA",
        "dual-DUT measurement-cut freeze",
    ):
        assert required in text


def test_mr2_review_is_linked_from_live_handoff() -> None:
    assert "MR-2 completion review (2026-10-25)" in HANDOFF.read_text(encoding="utf-8")
    assert "mr2_completion_review.md" in HANDOFF.read_text(encoding="utf-8")
