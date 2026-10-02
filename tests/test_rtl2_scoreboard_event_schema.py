from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_activation_manifest import load_manifest
from kvpress.rtl2_scoreboard_event_schema import RTL2ScoreboardEventSchemaError, load_schema, validate_schema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "analysis" / "rtl2_scoreboard_event_schema.json"
MANIFEST = ROOT / "analysis" / "rtl2_0_activation_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl2_scoreboard_event_schema.py"


def test_schema_is_a_pre_behavior_versioned_binding_of_all_inventory_events():
    schema = load_schema(SCHEMA)
    validate_schema(schema, load_manifest(MANIFEST))
    assert schema["status"] == "declared_pre_behavior_no_events_emittable"
    assert len(schema["event_records"]) == 14
    assert schema["adapter"]["state"] == "schema_only_not_implemented"


def test_schema_rejects_dropped_identity_or_early_event_emission():
    schema = copy.deepcopy(load_schema(SCHEMA))
    event = next(record for record in schema["event_records"] if record["event"] == "source_release")
    event["required_fields"].remove("source_generation")
    with pytest.raises(RTL2ScoreboardEventSchemaError, match="drops an inventory identity field"):
        validate_schema(schema, load_manifest(MANIFEST))

    schema = copy.deepcopy(load_schema(SCHEMA))
    schema["event_records"][0]["emission_state"] = "emittable_now"
    with pytest.raises(RTL2ScoreboardEventSchemaError, match="non-emittable"):
        validate_schema(schema, load_manifest(MANIFEST))


def test_schema_validator_cli_supports_help_and_default_inputs():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--activation-manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "RTL2 scoreboard event schema passed" in result.stdout
