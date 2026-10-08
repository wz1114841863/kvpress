from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_6_1_event_binding import (
    RTL26EventBindingError,
    RTL26EventObservation,
    RouteARTL26EventFieldBindingAdapter,
    load_binding,
    validate_binding,
    validate_source_hashes,
)


ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "analysis/rtl2_6_1_event_binding_manifest.json"
SCHEMA = ROOT / "analysis/rtl2_scoreboard_event_schema.json"
VALIDATOR = ROOT / "tools/validate_rtl2_6_1_event_binding.py"


def _payloads():
    return load_binding(BINDING), json.loads(SCHEMA.read_text(encoding="utf-8"))


def test_all_ten_schema_only_events_have_exact_owner_carrier_and_field_provenance():
    binding, schema = _payloads()
    validate_binding(binding, schema)
    assert [record["event"] for record in binding["event_bindings"]] == [
        "request_accept", "fragment_deliver", "write_commit", "descriptor_durable",
        "metadata_publish_commit", "authority_transition", "source_deliverable",
        "consumer_partial_commit", "source_release", "merge_request",
    ]
    assert all(record["capture_status"] == "contract_bound_chisel_capture_pending" for record in binding["event_bindings"])


def test_binding_rejects_hidden_defaults_non_origin_carriers_and_early_emission_claims():
    binding, schema = _payloads()
    malformed = copy.deepcopy(binding)
    malformed["event_bindings"][0]["field_provenance"][0]["expression"] = "internal request_id default"
    with pytest.raises(RTL26EventBindingError, match="internal/default"):
        validate_binding(malformed, schema)
    malformed = copy.deepcopy(binding)
    malformed["event_bindings"][1]["field_provenance"][0]["carrier"] = "not_an_origin"
    with pytest.raises(RTL26EventBindingError, match="non-origin carrier"):
        validate_binding(malformed, schema)
    malformed = copy.deepcopy(binding)
    malformed["event_bindings"][2]["capture_status"] = "bound_and_emittable"
    with pytest.raises(RTL26EventBindingError, match="must not claim a Chisel capture"):
        validate_binding(malformed, schema)


def test_adapter_requires_one_complete_explicit_schema_field_set_and_hashes_bind_sources():
    binding, _ = _payloads()
    validate_source_hashes(binding, ROOT)
    adapter = RouteARTL26EventFieldBindingAdapter(ROOT)
    observation = RTL26EventObservation("merge_request", {"request_id": 1, "incarnation": 2, "source_presence": 4})
    assert adapter.capture(observation) == observation
    with pytest.raises(RTL26EventBindingError, match="fields differ"):
        adapter.capture(RTL26EventObservation("merge_request", {"request_id": 1, "incarnation": 2}))
    with pytest.raises(RTL26EventBindingError, match="not in the RTL2.6.1"):
        adapter.capture(RTL26EventObservation("retire_ack", {"session_id": 0, "request_id": 1, "incarnation": 2}))
    malformed = copy.deepcopy(binding)
    malformed["source_sha256"]["analysis/rtl2_phase_contract.md"] = "0" * 64
    with pytest.raises(RTL26EventBindingError, match="hash-bound source drift"):
        validate_source_hashes(malformed, ROOT)


def test_validator_has_help_and_default_inputs():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--binding" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "event field-provenance binding passed" in result.stdout
