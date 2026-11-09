"""Acceptance boundaries for diagnostic PASS versus continuous-function PASS."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.check_stage_a_continuation_probes import check, parse_records, qualify_records


def observations():
    common = dict(outcome="BLOCKED", bound_cycles="128", first_terminal="1", second_terminal="0",
                  no_fault="1", gate_compact="0", r5_stream_slots="16",
                  position_backing_external="1", numeric_correspondence="0", capability_pass="0",
                  publications="1", handoffs="1", consumer_commits="4", payload_write_commits="1",
                  payload_fragments="8", sidecar_fragments="1")
    return {
        "READ_REUSE": dict(common, case="READ_REUSE", blocker="ONE_SHOT_ACTIVATION",
                           second_attention_accepted="1", second_plan_accepted="1", r6_active="1",
                           s2_empty="1", page_live="1", binder_have_plan="1", binder_have_page_ready="0",
                           binder_have_member_stream="0", descriptor_requests="0", lease_requests="0"),
        "ADMISSION_REUSE": dict(common, case="ADMISSION_REUSE", blocker="INGRESS_DONE",
                                second_join_accepted="0", r6_context_valid="1", r6_authority_valid="1",
                                binding_valid="1", ingress_done="1"),
    }


def log_text(records):
    return "\n".join("KVZAP_STAGE_A_PROBE_RESULT " + " ".join(k + "=" + v for k, v in fields.items())
                     for fields in records.values())


def make_fixture(root):
    workspace = root / "workspace"
    workspace.mkdir()
    source = workspace / "retained-main.scala"
    source.write_text("unchanged production source\n")
    archive = root / "source.tar.gz"
    archive.write_bytes(b"test fixture archive identity")
    files = {source.name: dict(bytes=source.stat().st_size,
                              sha256=hashlib.sha256(source.read_bytes()).hexdigest())}
    source_manifest = workspace / "source_manifest.json"
    source_manifest.write_text(json.dumps(dict(files=files, source_commit="fixture")))
    (root / "input_manifest.json").write_text(json.dumps(dict(
        schema="stage-a-continuation-probe-input-1", archive=str(archive),
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        source_manifest_sha256=hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
        files=files, source_commit="fixture")))
    (root / "compile_exit_status").write_text("0\n")
    (root / "test_exit_status").write_text("0\n")
    (root / "test.log").write_text(log_text(observations()) + "\nAll tests passed.\n")
    reports = workspace / "hardware/route_a/chisel/target/test-reports"
    reports.mkdir(parents=True)
    report = reports / "TEST-kvpress.routea.RouteAStageAContinuationProbeSpec.xml"
    report.write_text('<testsuite tests="2" failures="0" errors="0" skipped="0">'
                      '<testcase name="read"/><testcase name="admission"/></testsuite>')
    return source, archive, report


class StageAProbeQualificationTests(unittest.TestCase):
    def test_qualified_blockers_remain_functionally_open(self):
        result = qualify_records(parse_records(log_text(observations())))
        self.assertEqual(result["build_and_probe_execution"], "PASS")
        self.assertEqual(result["continuous_functional_closure"], "NOT_ESTABLISHED")

    def test_timeout_without_positive_evidence_is_rejected(self):
        for key in ("second_attention_accepted", "second_plan_accepted", "r6_active", "page_live"):
            values = observations()
            values["READ_REUSE"][key] = "0"
            with self.subTest(key=key), self.assertRaises(AssertionError):
                qualify_records(values)

    def test_first_use_failure_is_not_a_repeat_blocker(self):
        for case in observations():
            values = observations()
            values[case]["first_terminal"] = "0"
            with self.subTest(case=case), self.assertRaises(AssertionError):
                qualify_records(values)

    def test_missing_duplicate_and_echoed_records_rejected(self):
        valid = log_text(observations())
        one = valid.splitlines()[0]
        for text in (one, valid + "\n" + one, 'println("' + one + '")'):
            with self.subTest(text=text[:60]), self.assertRaises(AssertionError):
                parse_records(text)

    def test_unexpected_progress_requires_review(self):
        for case, key in (("READ_REUSE", "descriptor_requests"), ("ADMISSION_REUSE", "second_join_accepted")):
            values = copy.deepcopy(observations())
            values[case][key] = "1"
            with self.subTest(case=case), self.assertRaises(AssertionError):
                qualify_records(values)

    def test_malformed_fields_rejected(self):
        valid = log_text(observations())
        for suffix in (" outcome=BLOCKED", " invalid", " x=1=2"):
            with self.subTest(suffix=suffix), self.assertRaises(AssertionError):
                parse_records(valid + suffix)

    def test_completed_evidence_retains_negative_functional_verdict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_fixture(root)
            self.assertEqual(check(root)["verdicts"]["continuous_functional_closure"], "NOT_ESTABLISHED")

    def test_source_or_archive_change_rejected(self):
        for change in ("source", "archive"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, archive, _ = make_fixture(root)
                (source if change == "source" else archive).write_bytes(b"changed")
                with self.assertRaises(AssertionError):
                    check(root)

    def test_native_failure_or_skipped_xml_cannot_be_overridden_by_pass_text(self):
        for change in ("compile", "test", "xml"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _, _, report = make_fixture(root)
                if change == "xml":
                    report.write_text(report.read_text().replace('skipped="0"', 'skipped="1"'))
                else:
                    (root / (change + "_exit_status")).write_text("1\n")
                with self.assertRaises(AssertionError):
                    check(root)


if __name__ == "__main__":
    unittest.main()
