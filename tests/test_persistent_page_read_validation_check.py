"""Small synthetic acceptance-boundary tests; these do not simulate the RTL."""

import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from tools.check_persistent_page_read_validation import CASES, OWNER_MARKERS, SUITES, check, parse_records, qualify_records


def observations():
    scope = dict(outcome="PASS", persistent_v2="1", gate_compact="0", r5_stream_slots="16",
                 position_backing_external="1", numeric_correspondence="0")
    normal = dict(publications="1", handoffs="1", payload_write_commits="1", payload_fragments="16",
                  sidecar_fragments="2", consumer_commits="8", terminals_ok="2", terminals_fault="0",
                  source_releases="2", s2_generation="2", page_generation="0", retired="1", reclaimed="1",
                  no_memory_fault="1")
    negative = dict(fault_delta="1", read_delta="0", release_delta="0", consumer_delta="0",
                    live_after="0", slot_state_after="0", first_terminal_ok="1", page_live="1", s2_generation="1")
    result = {}
    for case in CASES:
        result[case] = dict(scope, case=case)
        if case in ("SAME_PAGE_TWICE", "RETIRE_DURING_PREFLIGHT"):
            result[case].update(normal)
        else:
            result[case].update(negative)
    result["RETIRE_DURING_PREFLIGHT"].update(attention_accepted_before_retire="1", preflight_incomplete_at_retire="1")
    result["FOREIGN_DECLARATION"].update(fault_delta="0", reject_delta="1")
    return result


def log_text(records):
    lines = ["KVZAP_PERSISTENT_READ_RESULT " + " ".join(k + "=" + v for k, v in fields.items())
             for fields in records.values()]
    old = dict(outcome="BLOCKED", bound_cycles="128", first_terminal="1", second_terminal="0",
               no_fault="1", gate_compact="0", r5_stream_slots="16", position_backing_external="1",
               numeric_correspondence="0", capability_pass="0", publications="1", handoffs="1",
               consumer_commits="4", payload_write_commits="1", payload_fragments="8", sidecar_fragments="1")
    read = dict(old, case="READ_REUSE", blocker="ONE_SHOT_ACTIVATION", second_attention_accepted="1",
                second_plan_accepted="1", r6_active="1", s2_empty="1", page_live="1", binder_have_plan="1",
                binder_have_page_ready="0", binder_have_member_stream="0", descriptor_requests="0", lease_requests="0")
    admission = dict(old, case="ADMISSION_REUSE", blocker="INGRESS_DONE", r6_context_valid="1",
                     r6_authority_valid="1", binding_valid="1", ingress_done="1", second_join_accepted="0")
    lines += ["KVZAP_STAGE_A_PROBE_RESULT " + " ".join(k + "=" + v for k, v in fields.items())
              for fields in (read, admission)]
    lines += list(OWNER_MARKERS) + ["All tests passed."]
    return "\n".join(lines) + "\n"


def fixture(root):
    workspace = root / "workspace"
    workspace.mkdir()
    source = workspace / "fixture.scala"
    source.write_text("synthetic acceptance fixture, never real RTL evidence\n")
    archive = root / "source.tar.gz"
    archive.write_bytes(b"synthetic archive identity")
    files = {source.name: dict(bytes=source.stat().st_size, sha256=hashlib.sha256(source.read_bytes()).hexdigest())}
    manifest_path = workspace / "source_manifest.json"
    manifest_path.write_text(json.dumps(dict(schema="persistent-page-read-source-1", feature="persistent_page_read_v2",
                                             source_commit="fixture", files=files)))
    (root / "input_manifest.json").write_text(json.dumps(dict(schema="persistent-page-read-input-1",
        feature="persistent_page_read_v2", source_commit="fixture", files=files, archive=str(archive),
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        source_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())))
    for status in ("compile_exit_status", "test_exit_status", "exit_status", "tmux_wrapper_exit_status"):
        (root / status).write_text("0\n")
    (root / "test.log").write_text(log_text(observations()))
    (root / "runner.log").write_text("KVZAP_PERSISTENT_READ_FUNCTIONAL_RUN_PASS_SINGLE_GROUP_NOT_FULL_DECODE\n"
                                      "KVZAP_PERSISTENT_READ_OUTER_EXIT=0\n")
    (root / "outer.log").write_text("KVZAP_PERSISTENT_READ_TMUX_WRAPPER_EXIT=0\n")
    reports = workspace / "hardware/route_a/chisel/target/test-reports"
    reports.mkdir(parents=True)
    for suite, tests in SUITES.items():
        report = '<testsuite tests="%d" failures="0" errors="0" skipped="0">' % tests
        report += "".join('<testcase name="case_%d"/>' % i for i in range(tests)) + "</testsuite>"
        (reports / ("TEST-" + suite + ".xml")).write_text(report)
        for i in range(tests):
            build = workspace / "hardware/route_a/chisel/build/chiselsim" / suite.split(".")[-1] / ("case_%d" % i) / "workdir-verilator"
            build.mkdir(parents=True)
            # This deliberately synthetic header tests gating only, not execution evidence.
            (build / "simulation").write_bytes(b"\x7fELF" + b"synthetic fixture" * 100)
            (build / "compilation-log.txt").write_text("synthetic compile fixture\n")
            (build / "execution-script.txt").write_text("synthetic execution fixture\n")
            (build / "simulation-log.txt").write_text("")
    return source, archive


