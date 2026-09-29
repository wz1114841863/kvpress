from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "validate_rtl1_0_verification_binding.py"
ADAPTER = ROOT / "hardware/route_a/chisel/testbench/route_a_scoreboard_oracle_binding.py"


def _load_adapter():
    spec = importlib.util.spec_from_file_location("route_a_scoreboard_oracle_binding", ADAPTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_rtl1_0_binding_validator_passes_without_model_execution():
    result = subprocess.run([sys.executable, str(TOOL)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "verification binding passed" in result.stdout


def test_rtl1_0_binding_rejects_owner_drift(tmp_path: Path):
    source = ROOT / "hardware/route_a/chisel/src/test/resources/rtl1_0_verification_binding.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["bindings"][0]["rtl_owner"] = "route_a_page_manager"
    candidate = tmp_path / "binding.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(TOOL), "--binding-manifest", str(candidate)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "owner drift" in result.stderr


def test_python_scoreboard_registry_preserves_frozen_oracle_entry_labels():
    adapter = _load_adapter()
    registry = adapter.RouteAScoreboardOracleBindingRegistry(ROOT)
    assert len(registry.assertion_ids()) == 15
    binding = registry.binding_for("a_gqa_release")
    assert binding.rtl_owner == "route_a_s2_gqa_source_wrapper"
    assert binding.oracle == "kvpress/route_a_architecture_reference.py"
    assert binding.entry_points == ("allocate_s2", "consumer_partial_commit", "release_s2")
    assert "payload read" in binding.forbidden_adapter


def test_python_scoreboard_registry_rejects_unknown_assertion_id():
    adapter = _load_adapter()
    registry = adapter.RouteAScoreboardOracleBindingRegistry(ROOT)
    with pytest.raises(KeyError):
        registry.binding_for("unknown_assertion")
