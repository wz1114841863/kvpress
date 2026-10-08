import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_6_5e_same_instance_review import RTL265eReviewError, load, validate, validate_hashes

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl2_6_5e_same_instance_witness_manifest.json"
CAPTURE = ROOT / "analysis/rtl2_6_5c_event_capture_replay_manifest.json"
PRIOR = ROOT / "analysis/rtl2_6_5d_completion_review.json"
VALIDATOR = ROOT / "tools/validate_rtl2_6_5e_same_instance_review.py"

def payloads():
    return load(MANIFEST), load(CAPTURE), load(PRIOR)

def test_same_instance_witness_closes_only_the_prior_named_testbench_gap():
    manifest, capture, prior = payloads(); validate(manifest, capture, prior)
    assert manifest["disposition"] == {"rtl2_production_transaction_dataflow_complete": True, "scope": "testbench_only_functional_transaction_dataflow"}

def test_review_rejects_hidden_witness_gap_false_capture_or_broadened_scope():
    manifest, capture, prior = payloads()
    bad = copy.deepcopy(manifest); bad["same_instance_witness"]["same_r5_durable_reclaim_to_retire_ack"] = False
    with pytest.raises(RTL265eReviewError, match="obligations"):
        validate(bad, capture, prior)
    bad_capture = copy.deepcopy(capture); bad_capture["replay_cases"].pop()
    with pytest.raises(RTL265eReviewError, match="case coverage"):
        validate(manifest, bad_capture, prior)
    bad = copy.deepcopy(manifest); bad["disposition"]["scope"] = "production_rtl"
    with pytest.raises(RTL265eReviewError, match="testbench-only"):
        validate(bad, capture, prior)

def test_hashes_and_cli_are_reproducible():
    manifest, _, _ = payloads(); validate_hashes(manifest, ROOT)
    bad = copy.deepcopy(manifest); bad["source_sha256"]["analysis/rtl2_6_5d_completion_review.json"] = "0" * 64
    with pytest.raises(RTL265eReviewError, match="hash-bound"):
        validate_hashes(bad, ROOT)
    assert "--prior-review" in subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    assert "passed" in subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True).stdout
