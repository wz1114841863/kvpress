#!/usr/bin/env python3
"""Qualify current-RTL blocker diagnostics, separately from functional success."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


PREFIX = "KVZAP_STAGE_A_PROBE_RESULT"
CASES = {"READ_REUSE", "ADMISSION_REUSE"}
SUITE = "kvpress.routea.RouteAStageAContinuationProbeSpec"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_records(log):
    records = {}
    for line in log.splitlines():
        match = re.fullmatch(r"(?:\[info\] )?" + PREFIX + r" (.+)", line)
        if not match:
            continue
        fields = {}
        for token in match.group(1).split():
            assert token.count("=") == 1, "malformed probe field: " + token
            key, value = token.split("=", 1)
            assert key and value and key not in fields, "duplicate/empty probe field"
            fields[key] = value
        case = fields.get("case")
        assert case in CASES and case not in records, "unexpected/duplicate probe case"
        records[case] = fields
    assert set(records) == CASES, "both independent probe records are required"
    return records


def qualify_records(records):
    """These pinned probes expect specific bounded current-RTL blockers."""
    assert set(records) == CASES
    for case, fields in records.items():
        assert fields["case"] == case
        assert fields["outcome"] == "BLOCKED", "unexpected outcome needs separate review"
        assert int(fields["bound_cycles"]) > 0
        assert fields["first_terminal"] == "1", "first-use prerequisite did not complete"
        assert fields["second_terminal"] == "0"
        for key, value in (("no_fault", "1"), ("gate_compact", "0"),
                           ("r5_stream_slots", "16"), ("position_backing_external", "1"),
                           ("numeric_correspondence", "0"), ("capability_pass", "0"),
                           ("publications", "1"), ("handoffs", "1"),
                           ("consumer_commits", "4"), ("payload_write_commits", "1"),
                           ("payload_fragments", "8"), ("sidecar_fragments", "1")):
            assert fields[key] == value, "unexpected fixture/scope evidence: " + key

    read = records["READ_REUSE"]
    assert read["blocker"] == "ONE_SHOT_ACTIVATION"
    for key in ("second_attention_accepted", "second_plan_accepted", "r6_active",
                "s2_empty", "page_live", "binder_have_plan"):
        assert read[key] == "1", "missing positive READ_REUSE evidence: " + key
    for key in ("binder_have_page_ready", "binder_have_member_stream",
                "descriptor_requests", "lease_requests"):
        assert read[key] == "0", "inconsistent READ_REUSE blocker: " + key

    admission = records["ADMISSION_REUSE"]
    assert admission["blocker"] == "INGRESS_DONE"
    for key in ("r6_context_valid", "r6_authority_valid", "binding_valid", "ingress_done"):
        assert admission[key] == "1", "missing held ADMISSION_REUSE input: " + key
    assert admission["second_join_accepted"] == "0"
    return {
        "build_and_probe_execution": "PASS",
        "same_page_reuse": "BLOCKED_CURRENT_RTL_IN_BOUNDED_PROBE",
        "multi_group_admission": "BLOCKED_CURRENT_RTL_IN_BOUNDED_PROBE",
        "continuous_functional_closure": "NOT_ESTABLISHED",
        "numeric_data_correspondence": "NOT_ESTABLISHED",
        "final_retire_reclaim_in_new_probes": "NOT_REACHED_AFTER_BLOCKER",
    }


def check(root):
    root = Path(root)
    manifest = json.loads((root / "input_manifest.json").read_text())
    workspace = root / "workspace"
    assert manifest["schema"] == "stage-a-continuation-probe-input-1"
    assert digest(manifest["archive"]) == manifest["archive_sha256"]
    assert digest(workspace / "source_manifest.json") == manifest["source_manifest_sha256"]
    source_manifest = json.loads((workspace / "source_manifest.json").read_text())
    assert source_manifest["files"] == manifest["files"]
    assert source_manifest["source_commit"] == manifest["source_commit"]
    for name, expected in manifest["files"].items():
        path = workspace / name
        assert path.stat().st_size == expected["bytes"] and digest(path) == expected["sha256"], name
    assert (root / "compile_exit_status").read_text().strip() == "0"
    assert (root / "test_exit_status").read_text().strip() == "0"
    report_path = workspace / "hardware/route_a/chisel/target/test-reports" / ("TEST-" + SUITE + ".xml")
    report = ET.parse(str(report_path)).getroot()
    assert int(report.attrib["tests"]) == 2
    assert all(int(report.attrib.get(k, "0")) == 0 for k in ("failures", "errors", "skipped"))
    assert len(list(report.iter("testcase"))) == 2
    log = (root / "test.log").read_text()
    assert "All tests passed." in log
    records = parse_records(log)
    verdicts = qualify_records(records)
    return {
        "schema": "stage-a-continuation-probe-result-1",
        "source_commit": manifest["source_commit"],
        "archive_sha256": manifest["archive_sha256"],
        "tests": 2,
        "verdicts": verdicts,
        "observations": records,
        "xml_sha256": digest(report_path),
        "test_log_sha256": digest(root / "test.log"),
        "source_files_checked": len(manifest["files"]),
        "scope": "bounded diagnostic reproduction only; no RTL repair, full-anchor execution, numeric correctness, timing, area or net-benefit claim",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="completed isolated probe root")
    args = parser.parse_args()
    result = check(args.root)
    (args.root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("KVZAP_STAGE_A_PROBES_POSTCHECK_PASS diagnostic_tests=2 continuous_functional_closure=NOT_ESTABLISHED")


if __name__ == "__main__":
    main()
