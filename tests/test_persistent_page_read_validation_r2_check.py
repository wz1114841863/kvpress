"""Synthetic acceptance tests only; these fixtures are not RTL execution evidence."""

import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from tests.test_persistent_page_read_validation_check import fixture as previous_fixture
from tools.check_persistent_page_read_validation_r2 import (
    FLOW, PARENT_MARKER, PARENT_SUITE, RUN_PASS, check, check_parent, write_preserved,
)


def fixture(root):
    previous_fixture(root)
    source_path = root / "workspace/source_manifest.json"
    source = json.loads(source_path.read_text())
    source["validation_flow"] = FLOW
    source_path.write_text(json.dumps(source))
    input_path = root / "input_manifest.json"
    inputs = json.loads(input_path.read_text())
    inputs.update(validation_flow=FLOW, parent_suite=PARENT_SUITE,
                  source_manifest_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest())
    input_path.write_text(json.dumps(inputs))
    (root / "parent_exit_status").write_text("0\n")
    (root / "parent_test.log").write_text(PARENT_MARKER + "\nAll tests passed.\n")
    report = root / "workspace/hardware/route_a/chisel/target/test-reports" / ("TEST-" + PARENT_SUITE + ".xml")
    report.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="real_parent"/></testsuite>')
    native = root / "workspace/hardware/route_a/chisel/build/chiselsim" / PARENT_SUITE.split(".")[-1] / "real_parent/workdir-verilator"
    native.mkdir(parents=True)
    (native / "simulation").write_bytes(b"\x7fELF" + b"synthetic parent fixture" * 100)
    (native / "compilation-log.txt").write_text("synthetic parent compilation\n")
    (native / "execution-script.txt").write_text("synthetic parent interaction\n")
    (native / "simulation-log.txt").write_text("")
    (root / "runner.log").write_text("KVZAP_PERSISTENT_READ_R2_PARENT_GATE_PASS tests=1\n" + RUN_PASS +
                                      "\nKVZAP_PERSISTENT_READ_OUTER_EXIT=0\n")
    snapshot = check_parent(root)
    write_preserved(root / "parent_gate_result.json", snapshot)
    return report, native


