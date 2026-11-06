#!/usr/bin/env python3
"""Run WCG1 library-cell edge tests and cell arithmetic; never synthesize a DUT."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA = "4aac97c4efda0665cdc8af807a1f5f6706f69a2359453b244562cd8158f27cbf"
CELLS_SHA = "6474144fd46f259c9529719b92b3698acc0b86b75608bdfd7e201078948cf3f4"
TB = ROOT / "hardware/route_a/dc/tests/wcg1_storage_edge_tb.sv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    result = subprocess.run(command, text=True, capture_output=True, timeout=60)
    log.write_text(result.stdout + result.stderr)
    return result.returncode, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-model", type=Path, required=True)
    parser.add_argument("--cells-tsv", type=Path, required=True, help="hash-pinned native DB attribute report")
    parser.add_argument("--output-dir", type=Path, required=True, help="new immutable result root")
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError("audit assertions require Python without -O")
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    assert sha(args.library_model) == MODEL_SHA
    assert sha(args.cells_tsv) == CELLS_SHA
    assert shutil.which("iverilog") and shutil.which("vvp")
    cells = {row["cell"]: row for row in csv.DictReader(args.cells_tsv.open(), delimiter="\t")}
    assert len(cells) == 16
    old = cells["EDFQD2BWP12T30P140LVT"]
    new = cells["DFQD2BWP12T30P140LVT"]
    gate = cells["CKLNQD1BWP12T30P140LVT"]
    assert gate["clock_gating_integrated_cell"] == "latch_posedge_precontrol"
    assert gate["dont_use"] != "true"
    rows, bits = 36 * 64, 36 * 64 * 159
    member_load = 79 * D(new["cp_capacitance"])
    suffix_load = 80 * D(new["cp_capacitance"])
    assert max(member_load, suffix_load) < D(gate["q_max_capacitance"])
    baseline = bits * D(old["area"])
    plain = bits * D(new["area"])
    gates = 2 * rows * D(gate["area"])
    cost = {
        "evidence": "native_unit_cell_sum_not_mapped_area_or_power",
        "bits": bits, "word_gates": 2 * rows,
        "enabled_data_cells": str(baseline), "plain_data_cells": str(plain),
        "clock_gate_cells": str(gates), "candidate_cell_sum_before_other_cost": str(plain + gates),
        "difference_before_buffers_hold_and_timing_resize": str(baseline - plain - gates),
        "member_cp_load_native_units_no_wire": str(member_load),
        "suffix_cp_load_native_units_no_wire": str(suffix_load),
        "gate_q_max_capacitance_native_units": gate["q_max_capacitance"],
        "unpriced": ["clock/data wires", "clock/data buffers", "hold repair", "timing resizing", "mapping policy"],
        "dont_use_unknown_is_not_mapping_eligibility_proof": True,
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    image = args.output_dir / "edge.vvp"
    compile_exit, _ = run(
        ["iverilog", "-g2012", "-s", "wcg1_storage_edge_tb", "-o", str(image), str(TB), str(args.library_model)],
        args.output_dir / "compile.log",
    )
    assert compile_exit == 0
    simulations = {}
    for mode in ("positive", "BARE_AND", "MERGED_ENABLE", "CLOCK_SKEW"):
        code, text = run(["vvp", str(image)] + ([] if mode == "positive" else ["+" + mode]),
                         args.output_dir / (mode.lower() + ".log"))
        if mode == "positive":
            assert code == 0 and "WCG1_EDGE_UNIT_PASS" in text
            match = re.search(r"checks=(\d+)", text)
            assert match and int(match.group(1)) == 978
            simulations[mode] = dict(exit=code, result="PASS", comparisons=978)
        else:
            expected = {"BARE_AND": "high_phase_enable_rise", "MERGED_ENABLE": "suffix row=0",
                        "CLOCK_SKEW": "root_edge_nba_data_change"}[mode]
            assert code != 0 and "WCG1_COMPARE_FAIL" in text and expected in text
            assert "WCG1_NEGATIVE_CONTROL_NOT_DETECTED" not in text
            simulations[mode] = dict(exit=code, result="EXPECTED_DIFFERENCE", expected=expected)
    report = dict(
        schema_version="route-a-wcg1-cell-feasibility-1",
        evidence_class="unsdf_library_cell_unit_simulation_and_native_unit_cost_not_wrapper_equivalence_or_sta",
        input_sha256={"checker": sha(Path(__file__)), "testbench": sha(TB),
                      "library_model": sha(args.library_model), "native_cells_tsv": sha(args.cells_tsv)},
        cost=cost, simulations=simulations,
        caveats=["Icarus does not enforce the native setup/hold checks or annotated gate delays",
                 "CLOCK_SKEW is synthetic, not measured cell delay or a proven legal physical input trace",
                 "generic wrapper and actual write-enable cone not implemented or simulated"],
    )
    report["artifact_sha256"] = {p.name: sha(p) for p in args.output_dir.iterdir() if p.is_file()}
    output = args.output_dir / "result.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print("WCG1_CELL_FEASIBILITY_PASS functional_unit=PASS negative_controls=3 cost=UNIT_ARITHMETIC_ONLY")
    print(f"result={output} sha256={sha(output)}")


if __name__ == "__main__":
    main()
