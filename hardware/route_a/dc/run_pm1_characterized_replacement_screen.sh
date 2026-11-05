#!/usr/bin/env bash
# Run the controlled PM1 bottom-up characterized child-replacement screen.
set -euo pipefail

if [[ "${1:-}" == --help ]]; then
  echo "usage: $0 OUTPUT_ROOT BASELINE_DDC CANDIDATE_SV CANDIDATE_INPUT_SHA256"
  exit 0
fi
if [[ $# -ne 4 ]]; then
  echo "usage: $0 OUTPUT_ROOT BASELINE_DDC CANDIDATE_SV CANDIDATE_INPUT_SHA256" >&2
  exit 2
fi

output_root=$1
baseline_ddc=$2
candidate_sv=$3
candidate_input_sha=$4
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
expected_ddc_sha=29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326
expected_candidate_sha=dfaf40814b0372962b1720c7c9289271d6dc60158fc0d2b09238e3bbe0496671

[[ ! -e $output_root ]] || { echo "refusing to overwrite $output_root" >&2; exit 3; }
[[ -f $baseline_ddc ]] || { echo "missing baseline DDC: $baseline_ddc" >&2; exit 4; }
[[ -f $candidate_sv ]] || { echo "missing candidate SV: $candidate_sv" >&2; exit 5; }
[[ -f $candidate_input_sha ]] || { echo "missing candidate hash manifest: $candidate_input_sha" >&2; exit 6; }

source "$script_dir/env_kvzap_control_projection_dc.sh"
mkdir -p "$output_root"
export KVZAP_PM1_CHARACTERIZED_ROOT="$output_root"
export KVZAP_PM1_BASELINE_DDC="$baseline_ddc"
export KVZAP_PM1_CANDIDATE_SV="$candidate_sv"

python3 - "$output_root" "$baseline_ddc" "$candidate_sv" "$candidate_input_sha" \
  "$script_dir/screen_pm1_characterized_replacement.tcl" \
  "$expected_ddc_sha" "$expected_candidate_sha" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root, ddc, candidate, hash_manifest, tcl, expected_ddc, expected_candidate = (
    Path(value).resolve() if index < 5 else value
    for index, value in enumerate(sys.argv[1:])
)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if sha(ddc) != expected_ddc:
    raise SystemExit("accepted baseline DDC hash mismatch")
if sha(candidate) != expected_candidate:
    raise SystemExit("accepted PM1 candidate hash mismatch")
subprocess.run(["sha256sum", "-c", str(hash_manifest)], check=True)

profile_path = Path(os.environ["KVZAP_DC_CONSTRAINT_MANIFEST"])
profile = json.loads(profile_path.read_text())
if profile["profile_id"] != "dc_feasibility_fair_v1":
    raise SystemExit("unexpected constraint profile")
library = Path(os.environ["KVZAP_DC_TARGET_LIBRARY"])
if sha(library) != profile["integrity"]["target_library_sha256"]:
    raise SystemExit("target library hash mismatch")

manifest = {
    "schema": "kvzap-pm1-characterized-replacement-v1",
    "scope": "saved mapped Route-A top plus port-identical contextual PM1 Page Manager child",
    "baseline_ddc": str(ddc),
    "baseline_ddc_sha256": sha(ddc),
    "candidate_sv": str(candidate),
    "candidate_sv_sha256": sha(candidate),
    "candidate_input_sha256": str(hash_manifest),
    "candidate_input_sha256_sha256": sha(hash_manifest),
    "screen_tcl": str(tcl),
    "screen_tcl_sha256": sha(tcl),
    "constraint_profile": profile["profile_id"],
    "target_library": str(library),
    "target_library_sha256": sha(library),
    "method": {
        "relink": "unique top-level pageManager instance; no force and no pin map",
        "characterize": "timing plus constraints plus connections",
        "compile": "candidate child only; map_effort medium",
        "expected_page_manager_registers": 62000,
    },
    "exclusions": [
        "top recompilation", "clock relaxation", "state deletion", "PPA",
        "system acceleration", "hardware net benefit",
    ],
}
with (root / "input_manifest.json").open("x") as handle:
    json.dump(manifest, handle, indent=2)
print("KVZAP_PM1_CHARACTERIZED_INPUT_PASS", flush=True)
PY

if ! ulimit -s unlimited 2>/dev/null; then
  echo "unable to raise DC stack limit to unlimited" >&2
  exit 7
fi
[[ $(ulimit -s) == unlimited ]] || {
  echo "DC stack limit is not unlimited" >&2
  exit 7
}
echo "KVZAP_PM1_CHARACTERIZED_STACK_PASS stack_kb=unlimited"

set +e
"$KVZAP_DC_SHELL" -f "$script_dir/screen_pm1_characterized_replacement.tcl" \
  2>&1 | tee "$output_root/dc_shell.log"
code=${PIPESTATUS[0]}
set -e
echo "KVZAP_PM1_CHARACTERIZED_REPLACEMENT_OUTER_EXIT=$code" | tee -a "$output_root/dc_shell.log"
exit "$code"