class PersistentReadQualificationTests(unittest.TestCase):
    def test_bounded_success_keeps_full_decode_and_numeric_open(self):
        verdict = qualify_records(parse_records(log_text(observations())))
        self.assertEqual(verdict["continuous_full_decode"], "NOT_ESTABLISHED")
        self.assertEqual(verdict["numerical_correspondence"], "NOT_ESTABLISHED")

    def test_repeat_must_have_one_real_write_two_services_and_final_reclaim(self):
        for key in ("payload_write_commits", "payload_fragments", "source_releases", "s2_generation", "retired", "reclaimed"):
            records = observations(); records["SAME_PAGE_TWICE"][key] = "0"
            with self.subTest(key=key), self.assertRaises(AssertionError):
                qualify_records(records)

    def test_fault_without_first_use_or_with_resource_side_effect_is_rejected(self):
        for key, value in (("first_terminal_ok", "0"), ("read_delta", "1"), ("release_delta", "1"),
                           ("live_after", "1"), ("slot_state_after", "1"), ("fault_delta", "0")):
            records = observations(); records["BAD_OWNER"][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                qualify_records(records)

    def test_foreign_identity_cannot_create_a_terminal(self):
        records = observations(); records["FOREIGN_DECLARATION"]["fault_delta"] = "1"
        with self.assertRaises(AssertionError):
            qualify_records(records)

    def test_missing_duplicate_and_echoed_observation_is_rejected(self):
        log = log_text(observations()); line = log.splitlines()[0]
        for text in (line, log + line + "\n", log.replace(line, 'println("' + line + '")')):
            with self.subTest(text=text[:40]), self.assertRaises(AssertionError):
                parse_records(text)

    def test_complete_synthetic_evidence_exercises_acceptance(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); fixture(root)
            result = check(root, require_outer=True)
            self.assertEqual(result["test_count"], sum(SUITES.values()))
            self.assertEqual(result["test_count"], 14)
            self.assertEqual(result["owner_unit_tests"], 5)
            self.assertTrue(result["final_tmux_wrapper_checked"])
            self.assertEqual(result["legacy_diagnostic_verdicts"]["multi_group_admission"], "BLOCKED_CURRENT_RTL_IN_BOUNDED_PROBE")

    def test_source_archive_native_and_native_count_drift_is_rejected(self):
        for change in ("source", "archive", "native_header", "native_missing"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as name:
                root = Path(name); source, archive = fixture(root)
                if change in ("source", "archive"):
                    (source if change == "source" else archive).write_bytes(b"changed")
                else:
                    executable = next((root / "workspace/hardware/route_a/chisel/build/chiselsim").glob("*/*/workdir-verilator/simulation"))
                    if change == "native_missing": executable.unlink()
                    else: executable.write_bytes(b"not an ELF" * 200)
                with self.assertRaises(AssertionError):
                    check(root)

    def test_native_failure_skip_or_nonzero_outer_is_rejected(self):
        for change in ("compile", "test", "xml", "outer", "tmux", "tmux_marker"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as name:
                root = Path(name); fixture(root)
                if change == "xml":
                    path = next((root / "workspace/hardware/route_a/chisel/target/test-reports").glob("*.xml"))
                    path.write_text(path.read_text().replace('skipped="0"', 'skipped="1"'))
                elif change == "tmux_marker":
                    (root / "outer.log").write_text("KVZAP_PERSISTENT_READ_TMUX_WRAPPER_EXIT=1\n")
                else:
                    path = root / ("exit_status" if change == "outer" else change + "_exit_status")
                    if change == "tmux": path = root / "tmux_wrapper_exit_status"
                    path.write_text("1\n")
                with self.assertRaises(AssertionError):
                    check(root, require_outer=True)

    def test_owner_observations_require_the_full_typed_line(self):
        for marker in OWNER_MARKERS:
            for replacement in ("", marker.split()[0] if " " in marker else marker + " extra=1"):
                with self.subTest(marker=marker, replacement=replacement), tempfile.TemporaryDirectory() as name:
                    root = Path(name); fixture(root)
                    path = root / "test.log"
                    path.write_text(path.read_text().replace(marker + "\n", replacement + "\n"))
                    with self.assertRaises(AssertionError):
                        check(root)

    def test_old_S2_invalid_count_cannot_qualify_new_priority_case(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); fixture(root)
            path = root / "test.log"
            path.write_text(path.read_text().replace("S2_OWNER_PASS invalid=4", "S2_OWNER_PASS invalid=3"))
            with self.assertRaises(AssertionError):
                check(root)

    def test_expected_owner_markers_match_actual_scala_print_literals(self):
        root = Path(__file__).resolve().parents[1]
        sources = [root / "hardware/route_a/chisel/src/test/scala/kvpress/routea" / relative for relative in
                   ("RouteAS2PersistentReservationSpec.scala", "RouteAPersistentPackedReadControllerSpec.scala",
                    "r5/RouteAR5PersistentReadAvailabilitySpec.scala")]
        actual = set()
        for source in sources:
            for expression in re.findall(r'println\(("[^"]*"(?:\s*\+\s*"[^"]*")*)\)', source.read_text()):
                actual.add("".join(re.findall(r'"([^"]*)"', expression)))
        for marker in OWNER_MARKERS:
            self.assertIn(marker, actual, "postcheck marker differs from an actual Scala println")


if __name__ == "__main__":
    unittest.main()
