import json

import pytest

from tools.simulate_kvzap_route_a39_consistent_gate import total_with_continued_admission, validate_inputs


def test_continue_admission_charges_identical_admission_after_both_paths():
    row = {
        "full_layer_bytes": "100",
        "hybrid_layer_bytes": "60",
        "full_layer_cycle_proxy": "20",
        "hybrid_layer_cycle_proxy": "12",
        "admission_bytes": "40",
    }
    assert total_with_continued_admission(row, "full_kv", admission_bandwidth=20) == (140.0, 22.0)
    assert total_with_continued_admission(row, "hybrid", admission_bandwidth=20) == (100.0, 14.0)


def test_rejects_oracle_from_a_different_memory_system_manifest(tmp_path):
    memory, oracle = tmp_path / "memory", tmp_path / "oracle"
    memory.mkdir()
    oracle.mkdir()
    (memory / "memory_system_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a37-memory-system-dse-1.0"}))
    (memory / "memory_system_layer_results.csv").write_text("baseline\n")
    (oracle / "adaptive_gate_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a37-adaptive-gate-dse-1.0", "assumptions": {"decision_objectives": ["cycles"]}, "source_artifact_sha256": {"memory_system_manifest_sha256": "different"}}))
    with pytest.raises(ValueError, match="oracle gate source mismatch.*simulate_kvzap_route_a37_adaptive_gate"):
        validate_inputs(memory, oracle)
