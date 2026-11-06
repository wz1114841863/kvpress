#!/usr/bin/env python3
"""Validate native WCG1 isolation artifacts; timing failure is a result, not PASS."""
import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value, label):
    value = float(value)
    assert math.isfinite(value), f"nonfinite {label}"
    return value


def unique_number(text, label):
    values = re.findall(r"^\s*" + re.escape(label) + r":\s*(\S+)\s*$", text, re.M)
    assert len(values) == 1, f"missing/duplicate native {label}"
    return number(values[0], label)


def native_area(text):
    # 'Total area' may be undefined under ZeroWireload. Cell area is authority.
    result = {key: unique_number(text, label) for key, label in (
        ("total_area", "Total cell area"), ("combinational_area", "Combinational area"),
        ("sequential_area", "Noncombinational area"), ("buffer_inverter_area", "Buf/Inv area"))}
    assert result["total_area"] > 0 and all(value >= 0 for value in result.values())
    assert abs(result["total_area"] - result["combinational_area"] - result["sequential_area"]) <= 2e-6, "native area components disagree"
    return result


def precision_slack(text):
    values = re.findall(r"^\s*slack \((?:MET|VIOLATED)\)\s+(\S+)\s*$", text, re.M)
    assert values, "no native precision slack"
    return min(number(value, "native slack") for value in values)


