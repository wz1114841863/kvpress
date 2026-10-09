from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools" / "validate_rtl3_5a_attention_partial_producer_boundary.py"
MANIFEST = ROOT / "analysis" / "rtl3_5a_attention_partial_producer_boundary_manifest.json"


def test_rtl3_5a_manifest_declares_one_external_query_owner_and_one_partial_owner():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["owners"]["query_context"] == "common_frontend_attention_context_provider"
    assert manifest["partial_packet_producer"] == "route_a_functional_attention_partial_provider"
    assert manifest["qwen_anchor_association"]["query_head_mapping"] == "query_head = 4 * kv_head + consumer_id"
    assert manifest["rope_and_position_semantics"]["query_rope_state"] == "already_applied_by_common_frontend"
    assert manifest["rope_and_position_semantics"]["key_rope_state"] == "already_applied_at_kv_creation"


def test_rtl3_5a_manifest_validator_and_help_pass():
    help_result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, check=True, text=True, capture_output=True
    )
    assert "partial-producer" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, check=True, text=True, capture_output=True)
    assert "PASS: RTL3.5-A" in result.stdout
