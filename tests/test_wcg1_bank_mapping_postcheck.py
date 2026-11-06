"""Ensure invalid STA evidence cannot masquerade as a successful WCG1 result."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wcg1_mapping", ROOT / "tools/check_wcg1_bank_mapping.py")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def fixture(root):
    for side in ("reference", "gated"):
        directory = root / side
        directory.mkdir()
        (directory / "native.log").write_text(f"KVZAP_WCG1_SIDE_RUN_PASS side={side}\n")
        (directory / "exit_status").write_text("0\n")
        for stage in ("raw", "repaired"):
            dest = directory / stage
            dest.mkdir()
            for name in ("area", "references", "qor", "constraints", "clocks", "gating", "setup", "hold", "check_design", "check_timing", "gate_setup", "gate_hold", "gated_data_hold"):
                (dest / (name + ".rpt")).write_text("member_gate_0/Q (CKLNQD1BWP12T30P140LVT) 0.123 0.123 r\nclock gating setup clock gating hold\n")
            for name in ("mapped.v", "mapped.ddc", "mapped.sdc"):
                (dest / name).write_text("artifact\n")
            metrics = dict(data_flops=10176, clock_gates=128 if side == "gated" else 0,
                           period_ns=2, propagated="true", total_area=40000 if side == "reference" else 30000,
                           max_slack_ns=.2, min_slack_ns=.01,
                           gate_max_slack_ns=.5, gate_min_slack_ns=.04)
            (dest / "metrics.tsv").write_text("metric\tvalue\n" + "".join(f"{k}\t{v}\n" for k, v in metrics.items()))
    return root


def test_reports_are_closed_but_negative_hold_is_not_timing_pass(tmp_path):
    root = fixture(tmp_path)
    path = root / "gated/repaired/metrics.tsv"
    path.write_text(path.read_text().replace("min_slack_ns\t0.01", "min_slack_ns\t-0.01"))
    result = CHECKER.check(root)
    assert result["tool_input_artifact_closure"] == "PASS"
    assert result["area_change"]["repaired"]["reduction_percent"] == 25
    assert not result["area_change"]["repaired"]["both_sides_timing_closed"]


def test_redirected_native_error_fails(tmp_path):
    root = fixture(tmp_path)
    (root / "gated/raw/gating.rpt").write_text("Error: missing clock gate\n")
    with pytest.raises(AssertionError):
        CHECKER.check(root)


def test_ideal_clock_fails(tmp_path):
    root = fixture(tmp_path)
    path = root / "gated/raw/metrics.tsv"
    path.write_text(path.read_text().replace("propagated\ttrue", "propagated\tfalse"))
    with pytest.raises(AssertionError):
        CHECKER.check(root)


def test_missing_gate_capture_path_fails(tmp_path):
    root = fixture(tmp_path)
    (root / "gated/raw/gated_data_hold.rpt").write_text("clock network delay (ideal)\n")
    with pytest.raises(AssertionError):
        CHECKER.check(root)
