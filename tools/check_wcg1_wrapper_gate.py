#!/usr/bin/env python3
"""Build/run the actual WCG1 gate before expensive wrapper tests; never run DC."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteACompactWordClocking.scala")
TESTS = Path("hardware/route_a/dc/tests")
MODEL_SHA = "4aac97c4efda0665cdc8af807a1f5f6706f69a2359453b244562cd8158f27cbf"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, output):
    result = subprocess.run([str(v) for v in command], text=True, capture_output=True, timeout=180)
    text = result.stdout + result.stderr
    output.write_text(text)
    return result.returncode, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New immutable preflight directory")
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--library-model", type=Path, help="Also require Icarus/native CKLNQ comparisons when provided")
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError("preflight assertions require Python without -O")
    out = args.output_dir.resolve()
    assert not out.exists(), "refusing to overwrite preflight"
    out.mkdir(parents=True)
    source = ROOT / SOURCE
    gate = re.search(r'setInline\("[^"]+", """(.*?)"""\)', source.read_text(), re.S).group(1)
    assert gate.count("if (!clock) enable_low = enable;") == 1
    assert "enable_low <= enable" not in gate
    assert "CKLNQD1BWP12T30P140LVT native_gate(.CP(clock), .E(enable), .TE(1'b0), .Q(gated_clock));" in gate
    fixed = out / "gate.sv"
    fixed.write_text(gate)
    old = out / "old_gate.sv"
    old.write_text(gate.replace("enable_low = enable", "enable_low <= enable"))
    code, version = run([args.verilator, "--version"], out / "verilator_version.log")
    assert code == 0 and "Verilator 5.041" in version, "match the failed wrapper tool version"
    code, text = run([args.verilator, "--lint-only", "--timescale", "1ps/1ps", "--top-module", "route_a_compact_word_clock_gate", old], out / "old_lint.log")
    assert code != 0 and "%Warning-COMBDLY" in text and "%Error: Exiting due to 1 warning(s)" in text
    obj = out / "obj"
    command = [args.verilator, "--cc", "--exe", "--build", "--assert", "--build-jobs", "1", "--verilate-jobs", "2", "--timescale", "1ps/1ps", "--top-module", "wcg1_gate_minimal", "--Mdir", obj,
               fixed, ROOT / TESTS / "wcg1_gate_minimal.sv", ROOT / TESTS / "wcg1_gate_minimal.cpp"]
    code, text = run(command, out / "fixed_build.log")
    assert code == 0 and not re.search(r"%\s*(?:Warning|Error)", text), "fixed minimal build must be warning-free"
    image = obj / "Vwcg1_gate_minimal"
    code, text = run([image], out / "positive.log")
    match = re.search(r"WCG1_VERILATOR_MINIMAL_PASS checks=(\d+) edge_checks=(\d+) modes=2", text)
    assert code == 0 and match and int(match.group(1)) == 6156 and int(match.group(2)) > 0
    negatives = {}
    for mode, failure in (("BARE_AND", "unexpected_positive_edge"), ("MERGED_ENABLE", "suffix_capture_mismatch")):
        status, message = run([image, mode], out / f"{mode.lower()}.log")
        assert status != 0 and f"WCG1_VERILATOR_MINIMAL_FAIL {failure}" in message
        negatives[mode] = dict(result="EXPECTED_DIFFERENCE", failure=failure)
    native = {}
    if args.library_model:
        assert sha(args.library_model) == MODEL_SHA and shutil.which("iverilog") and shutil.which("vvp")
        for mode in ("behavioral", "synthesis_binding"):
            image = out / f"{mode}.vvp"
            command = ["iverilog", "-g2012", "-s", "wcg1_wrapper_gate_tb"]
            if mode == "synthesis_binding":
                command += ["-DSYNTHESIS"]
            command += ["-o", image, ROOT / TESTS / "wcg1_wrapper_gate_tb.sv", fixed, args.library_model.resolve()]
            status, _ = run(command, out / f"{mode}_build.log")
            assert status == 0
            status, message = run(["vvp", image], out / f"{mode}.log")
            assert status == 0 and "WCG1_WRAPPER_GATE_NATIVE_EQUIVALENCE_PASS checks=368" in message
            native[mode] = dict(result="PASS", checks=368)
    files = [source, ROOT / TESTS / "wcg1_gate_minimal.sv", ROOT / TESTS / "wcg1_gate_minimal.cpp", ROOT / TESTS / "wcg1_wrapper_gate_tb.sv", Path(__file__)]
    result = dict(schema="wcg1-wrapper-gate-preflight-1", result="PASS", evidence_scope="unsdf model/scheduler/native-cell unit checks, not wrapper equivalence or timing", verilator=version.strip(), old_combdly="REPRODUCED", fixed_build="PASS_NO_WARNING_SUPPRESSION", checks=int(match.group(1)), edge_checks=int(match.group(2)), negatives=negatives, native_comparisons=native, native_model_sha256=MODEL_SHA if args.library_model else None, source_sha256={str(p.relative_to(ROOT)): sha(p) for p in files}, output_log_sha256={p.name:sha(p) for p in out.glob("*.log")})
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("WCG1_WRAPPER_GATE_PREFLIGHT_PASS checks=6156 native_modes=" + str(len(native)))


if __name__ == "__main__":
    main()
