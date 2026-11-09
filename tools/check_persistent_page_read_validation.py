#!/usr/bin/env python3
"""Qualify persistent-page functional tests, native artifacts and v1 regressions."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

try:
    from tools.check_stage_a_continuation_probes import parse_records as parse_old_records
    from tools.check_stage_a_continuation_probes import qualify_records as qualify_old_records
except ImportError:  # Direct script execution places tools/, rather than its parent, on sys.path.
    from check_stage_a_continuation_probes import parse_records as parse_old_records
    from check_stage_a_continuation_probes import qualify_records as qualify_old_records


PREFIX = "KVZAP_PERSISTENT_READ_RESULT"
CASES = {"SAME_PAGE_TWICE", "BAD_PAGE_GENERATION", "BAD_OWNER", "BAD_S2_SLOT",
         "BAD_S2_GENERATION", "FOREIGN_DECLARATION", "RETIRE_DURING_PREFLIGHT"}
SUITES = {"kvpress.routea.RouteAPersistentPageReadSpec": 3,
          "kvpress.routea.RouteAS2PersistentReservationSpec": 1,
          "kvpress.routea.r5.RouteAR5PersistentReadAvailabilitySpec": 1,
          "kvpress.routea.RouteAPersistentPackedReadControllerSpec": 3,
          "kvpress.routea.RouteAMeasurementDutR3Spec": 4,
          "kvpress.routea.RouteAStageAContinuationProbeSpec": 2}
OWNER_MARKERS = (
    "KVZAP_PERSISTENT_AVAILABILITY_CLEAR_HOLD_STALE_PASS",
    "PERSISTENT_READ_V2_PREFLIGHT_BACKPRESSURE_PASS plan_accepts=1 queries=1 reservations=1 demands=1 owner_mocks=1",
    "PERSISTENT_READ_V2_PREFLIGHT_REJECTION_PASS live_faults=1 foreign_faults=0 cancels=2 reservations=0 owner_mocks=1",
    "PERSISTENT_READ_V2_R6_NO_REPLAN_PASS real_r6=1 mocked_source_release=1 eligible_after_release=0 duplicate_plan_ready=0",
    "KVZAP_PERSISTENT_READ_S2_OWNER_PASS invalid=4 busy=1 granted=1 held_cycles=16 generation=1 "
    "R6_authorization_integration=WHOLE_DUT_TEST real_fill_or_reclaim=NOT_TESTED_IN_THIS_UNIT",
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_record(path, root):
    return dict(path=str(path.relative_to(root)), bytes=path.stat().st_size, sha256=digest(path))


def parse_records(log):
    records = {}
    for line in log.splitlines():
        match = re.fullmatch(r"(?:\[info\] )?" + PREFIX + r" (.+)", line)
        if not match:
            continue
        fields = {}
        for token in match.group(1).split():
            assert token.count("=") == 1, "malformed result field: " + token
            key, value = token.split("=", 1)
            assert key and value and key not in fields, "duplicate/empty result field"
            fields[key] = value
        case = fields.get("case")
        assert case in CASES and case not in records, "unexpected/duplicate persistent read case"
        records[case] = fields
    assert set(records) == CASES, "all persistent read observations are required"
    return records


def qualify_records(records):
    assert set(records) == CASES
    for case, fields in records.items():
        assert fields["case"] == case and fields["outcome"] == "PASS"
        for key, value in (("persistent_v2", "1"), ("gate_compact", "0"),
                           ("r5_stream_slots", "16"), ("position_backing_external", "1"),
                           ("numeric_correspondence", "0")):
            assert fields[key] == value, "unexpected fixture/scope evidence: " + key
    for case in ("SAME_PAGE_TWICE", "RETIRE_DURING_PREFLIGHT"):
        fields = records[case]
        for key, value in (("publications", "1"), ("handoffs", "1"),
                           ("payload_write_commits", "1"), ("payload_fragments", "16"),
                           ("sidecar_fragments", "2"), ("consumer_commits", "8"),
                           ("terminals_ok", "2"), ("terminals_fault", "0"),
                           ("source_releases", "2"), ("s2_generation", "2"),
                           ("page_generation", "0"), ("retired", "1"),
                           ("reclaimed", "1"), ("no_memory_fault", "1")):
            assert fields[key] == value, case + " incomplete lifecycle/data evidence: " + key
    assert records["RETIRE_DURING_PREFLIGHT"]["attention_accepted_before_retire"] == "1"
    assert records["RETIRE_DURING_PREFLIGHT"]["preflight_incomplete_at_retire"] == "1"
    for case in ("BAD_PAGE_GENERATION", "BAD_OWNER", "BAD_S2_SLOT", "BAD_S2_GENERATION"):
        fields = records[case]
        for key, value in (("fault_delta", "1"), ("read_delta", "0"),
                           ("release_delta", "0"), ("consumer_delta", "0"),
                           ("live_after", "0"), ("slot_state_after", "0"),
                           ("first_terminal_ok", "1"), ("page_live", "1"), ("s2_generation", "1")):
            assert fields[key] == value, case + " incomplete fail-closed evidence: " + key
    foreign = records["FOREIGN_DECLARATION"]
    for key, value in (("fault_delta", "0"), ("read_delta", "0"), ("release_delta", "0"),
                       ("consumer_delta", "0"), ("live_after", "0"),
                       ("slot_state_after", "0"), ("reject_delta", "1"),
                       ("first_terminal_ok", "1"), ("page_live", "1")):
        assert foreign[key] == value, "foreign declaration made/retained owner state: " + key
    return dict(same_page_repeat="PASS_BOUNDED_FUNCTIONAL_V2", errors="PASS_BOUNDED_FAIL_CLOSED_V2",
                retire_drain="PASS_BOUNDED_FUNCTIONAL_V2", multi_group_admission="UNCHANGED_NOT_IMPLEMENTED",
                continuous_full_decode="NOT_ESTABLISHED", numerical_correspondence="NOT_ESTABLISHED",
                area_timing_PPA_net_benefit="NO_NEW_EVIDENCE")


def check(root, require_outer=False):
    root = Path(root)
    workspace = root / "workspace"
    manifest = json.loads((root / "input_manifest.json").read_text())
    assert manifest["schema"] == "persistent-page-read-input-1"
    assert manifest["feature"] == "persistent_page_read_v2"
    assert digest(manifest["archive"]) == manifest["archive_sha256"]
    source_path = workspace / "source_manifest.json"
    assert digest(source_path) == manifest["source_manifest_sha256"]
    source = json.loads(source_path.read_text())
    assert source["schema"] == "persistent-page-read-source-1"
    assert source["feature"] == manifest["feature"] and source["source_commit"] == manifest["source_commit"]
    assert source["files"] == manifest["files"]
    for name, expected in manifest["files"].items():
        relative = Path(name)
        assert not relative.is_absolute() and ".." not in relative.parts
        assert "target" not in relative.parts and "build" not in relative.parts
        path = workspace / relative
        assert path.stat().st_size == expected["bytes"] and digest(path) == expected["sha256"], name
    assert (root / "compile_exit_status").read_text().strip() == "0"
    assert (root / "test_exit_status").read_text().strip() == "0"
    reports = {}
    native = []
    for suite, expected_tests in SUITES.items():
        path = workspace / "hardware/route_a/chisel/target/test-reports" / ("TEST-" + suite + ".xml")
        report = ET.parse(str(path)).getroot()
        assert int(report.attrib["tests"]) == expected_tests, suite
        assert all(int(report.attrib.get(k, "0")) == 0 for k in ("failures", "errors", "skipped")), suite
        cases = list(report.iter("testcase"))
        assert len(cases) == expected_tests and len({x.attrib["name"] for x in cases}) == expected_tests
        reports[suite] = file_record(path, root)
        native_root = workspace / "hardware/route_a/chisel/build/chiselsim" / suite.split(".")[-1]
        simulations = sorted(native_root.glob("*/workdir-verilator/simulation"))
        assert len(simulations) == expected_tests, "missing/unexpected native builds: " + suite
        for executable in simulations:
            with executable.open("rb") as stream:
                assert stream.read(4) == b"\x7fELF", str(executable)
            assert executable.stat().st_size > 1024
            artifacts = [executable] + [executable.parent / name for name in
                                      ("compilation-log.txt", "simulation-log.txt", "execution-script.txt")]
            assert all(x.is_file() for x in artifacts)
            assert artifacts[1].stat().st_size > 0 and artifacts[3].stat().st_size > 0
            native.append(dict(suite=suite,files=[file_record(x, root) for x in artifacts]))
    log = (root / "test.log").read_text()
    assert "All tests passed." in log
    records = parse_records(log)
    verdicts = qualify_records(records)
    legacy = qualify_old_records(parse_old_records(log))
    for marker in OWNER_MARKERS:
        assert len(re.findall(r"^(?:\[info\] )?" + re.escape(marker) + r"$", log, re.M)) == 1, marker
    outer_evidence = None
    if require_outer:
        assert (root / "exit_status").read_text().strip() == "0"
        assert (root / "tmux_wrapper_exit_status").read_text().strip() == "0"
        runner = (root / "runner.log").read_text()
        outer = (root / "outer.log").read_text()
        assert len(re.findall(r"^KVZAP_PERSISTENT_READ_OUTER_EXIT=0$", runner, re.M)) == 1
        assert len(re.findall(r"^KVZAP_PERSISTENT_READ_FUNCTIONAL_RUN_PASS_SINGLE_GROUP_NOT_FULL_DECODE$", runner, re.M)) == 1
        assert len(re.findall(r"^KVZAP_PERSISTENT_READ_TMUX_WRAPPER_EXIT=0$", outer, re.M)) == 1
        outer_evidence = {name: file_record(root / name, root) for name in
                          ("exit_status", "tmux_wrapper_exit_status", "runner.log", "outer.log")}
    return dict(schema="persistent-page-read-result-1", source_commit=manifest["source_commit"],
                archive_sha256=manifest["archive_sha256"], source_files_checked=len(manifest["files"]),
                test_count=sum(SUITES.values()), reports=reports, native_simulations=native,
                observations=records, verdicts=verdicts, legacy_diagnostic_verdicts=legacy,
                default_v1_R3_tests=4, default_v1_blocker_tests=2, successor_v2_tests=3, owner_unit_tests=5,
                final_outer_checked=require_outer, final_tmux_wrapper_checked=require_outer,
                outer_evidence=outer_evidence, test_log_sha256=digest(root / "test.log"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="isolated functional validation root")
    parser.add_argument("--final", action="store_true", help="also require completed outer exit/PASS markers")
    args = parser.parse_args()
    result = check(args.root, require_outer=args.final)
    output = args.root / ("result_final.json" if args.final else "result.json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("KVZAP_PERSISTENT_READ_POSTCHECK_PASS tests=%d successor=3 owner=5 legacy=6 full_decode=NOT_ESTABLISHED" % result["test_count"])


if __name__ == "__main__":
    main()
