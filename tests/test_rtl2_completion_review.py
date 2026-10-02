from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_activation_manifest import load_manifest
from kvpress.rtl2_completion_review import RTL2CompletionReviewError, load_review, validate_review
from kvpress.rtl2_scoreboard_event_schema import load_schema


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "analysis" / "rtl2_0_completion_review_manifest.json"
MANIFEST = ROOT / "analysis" / "rtl2_0_activation_manifest.json"
SCHEMA = ROOT / "analysis" / "rtl2_scoreboard_event_schema.json"
VALIDATOR = ROOT / "tools" / "validate_rtl2_completion_review.py"


def test_completion_review_passes_all_seven_closed_amendments_before_behavior():
    review = load_review(REVIEW)
    validate_review(review, load_manifest(MANIFEST), load_schema(SCHEMA), ROOT)
    assert len(review["amendment_closures"]) == 7
    assert review["review_checks"]["top_composition_only"] is True
    assert review["review_checks"]["behavioral_activation_started"] is False


def test_completion_review_rejects_missing_closure_or_missing_historical_review_anchor():
    review = copy.deepcopy(load_review(REVIEW))
    review["amendment_closures"] = review["amendment_closures"][:-1]
    with pytest.raises(RTL2CompletionReviewError, match="exact seven"):
        validate_review(review, load_manifest(MANIFEST), load_schema(SCHEMA), ROOT)

    review = copy.deepcopy(load_review(REVIEW))
    review["reviewed_commit"] = ""
    with pytest.raises(RTL2CompletionReviewError, match="reviewed commit"):
        validate_review(review, load_manifest(MANIFEST), load_schema(SCHEMA), ROOT)


def test_completion_review_validator_cli_supports_help_and_default_inputs():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--scoreboard-schema" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "RTL2.0 completion review passed" in result.stdout