def check(root: Path, recover_empty_area=False) -> dict:
    result = {"evidence_class": "one_bank_logic_mapping_propagated_cell_clock_sta_not_top_or_physical_signoff", "sides": {}}
    for side in ("reference", "gated"):
        directory = root / side
        log = (directory / "native.log").read_text(errors="replace")
        assert re.search(r"^KVZAP_WCG1_SIDE_RUN_PASS side=" + side + r"$", log, re.M), side
        assert (directory / "exit_status").read_text().strip() == "0", side
        for path in [directory / "native.log", *directory.rglob("*.rpt")]:
            assert not re.search(r"^\s*(?:Error:|Fatal:)", path.read_text(errors="replace"), re.M), path
        result["sides"][side] = {}
        for stage in ("raw", "repaired"):
            dest = directory / stage
            reports = ["area", "references", "qor", "constraints", "clocks", "gating", "setup", "hold", "check_design", "check_timing"]
            if side == "gated":
                reports += ["gate_setup", "gate_hold", "gated_data_hold"]
            for name in [*(f"{v}.rpt" for v in reports), "mapped.v", "mapped.ddc", "mapped.sdc", "metrics.tsv"]:
                assert (dest / name).stat().st_size > 0, dest / name
            rows = list(csv.DictReader((dest / "metrics.tsv").open(), delimiter="\t"))
            m = {r["metric"]: r["value"] for r in rows}
            assert len(rows) == len(m), "duplicate metric"
            assert int(m["data_flops"]) == 10176
            assert int(m["clock_gates"]) == (128 if side == "gated" else 0)
            assert float(m["period_ns"]) == 2 and m["propagated"] == "true", m
            area = native_area((dest / "area.rpt").read_text())
            empty_area = m["total_area"] == ""
            if empty_area:
                assert recover_empty_area, "empty area scalar requires explicit saved-artifact recovery"
                assert log.count("Attribute 'area' does not exist on design") == 2, "unknown empty-area cause"
            else:
                assert abs(number(m["total_area"], "area scalar") - area["total_area"]) <= 2e-6, "scalar/native area disagree"
            m.update(area, area_source="native_report_total_cell_area", recovered_empty_area=empty_area)
            for key, report in (("max_slack_ns", "setup"), ("min_slack_ns", "hold")) + ((("gate_max_slack_ns", "gate_setup"), ("gate_min_slack_ns", "gate_hold")) if side == "gated" else ()):
                scalar = number(m[key], key)
                precise = precision_slack((dest / f"{report}.rpt").read_text())
                assert abs(scalar - precise) <= 1e-5, f"scalar/native slack disagree: {key}"
                m[key] = precise
            mapped = (dest / "mapped.v").read_text()
            assert not re.search(r"\b(?:GTECH_\w+|SEQGEN)\b", mapped), "unmapped logic"
            cells = re.findall(r"\b(EDFQD\w+|DFQD\w+)\s+(member|suffix)_ff_r(\d+)_b(\d+)\s*\(", mapped)
            required = {(kind, str(row), str(bit)) for kind, width in (("member", 79), ("suffix", 80)) for row in range(64) for bit in range(width)}
            assert len(cells) == 10176 and {(kind, row, bit) for _, kind, row, bit in cells} == required, "mapped data inventory"
            assert all(ref.startswith("DFQD" if side == "gated" else "EDFQD") for ref, _, _, _ in cells), "storage architecture changed"
            gates = re.findall(r"\bCKLNQ\w+\s+(\w+_gate_\d+)\s*\(", mapped)
            expected = {f"{kind}_gate_{row}" for kind in ("member", "suffix") for row in range(64)} if side == "gated" else set()
            assert len(gates) == len(expected) and set(gates) == expected, "mapped gate inventory"
            lint = re.findall(r"^Warning:.*\((LINT-\d+)\)", (dest / "check_design.rpt").read_text(), re.M)
            m["lint_warning_counts"] = {code: lint.count(code) for code in sorted(set(lint))}
            assert not (set(lint) - {"LINT-28"}), "unexpected mapped lint"
            assert not re.search(r"^\s*Warning:", (dest / "check_timing.rpt").read_text(), re.M), "timing coverage warning"
            # DC must show actual propagated cell-clock capture, not an ideal branch.
            if side == "gated":
                hold = (dest / "gated_data_hold.rpt").read_text()
                # With -transition_time columns are Trans, Incr, Path. Check Incr.
                gate_delays = re.findall(r"\w+_gate_\d+/Q\s+\(CKLNQ\w+\)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", hold)
                assert gate_delays and all(number(v[1], "gate increment") > 0 for v in gate_delays), "missing nonzero gate capture arc"
                assert re.search(r"clock gating setup", (dest / "gate_setup.rpt").read_text(), re.I), "no gating setup check"
                assert re.search(r"clock gating hold", (dest / "gate_hold.rpt").read_text(), re.I), "no gating hold check"
            m["setup_closed"] = m["max_slack_ns"] >= 0
            m["hold_closed"] = m["min_slack_ns"] >= 0
            m["gate_checks_closed"] = side == "reference" or min(m["gate_max_slack_ns"], m["gate_min_slack_ns"]) >= 0
            qor = (dest / "qor.rpt").read_text()
            for key, label in (("total_area", "Cell Area"), ("combinational_area", "Combinational Area"), ("sequential_area", "Noncombinational Area")):
                assert abs(m[key] - unique_number(qor, label)) <= 2e-6, "QoR/area report disagree"
            for kind, prefix in (("setup", r"Design\s+WNS"), ("hold", r"Design \(Hold\)\s+WNS")):
                found = re.findall(prefix + r":\s*(\S+)\s+TNS:\s*(\S+)\s+Number of Violating Paths:\s*(\d+)", qor)
                assert len(found) == 1, "missing native QoR design summary"
                wns, tns, count = found[0]
                m[f"{kind}_qor"] = dict(wns_ns=number(wns, "WNS"), tns_ns=number(tns, "TNS"), violating_paths=int(count))
                if m[f"{kind}_closed"]:
                    assert float(tns) == 0 and int(count) == 0, "positive precision slack with native violations"
            m["no_violated_constraints"] = "This design has no violated constraints." in (dest / "constraints.rpt").read_text()
            result["sides"][side][stage] = m
    result["area_change"] = {}
    for stage in ("raw", "repaired"):
        ref, gated = (result["sides"][s][stage] for s in ("reference", "gated"))
        result["area_change"][stage] = {
            "saved_area": ref["total_area"] - gated["total_area"],
            "reduction_percent": 100 * (1 - gated["total_area"] / ref["total_area"]),
            "both_sides_timing_closed": all(m[k] for m in (ref, gated) for k in ("setup_closed", "hold_closed", "gate_checks_closed")),
        }
    result["native_artifact_closure"] = "PASS"
    result["artifact_sha256"] = {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in (".ddc", ".v", ".sdc", ".rpt", ".tsv")}
    return result


def source_inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def saved_constraints(text):
    assert not re.search(r"^set_(?:false_path|multicycle_path)\b", text, re.M), "timing exception introduced"
    clocks = re.findall(r"^create_clock .* -name kvzap_control_clk\s+-period (\S+)", text, re.M)
    assert len(clocks) == 1 and number(clocks[0], "SDC period") == 2
    assert "set_propagated_clock [get_clocks kvzap_control_clk]" in text
    for kind, value in (("setup", .1), ("hold", .02)):
        found = re.findall(r"^set_clock_uncertainty -" + kind + r" (\S+)", text, re.M)
        assert len(found) == 1 and number(found[0], kind) == value
    for pattern, expected in ((r"^set_input_delay -clock kvzap_control_clk\s+(\S+)", .2),
                              (r"^set_output_delay -clock kvzap_control_clk\s+(\S+)", .2),
                              (r"^set_input_transition -(?:max|min) (\S+)", .05),
                              (r"^set_load -pin_load (\S+)", .005)):
        values = re.findall(pattern, text, re.M)
        assert values and all(number(value, "SDC boundary") == expected for value in values)
    assert re.search(r"^set_input_delay .*\[get_ports reset\]", text, re.M), "reset must stay timed"


