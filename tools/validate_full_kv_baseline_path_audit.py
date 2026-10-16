#!/usr/bin/env python3
"""Validate the bounded Full-KV path audit and W0 implementation package."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "analysis/full_kv_baseline_path_audit_20261016.json"
DOC = ROOT / "analysis/full_kv_baseline_path_audit_20261016.md"
MATRIX = ROOT / "analysis/measurement_baseline_matrix.json"
CANDIDATE = ROOT / "analysis/measurement_realization_candidate_manifest.json"


def main() -> int:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    assert audit["schema_version"] == "kvzap-route-a-full-kv-baseline-path-audit-1.0"
    assert audit["status"] == "targeted_source_audit_complete_rtl_work_package_pending_user_authorization"
    assert matrix["status"] == "baseline_planning_approved_for_limited_chisel_measurement_dut_preparation"
    assert candidate["status"] == "candidate_preparation_scope_approved_for_bounded_chisel_work_package"
    assert "no further MBR review is required" in audit["approval_record"]
    paths = {item["id"]: item for item in audit["path_audit"]}
    assert set(paths) == {"read_request_producer_to_r2_r1", "memory_response_to_s2_ready", "source_completion_to_consumers_terminal_retire"}
    assert all(item["status"].startswith("open_missing") for item in paths.values())
    assert "RouteAPackedS2ReadProducer" in paths["read_request_producer_to_r2_r1"]["forbidden_shortcut"]
    assert "PageRef/sidecar/source identity" in paths["memory_response_to_s2_ready"]["forbidden_shortcut"]
    assert "R4 merge" in paths["source_completion_to_consumers_terminal_retire"]["forbidden_shortcut"]
    package = audit["work_package"]
    assert package["id"] == "dual_measurement_dut_w0_full_kv_legal_path"
    assert len(package["new_scala_files"]) == 5
    assert "DC" in package["excluded"] and "CACTI" in package["excluded"]
    assert package["next_gate"] == "explicit user authorization to implement W0 Chisel files"

    doc = DOC.read_text(encoding="utf-8")
    for phrase in [
        "MBR.0, MBR.1, and\nMBR.1-A are approved and are not reopened here.",
        "insufficient for direct integration",
        "First concrete dual-DUT Chisel integration work package",
        "FullKVReadProducer",
        "FullKVS2ReadEndpoint",
        "FullKVTerminalRetireAdapter",
        "No further\nMBR review or new overall planning phase is required.",
        "W0 is ready for a direct user authorization",
    ]:
        assert phrase in doc, phrase
    print("PASS: Full-KV path gaps and W0 Chisel scope are explicit and bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
