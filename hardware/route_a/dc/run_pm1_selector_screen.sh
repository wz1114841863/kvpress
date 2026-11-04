#!/usr/bin/env bash
# Run only the isolated original/banked exact-priority selector comparison.
set -euo pipefail
if [[ "${1:-}" == --help ]]; then
  echo 'Usage: run_pm1_selector_screen.sh PREPARED_NEW_ROOT'
  echo 'Root must contain inputs/*.sv and copied scripts/{environment,constraints,profile,screen}.'
  exit 0
fi
root="${1:?supply an isolated prepared root}"
[[ -d "$root/inputs" && -d "$root/scripts" ]]
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
    assert (root / f'inputs/pm1_{side}_selector.sv').is_file()
files = [p for sub in ('inputs', 'scripts', 'source') for p in (root / sub).rglob('*') if p.is_file()]
manifest = {
    'schema': 'kvzap-pm1-isolated-exact-priority-selector-v1',
    'scope': 'combinational allocatedLine lowest-index selector only; state and Page Manager control excluded',
    'geometry': {'entries': 36720, 'index_bits': 16, 'candidate_bank_size': 64, 'candidate_banks': 574},
    'semantics': 'selected_valid is OR reduction; selected_index is exact lowest set bit; empty index preserves Chisel PriorityEncoder terminal-index convention',
    'profile': profile['profile_id'], 'constraints': profile['constraints'],
    'target_library': str(library), 'target_library_sha256': sha(library),
    'files_sha256': {str(p.relative_to(root)): sha(p) for p in sorted(files)},
    'exclusions': ['allocatedLine storage', 'Page Manager state/control', 'full Route-A synthesis', 'PPA', 'system net benefit'],
}
with (root / 'manifest.json').open('x') as f:
    json.dump(manifest, f, indent=2)
print('KVZAP_PM1_SCREEN_INPUT_PASS', flush=True)
PY
cd "$root"
set +e
"$KVZAP_DC_SHELL" -f "$root/scripts/screen_pm1_selector.tcl"
code=$?
set -e
echo "KVZAP_PM1_SELECTOR_SCREEN_OUTER_EXIT=$code"
exit "$code"
