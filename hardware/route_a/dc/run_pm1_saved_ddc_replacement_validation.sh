#!/usr/bin/env bash
# Validate the existing mapped PM1 child through a short saved-DDC-only relink.
set -euo pipefail

if [[ "${1:-}" == --help ]]; then
  echo "usage: $0 OUTPUT_ROOT BASELINE_DDC CANDIDATE_DDC CANDIDATE_MAPPED_V R3_INPUT_MANIFEST"
  exit 0
fi
if [[ $# -ne 5 ]]; then
  echo "usage: $0 OUTPUT_ROOT BASELINE_DDC CANDIDATE_DDC CANDIDATE_MAPPED_V R3_INPUT_MANIFEST" >&2
  exit 2
fi

output_root=$1
baseline_ddc=$2
candidate_ddc=$3
candidate_mapped_v=$4
r3_input_manifest=$5
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
expected_baseline_ddc_sha=29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326
expected_candidate_ddc_sha=38038fb2c9edc434d6bc3059e9166c57c63cfed78269e2765a2f758e21fddb0e
expected_candidate_mapped_v_sha=e98ef9cac40e87d40f5ed8426bc0f2dd09ac8b5eb2e51d508a31fe3179eb9aa2

[[ ! -e $output_root ]] || { echo "refusing to overwrite $output_root" >&2; exit 3; }
for required in "$baseline_ddc" "$candidate_ddc" "$candidate_mapped_v" "$r3_input_manifest"; do
  [[ -f $required ]] || { echo "missing input: $required" >&2; exit 4; }
done

source "$script_dir/env_kvzap_control_projection_dc.sh"
mkdir -p "$output_root"
export KVZAP_PM1_SAVED_DDC_ROOT="$output_root"
export KVZAP_PM1_BASELINE_DDC="$baseline_ddc"
export KVZAP_PM1_CANDIDATE_DDC="$candidate_ddc"

python3 - "$output_root" "$baseline_ddc" "$candidate_ddc" \
  "$candidate_mapped_v" "$r3_input_manifest" \
  "$script_dir/validate_pm1_saved_ddc_replacement.tcl" \
  "$expected_baseline_ddc_sha" "$expected_candidate_ddc_sha" \
  "$expected_candidate_mapped_v_sha" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sys

root, baseline, candidate, mapped_v, r3_manifest, tcl = (
    Path(value).resolve() for value in sys.argv[1:7]
)
expected_baseline, expected_candidate, expected_mapped_v = sys.argv[7:10]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for path, expected in (
    (baseline, expected_baseline),
    (candidate, expected_candidate),
    (mapped_v, expected_mapped_v),
):
    actual = sha(path)
    if actual != expected:
        raise SystemExit(f"input hash mismatch for {path}: {actual}")

r3 = json.loads(r3_manifest.read_text())
if r3.get("schema") != "kvzap-pm1-characterized-replacement-v1":
    raise SystemExit("unexpected r3 manifest schema")
if r3.get("baseline_ddc_sha256") != expected_baseline:
    raise SystemExit("r3 baseline DDC identity mismatch")
if r3.get("method", {}).get("expected_precompile_registers") != 62002:
    raise SystemExit("r3 precompile register contract mismatch")
if r3.get("method", {}).get("expected_postcompile_registers") != 62000:
    raise SystemExit("r3 postcompile register contract mismatch")

profile_path = Path(os.environ["KVZAP_DC_CONSTRAINT_MANIFEST"])
profile = json.loads(profile_path.read_text())
if profile["profile_id"] != "dc_feasibility_fair_v1":
    raise SystemExit("unexpected constraint profile")
library = Path(os.environ["KVZAP_DC_TARGET_LIBRARY"])
if sha(library) != profile["integrity"]["target_library_sha256"]:
    raise SystemExit("target library hash mismatch")
if r3.get("target_library_sha256") != sha(library):
    raise SystemExit("r3 target library identity mismatch")

manifest = {
    "schema": "kvzap-pm1-saved-ddc-validation-v1",
    "scope": "read/link/report existing accepted top and mapped PM1 child only",
    "baseline_ddc": str(baseline),
    "baseline_ddc_sha256": sha(baseline),
    "candidate_ddc": str(candidate),
    "candidate_ddc_sha256": sha(candidate),
    "candidate_mapped_v": str(mapped_v),
    "candidate_mapped_v_sha256": sha(mapped_v),
    "r3_input_manifest": str(r3_manifest),
    "r3_input_manifest_sha256": sha(r3_manifest),
    "validation_tcl": str(tcl),
    "validation_tcl_sha256": sha(tcl),
    "constraint_profile": profile["profile_id"],
    "target_library": str(library),
    "target_library_sha256": sha(library),
    "method": {
        "relink": "unique pageManager instance; no force and no pin map",
        "operations": "read_ddc, link, check and report only",
        "forbidden": ["analyze", "elaborate", "characterize", "compile", "write_ddc"],
    },
}
with (root / "input_manifest.json").open("x") as handle:
    json.dump(manifest, handle, indent=2)
print("KVZAP_PM1_SAVED_DDC_INPUT_PASS", flush=True)
PY

if ! ulimit -s unlimited 2>/dev/null; then
  echo "unable to raise DC stack limit to unlimited" >&2
  exit 5
fi
[[ $(ulimit -s) == unlimited ]] || {
  echo "DC stack limit is not unlimited" >&2
  exit 5
}
echo "KVZAP_PM1_SAVED_DDC_STACK_PASS stack_kb=unlimited"

set +e
"$KVZAP_DC_SHELL" -f "$script_dir/validate_pm1_saved_ddc_replacement.tcl" \
  2>&1 | tee "$output_root/dc_shell.log"
code=${PIPESTATUS[0]}
set -e

if (( code == 0 )); then
  set +e
  python3 - "$output_root" <<'PY' 2>&1 | tee -a "$output_root/dc_shell.log"
from collections import Counter
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
log = root / "dc_shell.log"
summary = root / "summary.tsv"
required = [
    summary,
    root / "baseline/top_check_design.rpt",
    root / "baseline/top_check_timing.rpt",
    root / "baseline/top_qor.rpt",
    root / "baseline/top_area_hierarchy.rpt",
    root / "baseline/top_timing_setup.rpt",
    root / "baseline/top_timing_hold.rpt",
    root / "baseline/child_qor.rpt",
    root / "baseline/child_area.rpt",
    root / "candidate/check_design.rpt",
    root / "candidate/check_timing.rpt",
    root / "candidate/clocks.rpt",
    root / "candidate/qor.rpt",
    root / "candidate/area_hierarchy.rpt",
    root / "candidate/references.rpt",
    root / "candidate/timing_setup.rpt",
    root / "candidate/timing_hold.rpt",
    root / "relinked_top/check_design.rpt",
    root / "relinked_top/check_timing.rpt",
    root / "relinked_top/qor.rpt",
    root / "relinked_top/area_hierarchy.rpt",
    root / "relinked_top/timing_setup.rpt",
    root / "relinked_top/timing_hold.rpt",
]
missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
if missing:
    raise SystemExit("missing or empty saved-DDC artifacts: " + ", ".join(missing))

native_errors = [
    line for line in log.read_text(errors="replace").splitlines()
    if re.match(r"^(?:Error|Fatal):", line)
]
if native_errors:
    raise SystemExit("native saved-DDC errors present: " + " | ".join(native_errors[-8:]))

rows = {}
for line in summary.read_text().splitlines()[1:]:
    key, sep, value = line.partition("\t")
    if not sep or not value:
        raise SystemExit(f"incomplete saved-DDC summary row: {line!r}")
    rows[key] = value
expected_rows = {
    "validation_kind": "saved_ddc_only",
    "top_design": "route_a_control_projection",
    "baseline_ref": "route_a_page_manager",
    "candidate_ref": "route_a_page_manager_pm1",
    "page_manager_boundary_pins": "4289",
    "baseline_registers": "62000",
    "candidate_registers": "62000",
    "candidate_clocks": "1",
    "candidate_proxy_instances": "1",
    "relinked_top_registers": "577106",
}
if rows != expected_rows:
    raise SystemExit(f"unexpected saved-DDC summary: {rows!r}")

def area(path):
    match = re.search(r"^Total cell area:\s+([0-9.]+)$", path.read_text(), re.MULTILINE)
    if not match:
        raise SystemExit(f"missing total cell area in {path}")
    return float(match.group(1))

def qor(path):
    text = path.read_text()
    patterns = {
        "setup_wns_ns": r"Critical Path Slack:\s+(-?[0-9.]+)",
        "setup_tns_ns": r"Total Negative Slack:\s+(-?[0-9.]+)",
        "setup_violating_paths": r"No\. of Violating Paths:\s+([0-9.]+)",
        "hold_wns_ns": r"Worst Hold Violation:\s+(-?[0-9.]+)",
        "hold_tns_ns": r"Total Hold Violation:\s+(-?[0-9.]+)",
        "hold_violating_paths": r"No\. of Hold Violations:\s+([0-9.]+)",
    }
    values = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if not match:
            raise SystemExit(f"missing {key} in {path}")
        values[key] = float(match.group(1))
    return values

def lint(path):
    lines = path.read_text().splitlines()
    categories = Counter(re.findall(r"\(LINT-[0-9]+\)", "\n".join(lines)))
    return {
        "warning_lines": sum(line.startswith("Warning:") for line in lines),
        "error_lines": sum(line.startswith("Error:") for line in lines),
        "categories": dict(sorted(categories.items())),
    }

evidence = {
    "schema": "kvzap-pm1-saved-ddc-evidence-v1",
    "areas": {
        "baseline_top": area(root / "baseline/top_area_hierarchy.rpt"),
        "baseline_child": area(root / "baseline/child_area.rpt"),
        "candidate_child": area(root / "candidate/area_hierarchy.rpt"),
        "relinked_top": area(root / "relinked_top/area_hierarchy.rpt"),
    },
    "timing": {
        "baseline_top": qor(root / "baseline/top_qor.rpt"),
        "candidate_child": qor(root / "candidate/qor.rpt"),
        "relinked_top": qor(root / "relinked_top/qor.rpt"),
    },
    "lint": {
        "baseline_top": lint(root / "baseline/top_check_design.rpt"),
        "candidate_child": lint(root / "candidate/check_design.rpt"),
        "relinked_top": lint(root / "relinked_top/check_design.rpt"),
    },
}
expected_areas = {
    "baseline_top": 3622375.558791,
    "baseline_child": 407451.238597,
    "candidate_child": 390334.056566,
    "relinked_top": 3605258.376760,
}
for key, expected in expected_areas.items():
    if abs(evidence["areas"][key] - expected) > 0.001:
        raise SystemExit(f"unexpected {key} area: {evidence['areas'][key]}")
expected_warnings = {"baseline_top": 44533, "candidate_child": 2599, "relinked_top": 44537}
for key, expected in expected_warnings.items():
    actual = evidence["lint"][key]["warning_lines"]
    if actual != expected or evidence["lint"][key]["error_lines"] != 0:
        raise SystemExit(f"unexpected {key} lint counts: {evidence['lint'][key]}")

(root / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
print("KVZAP_PM1_SAVED_DDC_POSTCHECK_PASS")
PY
  post_code=${PIPESTATUS[0]}
  set -e
  if (( post_code != 0 )); then
    code=8
  fi
fi

echo "KVZAP_PM1_SAVED_DDC_OUTER_EXIT=$code" | tee -a "$output_root/dc_shell.log"
exit "$code"
