#!/usr/bin/env bash
# Run the registered original/banked PM1 selector sides in independent DC processes.
set -euo pipefail
if [[ "${1:-}" == --help ]]; then
  echo 'Usage: run_pm1_registered_selector_screen.sh PREPARED_NEW_ROOT'
  echo 'Root must contain registered inputs and copied environment/constraints/profile/side-screen scripts.'
  exit 0
fi
root="${1:?supply an isolated prepared root}"
[[ -d "$root/inputs" && -d "$root/scripts" && -d "$root/source" ]]
[[ ! -e "$root/manifest.json" && ! -e "$root/original" && ! -e "$root/banked" ]]
source "$root/scripts/env_kvzap_control_projection_dc.sh"
export KVZAP_PM1_SCREEN_ROOT="$root"
python3 - "$root" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
profile = json.loads((root / 'scripts/dc_feasibility_fair_r5_descriptor_successor_v1.json').read_text())
assert profile['profile_id'] == os.environ['KVZAP_DC_CONSTRAINT_PROFILE'] == 'dc_feasibility_fair_v1'
for key, env in (
    ('clock_period_ns', 'KVZAP_DC_CLOCK_PERIOD_NS'),
    ('setup_uncertainty_ns', 'KVZAP_DC_CLOCK_SETUP_UNCERTAINTY_NS'),
    ('hold_uncertainty_ns', 'KVZAP_DC_CLOCK_HOLD_UNCERTAINTY_NS'),
    ('input_delay_ns', 'KVZAP_DC_INPUT_DELAY_NS'),
    ('output_delay_ns', 'KVZAP_DC_OUTPUT_DELAY_NS'),
    ('input_transition_ns', 'KVZAP_DC_INPUT_TRANSITION_NS'),
    ('output_load_pf', 'KVZAP_DC_OUTPUT_LOAD_PF'),
):
    assert os.environ[env] == profile['constraints'][key], env
library = Path(os.environ['KVZAP_DC_TARGET_LIBRARY'])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(library) == profile['integrity']['target_library_sha256']
assert sha(root / 'scripts/constraints_control_projection.tcl') == profile['integrity']['constraint_tcl_sha256']
for side in ('original', 'banked'):
    assert (root / f'inputs/pm1_{side}_registered_selector.sv').is_file()
files = [p for sub in ('inputs', 'scripts', 'source') for p in (root / sub).rglob('*') if p.is_file()]
manifest = {
    'schema': 'kvzap-pm1-registered-exact-priority-selector-v2',
    'scope': 'matched 36720-bit state Q to exact selector to registered D; production Page Manager control excluded',
    'geometry': {'entries': 36720, 'index_bits': 16, 'candidate_bank_size': 64, 'candidate_banks': 574},
    'matched_boundaries': {'state_register_bits': 36720, 'result_register_bits': 17, 'state_feed': 'serial shift'},
    'semantics': 'cycle-exact valid and lowest-index result; empty raw index convention retained',
    'process_isolation': 'one dc_shell process per side',
    'profile': profile['profile_id'], 'constraints': profile['constraints'],
    'target_library': str(library), 'target_library_sha256': sha(library),
    'files_sha256': {str(p.relative_to(root)): sha(p) for p in sorted(files)},
    'exclusions': ['production Page Manager update logic', 'full Route-A synthesis', 'PPA', 'system net benefit'],
}
with (root / 'manifest.json').open('x') as f:
    json.dump(manifest, f, indent=2)
print('KVZAP_PM1_REGISTERED_SCREEN_INPUT_PASS', flush=True)
PY

overall=0
for side in original banked; do
  export KVZAP_PM1_SCREEN_SIDE="$side"
  side_log="$root/${side}_dc_shell.log"
  set +e
  "$KVZAP_DC_SHELL" -f "$root/scripts/screen_pm1_registered_selector_side.tcl" 2>&1 | tee "$side_log"
  side_code=${PIPESTATUS[0]}
  set -e
  echo "KVZAP_PM1_REGISTERED_SCREEN_SIDE_OUTER_EXIT side=$side code=$side_code" | tee -a "$side_log"
  if [[ "$side_code" -ne 0 ]]; then overall=1; fi
done
if [[ "$overall" -eq 0 ]]; then
  echo KVZAP_PM1_REGISTERED_SELECTOR_SCREEN_PASS
else
  echo KVZAP_PM1_REGISTERED_SELECTOR_SCREEN_FAIL
fi
echo "KVZAP_PM1_REGISTERED_SELECTOR_SCREEN_OUTER_EXIT=$overall"
exit "$overall"
