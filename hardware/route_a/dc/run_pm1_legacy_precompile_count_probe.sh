#!/usr/bin/env bash
# Establish the frozen legacy raw-child precompile register count under the
# same unlimited-stack DC analyze/elaborate/link path as PM1 r2.
set -euo pipefail

if [[ "${1:-}" == --help ]]; then
  echo "usage: $0 OUTPUT_ROOT BASELINE_DDC LEGACY_SV PM1_SV"
  exit 0
fi
if [[ $# -ne 4 ]]; then
  echo "usage: $0 OUTPUT_ROOT BASELINE_DDC LEGACY_SV PM1_SV" >&2
  exit 2
fi

output_root=$1
baseline_ddc=$2
legacy_sv=$3
pm1_sv=$4
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
expected_ddc_sha=29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326
expected_legacy_sha=f5e3299f9af08b05ac1de3c2a09967303fa2294f4c31dc2b81f7dccb3bde97b4
expected_pm1_sha=dfaf40814b0372962b1720c7c9289271d6dc60158fc0d2b09238e3bbe0496671

[[ ! -e $output_root ]] || { echo "refusing to overwrite $output_root" >&2; exit 3; }
for input in "$baseline_ddc" "$legacy_sv" "$pm1_sv"; do
  [[ -f $input ]] || { echo "missing input: $input" >&2; exit 4; }
done

source "$script_dir/env_kvzap_control_projection_dc.sh"
mkdir -p "$output_root/inputs"
legacy_probe_sv=$output_root/inputs/route_a_page_manager_legacy_raw_probe.sv
export KVZAP_PM1_LEGACY_COUNT_ROOT="$output_root"
export KVZAP_PM1_BASELINE_DDC="$baseline_ddc"
export KVZAP_PM1_LEGACY_PROBE_SV="$legacy_probe_sv"

python3 - "$output_root" "$baseline_ddc" "$legacy_sv" "$pm1_sv" \
  "$legacy_probe_sv" "$script_dir/probe_pm1_legacy_precompile_count.tcl" \
  "$expected_ddc_sha" "$expected_legacy_sha" "$expected_pm1_sha" <<'PY'
import hashlib
import json
import os
import re
from pathlib import Path
import sys

(root, ddc, legacy, pm1, probe, tcl) = map(Path, sys.argv[1:7])
expected_ddc, expected_legacy, expected_pm1 = sys.argv[7:10]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for path, expected, label in (
    (ddc, expected_ddc, "accepted DDC"),
    (legacy, expected_legacy, "frozen legacy child"),
    (pm1, expected_pm1, "accepted PM1 child"),
):
    if sha(path) != expected:
        raise SystemExit(f"{label} hash mismatch")

decl_re = re.compile(r"^\s*reg\s+(?:\[(\d+):(\d+)\]\s+)?([A-Za-z_][A-Za-z0-9_$]*);\s*$")
nba_re = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_$]*)(?:\[[^]]+\])?\s*<=")
def scan(path):
    declarations = {}
    targets = set()
    with path.open() as handle:
        for line in handle:
            match = decl_re.match(line)
            if match:
                high, low, name = match.groups()
                declarations[name] = 1 if high is None else abs(int(high) - int(low)) + 1
            match = nba_re.match(line)
            if match:
                targets.add(match.group(1))
    return declarations, targets

legacy_declarations, legacy_targets = scan(legacy)
pm1_declarations, pm1_targets = scan(pm1)
if legacy_declarations != pm1_declarations:
    raise SystemExit("legacy/PM1 sequential declarations differ")
if legacy_targets != pm1_targets:
    raise SystemExit("legacy/PM1 nonblocking assignment targets differ")

old = b"module route_a_page_manager("
new = b"module route_a_page_manager_legacy_raw_probe("
replacements = 0
with legacy.open("rb") as source, probe.open("xb") as destination:
    for line in source:
        count = line.count(old)
        replacements += count
        destination.write(line.replace(old, new))
if replacements != 1:
    raise SystemExit(f"expected one legacy module rename, found {replacements}")

profile = json.loads(Path(os.environ["KVZAP_DC_CONSTRAINT_MANIFEST"]).read_text())
if profile["profile_id"] != "dc_feasibility_fair_v1":
    raise SystemExit("unexpected constraint profile")
library = Path(os.environ["KVZAP_DC_TARGET_LIBRARY"])
if sha(library) != profile["integrity"]["target_library_sha256"]:
    raise SystemExit("target library hash mismatch")

manifest = {
    "schema": "kvzap-pm1-legacy-precompile-count-v1",
    "baseline_ddc": str(ddc),
    "baseline_ddc_sha256": sha(ddc),
    "legacy_sv": str(legacy),
    "legacy_sv_sha256": sha(legacy),
    "pm1_sv": str(pm1),
    "pm1_sv_sha256": sha(pm1),
    "legacy_probe_sv": str(probe),
    "legacy_probe_sv_sha256": sha(probe),
    "probe_tcl": str(tcl),
    "probe_tcl_sha256": sha(tcl),
    "constraint_profile": profile["profile_id"],
    "target_library": str(library),
    "target_library_sha256": sha(library),
    "raw_state_equivalence": {
        "declaration_objects": len(legacy_declarations),
        "declaration_bits": sum(legacy_declarations.values()),
        "nonblocking_targets": len(legacy_targets),
        "added_declarations": 0,
        "removed_declarations": 0,
        "width_mismatches": 0,
        "added_nonblocking_targets": 0,
        "removed_nonblocking_targets": 0,
    },
    "scope": "analyze/elaborate/link/count only; no compile, characterize, relink or constraint change",
}
with (root / "input_manifest.json").open("x") as handle:
    json.dump(manifest, handle, indent=2)
print("KVZAP_PM1_LEGACY_COUNT_INPUT_PASS", flush=True)
PY

if ! ulimit -s unlimited 2>/dev/null; then
  echo "unable to raise DC stack limit to unlimited" >&2
  exit 5
fi
[[ $(ulimit -s) == unlimited ]] || { echo "DC stack limit is not unlimited" >&2; exit 5; }
echo "KVZAP_PM1_LEGACY_COUNT_STACK_PASS stack_kb=unlimited"

set +e
"$KVZAP_DC_SHELL" -f "$script_dir/probe_pm1_legacy_precompile_count.tcl" \
  2>&1 | tee "$output_root/dc_shell.log"
code=${PIPESTATUS[0]}
set -e
echo "KVZAP_PM1_LEGACY_PRECOMPILE_COUNT_OUTER_EXIT=$code" | tee -a "$output_root/dc_shell.log"
exit "$code"
