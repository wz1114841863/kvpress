import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_6_5d_completion_review import (
    RTL265dCompletionReviewError,
    load_review,
    validate_review,
    validate_source_hashes,
)


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "analysis/rtl2_6_5d_completion_review.json"
SCHEMA = ROOT / "analysis/rtl2_scoreboard_event_schema.json"
CAPTURE = ROOT / "analysis/rtl2_6_5c_event_capture_replay_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl2_6_5d_completion_review.py"


def _payloads():
    return load_review(REVIEW), json.loads(SCHEMA.read_text()), json.loads(CAPTURE.read_text())


def test_review_preserves_no_pass_until_one_same_instance_real_owner_trace_exists():
    review, schema, capture = _payloads()
    validate_review(review, schema, capture)
    assert review["disposition"]["rtl2_production_transaction_dataflow_complete"] is False
    assert review["same_instance_real_owner_trace"]["present"] is False


def test_review_rejects_false_pass_missing_event_capture_or_hidden_gap():
    review, schema, capture = _payloads()
    bad = copy.deepcopy(review); bad["disposition"]["rtl2_production_transaction_dataflow_complete"] = True
    with pytest.raises(RTL265dCompletionReviewError, match="cannot authorize"):
        validate_review(bad, schema, capture)
    bad = copy.deepcopy(review); bad["same_instance_real_owner_trace"]["present"] = True
    with pytest.raises(RTL265dCompletionReviewError, match="may not invent"):
        validate_review(bad, schema, capture)
    bad_capture = copy.deepcopy(capture); bad_capture["captured_event_order"].pop()
    with pytest.raises(RTL265dCompletionReviewError, match="all immutable events"):
        validate_review(review, schema, bad_capture)


def test_review_hashes_and_cli_are_reproducible():
    review, _, _ = _payloads()
    validate_source_hashes(review, ROOT)
    bad = copy.deepcopy(review); bad["source_sha256"]["analysis/rtl2_scoreboard_event_schema.json"] = "0" * 64
    with pytest.raises(RTL265dCompletionReviewError, match="hash-bound"):
        validate_source_hashes(bad, ROOT)
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--capture-manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "no-PASS disposition" in result.stdout