def verify_saved_inputs(root, inputs, archive, launch, evidence):
    assert sha(archive) == launch["archive_sha256"]
    assert sha(inputs / "manifest.json") == launch["manifest_sha256"]
    assert sha(inputs / "SHA256SUMS") == launch["checksums_sha256"]
    assert sha(root / "input_manifest.json") == launch["manifest_sha256"]
    for name, expected in launch["manifest"]["input_sha256"].items():
        assert Path(name).name == name and sha(inputs / name) == expected, name
    for line in (inputs / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        assert Path(name).name == name and sha(inputs / name) == expected, name
    # Read and hash the actual DB; this invokes no EDA executable.
    pins = (root / "input_sha256.txt").read_text().splitlines()
    assert len(pins) == 2
    for line in pins:
        expected, name = line.split(maxsplit=1)
        assert sha(Path(name)) == expected, name
    assert pins[0].split()[0] == launch["manifest"]["db_sha256"]
    assert root.name == launch["manifest"]["run_id"] == evidence["run_id"]
    for name, expected in evidence["artifact_sha256"].items():
        assert not Path(name).is_absolute() and ".." not in Path(name).parts
        assert sha(root / name) == expected, name
    assert (root / "exit_status").read_text().strip() == "1", "original failed marker changed"
    assert "ValueError: could not convert string to float: ''" in (root / "launcher.log").read_text()


def saved_validation(args):
    assert all((args.inputs, args.archive, args.launch_record, args.evidence_record, args.output_dir))
    root = args.root.resolve()
    output = args.output_dir.resolve()
    assert output != root and root not in output.parents, "output must be outside frozen run"
    assert output != args.inputs.resolve() and args.inputs.resolve() not in output.parents, "output must be outside frozen inputs"
    launch = json.loads(args.launch_record.read_text())
    evidence = json.loads(args.evidence_record.read_text())
    verify_saved_inputs(root, args.inputs, args.archive, launch, evidence)
    before = source_inventory(root)
    for side in ("reference", "gated"):
        for stage in ("raw", "repaired"):
            saved_constraints((root / side / stage / "mapped.sdc").read_text())
    result = check(root, recover_empty_area=True)
    assert result["area_change"]["repaired"]["both_sides_timing_closed"], "repaired screen timing not closed"
    assert result["area_change"]["repaired"]["saved_area"] > 0, "no repaired area benefit"
    assert all(result["sides"][side]["repaired"]["no_violated_constraints"] for side in ("reference", "gated"))
    verify_saved_inputs(root, args.inputs, args.archive, launch, evidence)
    assert source_inventory(root) == before, "source run changed during validation"
    result.update(schema="wcg1-saved-artifact-validation-1", disposition="ACCEPTED_MATCHED_BANK_SCREEN",
                  tool_input_artifact_closure="PASS", original_outer_exit=1,
                  source_root=str(root), source_inventory_sha256=before,
                  validation_tool_sha256=sha(Path(__file__)),
                  launch_record_sha256=sha(args.launch_record), evidence_record_sha256=sha(args.evidence_record),
                  no_eda_tool_invoked=True, area_recovery="explicit native-report derivation; frozen metrics unchanged")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--recover-empty-area", action="store_true", help="Pinned saved-artifact recovery only; requires all provenance/output arguments")
    parser.add_argument("--output-dir", type=Path, help="New separate output root, never the frozen run")
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--launch-record", type=Path)
    parser.add_argument("--evidence-record", type=Path)
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError("validation assertions require Python without -O")
    if args.recover_empty_area:
        assert args.output_dir and not args.output_dir.exists(), "new sidecar output required"
        result = saved_validation(args)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        path = args.output_dir / "result.json"
    else:
        assert args.output_dir is None, "separate output requires pinned recovery"
        result = check(args.root)
        path = args.root / "result.json"
        assert not path.exists(), "refusing to overwrite result"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print("KVZAP_WCG1_MAPPING_POSTCHECK_PASS")


if __name__ == "__main__":
    main()
