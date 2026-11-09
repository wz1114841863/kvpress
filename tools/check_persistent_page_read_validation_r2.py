#!/usr/bin/env python3
"""Qualify the real R5-parent gate and the unchanged fourteen-test v2/v1 closure."""

import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

try:
    from tools import check_persistent_page_read_validation as previous
except ImportError:
    import check_persistent_page_read_validation as previous


FLOW = "r2_parent_gate"
PARENT_SUITE = "kvpress.routea.r5.RouteAR5PersistentReadParentSpec"
# Kept in exact agreement with the parent suite's literal printed observation.
PARENT_MARKER = ("KVZAP_PERSISTENT_READ_R5_PARENT_PASS real_parent=1 allocations=2 marks=1 queries=2 "
                 "scan_overlap=1 held_result_cycles=4 ghost_scan_outstanding=0 owner_facts_mocked=1")
RUN_PASS = "KVZAP_PERSISTENT_READ_R2_FUNCTIONAL_RUN_PASS_SINGLE_GROUP_NOT_FULL_DECODE"


def identity(root):
    workspace = root / "workspace"
    manifest = json.loads((root / "input_manifest.json").read_text())
    assert manifest["schema"] == "persistent-page-read-input-1"
    assert manifest["feature"] == "persistent_page_read_v2"
    assert manifest["validation_flow"] == FLOW
    assert manifest["parent_suite"] == PARENT_SUITE
    assert previous.digest(manifest["archive"]) == manifest["archive_sha256"]
    source_path = workspace / "source_manifest.json"
    assert previous.digest(source_path) == manifest["source_manifest_sha256"]
    source = json.loads(source_path.read_text())
    assert source["schema"] == "persistent-page-read-source-1"
    assert source["feature"] == manifest["feature"]
    assert source["validation_flow"] == FLOW
    assert source["source_commit"] == manifest["source_commit"]
    assert source["files"] == manifest["files"]
    for name, expected in manifest["files"].items():
        relative = Path(name)
        assert not relative.is_absolute() and ".." not in relative.parts
        assert "target" not in relative.parts and "build" not in relative.parts
        path = workspace / relative
        assert path.stat().st_size == expected["bytes"]
        assert previous.digest(path) == expected["sha256"], name
    return manifest


def check_parent(root):
    root = Path(root)
    manifest = identity(root)
    assert (root / "compile_exit_status").read_text().strip() == "0"
    assert (root / "parent_exit_status").read_text().strip() == "0"
    log = (root / "parent_test.log").read_text()
    assert "All tests passed." in log
    assert len(re.findall(r"^(?:\[info\] )?" + re.escape(PARENT_MARKER) + r"$", log, re.M)) == 1
    workspace = root / "workspace"
    report_path = workspace / "hardware/route_a/chisel/target/test-reports" / ("TEST-" + PARENT_SUITE + ".xml")
    report = ET.parse(str(report_path)).getroot()
    assert int(report.attrib["tests"]) == 1
    assert all(int(report.attrib.get(key, "0")) == 0 for key in ("failures", "errors", "skipped"))
    cases = list(report.iter("testcase"))
    assert len(cases) == 1
    native_root = workspace / "hardware/route_a/chisel/build/chiselsim" / PARENT_SUITE.split(".")[-1]
    simulations = sorted(native_root.glob("*/workdir-verilator/simulation"))
    assert len(simulations) == 1, "one fresh real-parent native build is required"
    executable = simulations[0]
    with executable.open("rb") as stream:
        assert stream.read(4) == b"\x7fELF"
    assert executable.stat().st_size > 1024
    artifacts = [executable] + [executable.parent / name for name in
                               ("compilation-log.txt", "simulation-log.txt", "execution-script.txt")]
    assert all(path.is_file() for path in artifacts)
    assert artifacts[1].stat().st_size > 0 and artifacts[3].stat().st_size > 0
    return dict(schema="persistent-page-read-r2-parent-gate-1", validation_flow=FLOW,
                source_commit=manifest["source_commit"], archive_sha256=manifest["archive_sha256"],
                source_files_checked=len(manifest["files"]), tests=1,
                marker=PARENT_MARKER, report=previous.file_record(report_path, root),
                native=[previous.file_record(path, root) for path in artifacts],
                log=previous.file_record(root / "parent_test.log", root),
                phase_exit=previous.file_record(root / "parent_exit_status", root))


def check(root, require_outer=False):
    root = Path(root)
    parent = check_parent(root)
    saved = json.loads((root / "parent_gate_result.json").read_text())
    assert saved == parent, "the parent gate artifact set changed after it qualified"
    # Retain every source/native/XML/typed-observation requirement of r1.
    # The parent suite runs separately and is intentionally absent from the
    # following fourteen-suite testOnly command, preserving its first result.
    result = previous.check(root, require_outer=False)
    assert result["source_commit"] == parent["source_commit"]
    assert result["archive_sha256"] == parent["archive_sha256"]
    result["schema"] = "persistent-page-read-r2-result-1"
    result["validation_flow"] = FLOW
    result["parent_gate"] = parent
    result["reports"][PARENT_SUITE] = parent["report"]
    result["native_simulations"].append(dict(suite=PARENT_SUITE, files=parent["native"]))
    result["test_count"] += parent["tests"]
    result["owner_unit_tests"] += parent["tests"]
    assert result["test_count"] == 15 and result["owner_unit_tests"] == 6
    result["parent_gate_preserved"] = True
    result["final_outer_checked"] = require_outer
    result["final_tmux_wrapper_checked"] = require_outer
    result["outer_evidence"] = None
    if require_outer:
        assert (root / "exit_status").read_text().strip() == "0"
        assert (root / "tmux_wrapper_exit_status").read_text().strip() == "0"
        runner = (root / "runner.log").read_text()
        outer = (root / "outer.log").read_text()
        for marker in ("KVZAP_PERSISTENT_READ_OUTER_EXIT=0", RUN_PASS,
                       "KVZAP_PERSISTENT_READ_R2_PARENT_GATE_PASS tests=1"):
            assert len(re.findall(r"^" + re.escape(marker) + r"$", runner, re.M)) == 1, marker
        assert len(re.findall(r"^KVZAP_PERSISTENT_READ_TMUX_WRAPPER_EXIT=0$", outer, re.M)) == 1
        result["outer_evidence"] = {name: previous.file_record(root / name, root) for name in
                                    ("exit_status", "tmux_wrapper_exit_status", "runner.log", "outer.log")}
    return result


def write_preserved(path, result):
    if path.exists():
        assert json.loads(path.read_text()) == result, "refusing to overwrite a different qualification result"
    else:
        path.write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="new isolated r2 functional validation root")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--parent-only", action="store_true", help="qualify and snapshot only the first real R5-parent phase")
    modes.add_argument("--final", action="store_true", help="also require successful runner and tmux outer completion")
    args = parser.parse_args()
    if sys.flags.optimize:
        raise RuntimeError("qualification requires Python assertions enabled")
    if args.parent_only:
        result = check_parent(args.root)
        write_preserved(args.root / "parent_gate_result.json", result)
        print("KVZAP_PERSISTENT_READ_R2_PARENT_GATE_PASS tests=1")
    else:
        result = check(args.root, require_outer=args.final)
        write_preserved(args.root / ("result_final.json" if args.final else "result.json"), result)
        print("KVZAP_PERSISTENT_READ_R2_POSTCHECK_PASS tests=15 successor=3 owner=6 legacy=6 full_decode=NOT_ESTABLISHED")


if __name__ == "__main__":
    main()
