"""Ensure invalid STA evidence cannot masquerade as a successful WCG1 result."""
import importlib.util
import re
import subprocess
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
                (dest / (name + ".rpt")).write_text("member_gate_0/Q (CKLNQD1BWP12T30P140LVT) 0.05 0.123 0.123 r\nclock gating setup clock gating hold\n")
            for name in ("mapped.v", "mapped.ddc", "mapped.sdc"):
                (dest / name).write_text("artifact\n")
            cell = "EDFQD2" if side == "reference" else "DFQD2"
            mapped = "".join(f"{cell}BWP12T30P140LVT {kind}_ff_r{row}_b{bit}();\n" for kind, width in (("member", 79), ("suffix", 80)) for row in range(64) for bit in range(width))
            if side == "gated":
                mapped += "".join(f"CKLNQD1BWP12T30P140LVT {kind}_gate_{row}();\n" for kind in ("member", "suffix") for row in range(64))
            (dest / "mapped.v").write_text(mapped)
            total = 40000 if side == "reference" else 30000
            (dest / "area.rpt").write_text(f"Combinational area: 10000.000000\nNoncombinational area: {total-10000}.000000\nBuf/Inv area: 100.000000\nTotal cell area: {total}.000000\nTotal area: undefined\n")
            (dest / "qor.rpt").write_text(f"Cell Area: {total}.000000\nCombinational Area: 10000.000000\nNoncombinational Area: {total-10000}.000000\nDesign WNS: 0.00 TNS: 0.00 Number of Violating Paths: 0\nDesign (Hold) WNS: 0.00 TNS: 0.00 Number of Violating Paths: 0\n")
            (dest / "constraints.rpt").write_text("This design has no violated constraints.\n")
            for name, slack in (("setup", .2), ("hold", .01), ("gate_setup", .5), ("gate_hold", .04)):
                (dest / f"{name}.rpt").write_text(f"clock gating setup clock gating hold\nslack (MET) {slack}\n")
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
    (path.parent / "hold.rpt").write_text("slack (VIOLATED) -0.01\n")
    result = CHECKER.check(root)
    assert result["native_artifact_closure"] == "PASS"
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


def empty_scalar_fixture(root):
    root = fixture(root)
    for side in ("reference", "gated"):
        log = root / side / "native.log"
        log.write_text(log.read_text() + f"Warning: Attribute 'area' does not exist on design 'wcg1_{side}'. (UID-101)\n" * 2)
        for stage in ("raw", "repaired"):
            path = root / side / stage / "metrics.tsv"
            path.write_text(re.sub(r"total_area\t\d+", "total_area\t", path.read_text()))
    return root


def test_empty_area_needs_explicit_recovery_and_keeps_metrics_unchanged(tmp_path):
    root = empty_scalar_fixture(tmp_path)
    path = root / "gated/repaired/metrics.tsv"
    before = path.read_bytes()
    with pytest.raises(AssertionError, match="explicit"):
        CHECKER.check(root)
    result = CHECKER.check(root, recover_empty_area=True)
    assert result["sides"]["gated"]["repaired"]["total_area"] == 30000
    assert result["sides"]["gated"]["repaired"]["recovered_empty_area"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("replacement", ["Total area: 30000", "Total cell area: NaN", "Total cell area: inf", "Total cell area: 0", "Total cell area: 30001", "Total cell area: 30000\nTotal cell area: 30000"])
def test_missing_nonfinite_inconsistent_or_duplicate_native_area_fails(tmp_path, replacement):
    root = empty_scalar_fixture(tmp_path)
    path = root / "gated/repaired/area.rpt"
    path.write_text(path.read_text().replace("Total cell area: 30000.000000", replacement))
    with pytest.raises((AssertionError, ValueError)):
        CHECKER.check(root, recover_empty_area=True)


def test_unknown_empty_scalar_cause_fails(tmp_path):
    root = empty_scalar_fixture(tmp_path)
    path = root / "reference/native.log"
    path.write_text("KVZAP_WCG1_SIDE_RUN_PASS side=reference\n")
    with pytest.raises(AssertionError, match="cause"):
        CHECKER.check(root, recover_empty_area=True)


def test_scalar_area_mismatch_is_not_overwritten(tmp_path):
    root = fixture(tmp_path)
    path = root / "gated/repaired/metrics.tsv"
    path.write_text(path.read_text().replace("total_area\t30000", "total_area\t29999"))
    with pytest.raises(AssertionError, match="disagree"):
        CHECKER.check(root)


def test_nonzero_transition_does_not_prove_clock_gate_delay(tmp_path):
    root = fixture(tmp_path)
    (root / "gated/raw/gated_data_hold.rpt").write_text("member_gate_0/Q (CKLNQD1BWP12T30P140LVT) 0.05 0.000000 0.123 r\n")
    with pytest.raises(AssertionError, match="capture arc"):
        CHECKER.check(root)


@pytest.mark.parametrize("case", ["valid", "missing", "nonfinite", "inconsistent"])
def test_tcl_area_collector_without_dc(tmp_path, case):
    source = (ROOT / "hardware/route_a/dc/screen_wcg1_bank_sta.tcl").read_text()
    proc = source.split("# End native area reader")[0]
    text = "Total cell area: 30.000000\nCombinational area: 10.000000\nNoncombinational area: 20.000000\n"
    if case == "missing":
        text = text.replace("Total cell area", "Total area")
    elif case == "nonfinite":
        text = text.replace("30.000000", "NaN")
    elif case == "inconsistent":
        text = text.replace("30.000000", "31.000000")
    path = tmp_path / "area.rpt"
    path.write_text(text)
    script = proc + '\nif {[catch {wcg1_native_area_values {' + str(path) + '}} value]} {puts stderr $value; exit 1}\nputs $value\n'
    result = subprocess.run(["tclsh"], input=script, text=True, capture_output=True, check=False)
    assert (result.returncode == 0) == (case == "valid"), result.stderr


@pytest.mark.parametrize("mutation", [None, "period", "hold", "false_path"])
def test_saved_constraints_preserve_fair_profile(mutation):
    text = """create_clock [get_ports clock] -name kvzap_control_clk -period 2 -waveform {0 1}
set_clock_uncertainty -setup 0.1 [get_clocks kvzap_control_clk]
set_clock_uncertainty -hold 0.02 [get_clocks kvzap_control_clk]
set_propagated_clock [get_clocks kvzap_control_clk]
set_input_delay -clock kvzap_control_clk 0.2 [get_ports reset]
set_output_delay -clock kvzap_control_clk 0.2 [get_ports result]
set_input_transition -max 0.05 [get_ports clock]
set_load -pin_load 0.005 [get_ports result]
"""
    if mutation == "period":
        text = text.replace("-period 2", "-period 3")
    elif mutation == "hold":
        text = text.replace("-hold 0.02", "-hold 0.01")
    elif mutation == "false_path":
        text += "set_false_path -from [get_ports reset]\n"
    if mutation is None:
        CHECKER.saved_constraints(text)
    else:
        with pytest.raises(AssertionError):
            CHECKER.saved_constraints(text)
