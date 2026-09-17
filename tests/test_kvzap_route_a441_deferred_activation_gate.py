import json

import pytest

from tools.run_kvzap_qwen_a441_deferred_activation_gate import read_completed_a435


def test_a441_requires_complete_three_workload_a435_source(tmp_path):
    report = tmp_path / "a435.json"
    report.write_text(json.dumps({
        "schema_version": "kvzap-route-a435-microevent-quantum-sweep-1.0",
        "status": "complete",
        "config": {"admission_budgets": [1, 8, 32]},
        "per_workload_rows": [{"preset": name} for name in ("retrieval", "summarization", "reasoning")],
    }), encoding="utf-8")
    assert read_completed_a435(report)["status"] == "complete"


def test_a441_rejects_incomplete_or_wrong_quantum_a435_source(tmp_path):
    report = tmp_path / "bad.json"
    report.write_text(json.dumps({
        "schema_version": "kvzap-route-a435-microevent-quantum-sweep-1.0",
        "status": "complete",
        "config": {"admission_budgets": [1, 32]},
        "per_workload_rows": [],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Q="):
        read_completed_a435(report)