class ParentGatedQualificationTests(unittest.TestCase):
    def test_parent_plus_original_fourteen_are_all_required(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); fixture(root)
            result = check(root, require_outer=True)
            self.assertEqual(result["test_count"], 15)
            self.assertEqual(result["owner_unit_tests"], 6)
            self.assertEqual(len(result["reports"]), 7)
            self.assertEqual(len(result["native_simulations"]), 15)
            self.assertTrue(result["parent_gate_preserved"])
            self.assertTrue(result["final_tmux_wrapper_checked"])
            self.assertEqual(result["verdicts"]["continuous_full_decode"], "NOT_ESTABLISHED")

    def test_parent_gate_can_qualify_before_full_phase_exists(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); fixture(root)
            (root / "test_exit_status").unlink()
            (root / "test.log").unlink()
            self.assertEqual(check_parent(root)["tests"], 1)
            with self.assertRaises(FileNotFoundError):
                check(root)

    def test_parent_gate_rejects_nonzero_compile_or_parent_exit(self):
        for status in ("compile_exit_status", "parent_exit_status"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as name:
                root = Path(name); fixture(root)
                (root / status).write_text("1\n")
                with self.assertRaises(AssertionError):
                    check_parent(root)

    def test_parent_xml_requires_one_successful_executed_case(self):
        for change in ("tests", "failures", "errors", "skipped", "case_count"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as name:
                root = Path(name); report, _ = fixture(root)
                text = report.read_text()
                if change == "case_count":
                    text = text.replace("</testsuite>", '<testcase name="extra"/></testsuite>')
                else:
                    old = 'tests="1"' if change == "tests" else change + '="0"'
                    text = text.replace(old, change + ('="2"' if change == "tests" else '="1"'))
                report.write_text(text)
                with self.assertRaises(AssertionError):
                    check_parent(root)

    def test_parent_native_and_all_artifacts_must_exist(self):
        for change in ("bad_header", "missing", "missing_compile", "missing_script", "empty_script"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as name:
                root = Path(name); _, native = fixture(root)
                if change == "bad_header": (native / "simulation").write_bytes(b"not ELF" * 200)
                elif change == "missing": (native / "simulation").unlink()
                elif change == "missing_compile": (native / "compilation-log.txt").unlink()
                elif change == "missing_script": (native / "execution-script.txt").unlink()
                else: (native / "execution-script.txt").write_text("")
                with self.assertRaises(AssertionError):
                    check_parent(root)

    def test_parent_marker_requires_one_complete_typed_line(self):
        for replacement in ("", PARENT_MARKER.split()[0], PARENT_MARKER + "\n" + PARENT_MARKER,
                            'println("' + PARENT_MARKER + '")',
                            PARENT_MARKER.replace("queries=2", "queries=1")):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as name:
                root = Path(name); fixture(root)
                (root / "parent_test.log").write_text(replacement + "\nAll tests passed.\n")
                with self.assertRaises(AssertionError):
                    check_parent(root)

    def test_parent_snapshot_prevents_later_overwrite(self):
        for artifact in ("execution-script.txt", "simulation", "compilation-log.txt", "log"):
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as name:
                root = Path(name); _, native = fixture(root)
                path = root / "parent_test.log" if artifact == "log" else native / artifact
                with path.open("ab") as stream:
                    stream.write(b"later overwrite drift\n")
                with self.assertRaises(AssertionError):
                    check(root)
                with self.assertRaises(AssertionError):
                    write_preserved(root / "parent_gate_result.json", check_parent(root))

    def test_original_fourteen_strict_checks_are_retained(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); fixture(root)
            (root / "test_exit_status").write_text("1\n")
            with self.assertRaises(AssertionError):
                check(root)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); fixture(root)
            path = root / "test.log"
            path.write_text(path.read_text().replace("fault_delta=1", "fault_delta=0"))
            with self.assertRaises(AssertionError):
                check(root)

    def test_flow_and_parent_identity_must_match_the_frozen_input(self):
        for key, replacement in (("validation_flow", "old_flow"), ("parent_suite", "wrong.suite")):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as name:
                root = Path(name); fixture(root)
                path = root / "input_manifest.json"
                manifest = json.loads(path.read_text()); manifest[key] = replacement
                path.write_text(json.dumps(manifest))
                with self.assertRaises(AssertionError):
                    check_parent(root)

    def test_final_requires_new_pass_and_parent_gate_and_both_outer_exits(self):
        for change in ("runner_pass", "parent_gate", "outer", "tmux", "tmux_marker"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as name:
                root = Path(name); fixture(root)
                if change == "runner_pass":
                    path = root / "runner.log"; path.write_text(path.read_text().replace(RUN_PASS, "old-run-pass"))
                elif change == "parent_gate":
                    path = root / "runner.log"; path.write_text(path.read_text().replace("R2_PARENT_GATE_PASS tests=1", "R2_PARENT_GATE_PASS tests=0"))
                elif change == "tmux_marker": (root / "outer.log").write_text("KVZAP_PERSISTENT_READ_TMUX_WRAPPER_EXIT=1\n")
                else: (root / ("exit_status" if change == "outer" else "tmux_wrapper_exit_status")).write_text("1\n")
                with self.assertRaises(AssertionError):
                    check(root, require_outer=True)

    def test_parent_marker_matches_actual_scala_literal(self):
        root = Path(__file__).resolve().parents[1]
        source = root / "hardware/route_a/chisel/src/test/scala/kvpress/routea/r5/RouteAR5PersistentReadParentSpec.scala"
        actual = set()
        for expression in re.findall(r'println\(("[^"]*"(?:\s*\+\s*"[^"]*")*)\)', source.read_text()):
            actual.add("".join(re.findall(r'"([^"]*)"', expression)))
        self.assertIn(PARENT_MARKER, actual)


if __name__ == "__main__":
    unittest.main()
