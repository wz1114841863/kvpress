from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.rtl2_attention_terminal_scoreboard_binding import (
    AttentionTerminalObservation,
    AttentionTerminalScoreboardBindingError,
    RouteARTL2AttentionTerminalScoreboardAdapter,
    validate_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "analysis" / "rtl2_4_3_attention_terminal_scoreboard_binding.json"
SCHEMA = ROOT / "analysis" / "rtl2_scoreboard_event_schema.json"
OVERLAY = ROOT / "analysis" / "rtl2_scoreboard_event_phase_reconciliation_01.json"
VALIDATOR = ROOT / "tools" / "validate_rtl2_4_3_attention_terminal_scoreboard_binding.py"


def _event(request_id: int, incarnation: int, terminal_status: int) -> AttentionTerminalObservation:
    return AttentionTerminalObservation("attention_terminal", {"request_id": request_id, "incarnation": incarnation, "terminal_status": terminal_status})


def test_binding_preserves_r4_origin_and_r6_outward_observation_without_rewriting_base_schema():
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    validate_binding(binding, schema, overlay)
    assert schema["status"] == "declared_pre_behavior_no_events_emittable"
    assert next(item for item in overlay["overrides"] if item["event"] == "attention_terminal")["active_activation_phase"] == "rtl2_4"


def test_adapter_dispatches_exact_success_and_numeric_fault_to_the_existing_r6_reference():
    adapter = RouteARTL2AttentionTerminalScoreboardAdapter(ROOT)
    adapter.arm_attention(TransactionIdentity(1, 1))
    assert adapter.dispatch(_event(1, 1, 0)) == "success"
    adapter.arm_attention(TransactionIdentity(2, 0))
    assert adapter.dispatch(_event(2, 0, 1)) == "fault"


def test_adapter_rejects_malformed_duplicate_stale_and_reset_era_terminal_events():
    adapter = RouteARTL2AttentionTerminalScoreboardAdapter(ROOT)
    with pytest.raises(AttentionTerminalScoreboardBindingError, match="active or retiring"):
        adapter.dispatch(_event(1, 0, 0))
    adapter.arm_attention(TransactionIdentity(3, 1))
    assert adapter.dispatch(_event(3, 1, 0)) == "success"
    with pytest.raises(AttentionTerminalScoreboardBindingError, match="not live"):
        adapter.dispatch(_event(3, 1, 0))
    adapter.arm_attention(TransactionIdentity(4, 0))
    adapter.destructive_reset()
    with pytest.raises(AttentionTerminalScoreboardBindingError, match="active or retiring"):
        adapter.dispatch(_event(4, 0, 1))
    with pytest.raises(AttentionTerminalScoreboardBindingError, match="fields differ"):
        adapter.dispatch(AttentionTerminalObservation("attention_terminal", {"request_id": 0, "incarnation": 0}))
    with pytest.raises(AttentionTerminalScoreboardBindingError, match="unknown terminal_status"):
        adapter.dispatch(_event(0, 0, 2))


def test_binding_validator_rejects_field_or_owner_drift_and_cli_supports_help_and_defaults():
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    malformed = copy.deepcopy(binding)
    malformed["event"]["required_fields"].remove("terminal_status")
    with pytest.raises(AttentionTerminalScoreboardBindingError, match="required fields drift"):
        validate_binding(malformed, schema, overlay)
    malformed = copy.deepcopy(binding)
    malformed["event"]["origin_owner"] = "route_a_lifecycle_adapter"
    with pytest.raises(AttentionTerminalScoreboardBindingError, match="origin owner/carrier"):
        validate_binding(malformed, schema, overlay)
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--phase-overlay" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "attention-terminal scoreboard binding passed" in result.stdout
