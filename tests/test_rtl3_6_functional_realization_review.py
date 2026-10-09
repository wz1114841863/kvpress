from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl3_6_functional_realization_review import (
    RTL36FunctionalRealizationReviewError,
    load,
    validate,
    validate_hashes,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl3_6_functional_realization_completion_review_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl3_6_functional_realization_review.py"


def test_rtl3_6_records_completed_slices_without_overclaiming_live_composition():
    manifest = load(MANIFEST)
    validate(manifest, ROOT)
    assert manifest["disposition"]["rtl3_functional_realization_complete"] is False
    assert "no_same_instance_live_functional_partial_to_r4_to_r6_terminal_binding" in manifest["open_gaps"]


def test_rtl3_6_rejects_false_pass_hidden_gap_and_predecessor_drift():
    manifest = load(MANIFEST)
    bad = copy.deepcopy(manifest)
    bad["disposition"]["rtl3_functional_realization_complete"] = True
    with pytest.raises(RTL36FunctionalRealizationReviewError, match="may not claim"):
        validate(bad, ROOT)
    bad = copy.deepcopy(manifest)
    bad["open_gaps"] = bad["open_gaps"][1:]
    with pytest.raises(RTL36FunctionalRealizationReviewError, match="gap"):
        validate(bad, ROOT)
    bad = copy.deepcopy(manifest)
    bad["blocked_preflight"]["bindings"] = []
    with pytest.raises(RTL36FunctionalRealizationReviewError, match="blocked replay"):
        validate(bad, ROOT)
    bad = copy.deepcopy(manifest)
    bad["reviewed_predecessors"]["analysis/rtl3_5c_cross_language_packet_binding_manifest.json"] = "production_top_bound"
    with pytest.raises(RTL36FunctionalRealizationReviewError, match="predecessor"):
        validate(bad, ROOT)


def test_rtl3_6_hashes_and_validator_help_are_reproducible():
    manifest = load(MANIFEST)
    validate_hashes(manifest, ROOT)
    bad = copy.deepcopy(manifest)
    bad["source_sha256"]["analysis/rtl3_6_functional_realization_completion_review.md"] = "0" * 64
    with pytest.raises(RTL36FunctionalRealizationReviewError, match="hash-bound"):
        validate_hashes(bad, ROOT)
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "precise no-PASS" in result.stdout
