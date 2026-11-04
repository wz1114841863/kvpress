#!/usr/bin/env bash
# Run only the isolated original/shared combinational read-network comparison.
set -euo pipefail
if [[ "${1:-}" == --help ]]; then
  echo 'Usage: run_rd1_read_network_screen.sh PREPARED_NEW_ROOT'
  echo 'Root must contain inputs/*.sv and copied scripts/{environment,constraints,profile,screen}.'
  exit 0
fi
root="${1:?supply an isolated prepared root}"
[[ -d "$root/inputs" && -d "$root/scripts" ]]
[[ ! -e "$root/manifest.json" && ! -e "$root/original" && ! -e "$root/shared" ]]
source "$root/scripts/env_kvzap_control_projection_dc.sh"
export KVZAP_RD1_SCREEN_ROOT="$root"
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
for side in ('original', 'shared'):
    assert (root / f'inputs/rd1_{side}_read_network.sv').is_file()
files = [p for sub in ('inputs', 'scripts', 'source') for p in (root / sub).rglob('*') if p.is_file()]
manifest = {
    'schema': 'kvzap-rd1-isolated-read-network-v1',
    'scope': 'combinational M/S/O member reader only; storage area excluded',
    'geometry': [36, 64, 79],
    'legal_domain': 'at most one valid M/S/O request per bank; valid layers < 36',
    'outputs': 'valid-gated payload for M/S/O; position for S/O; M position constant zero on both sides',
    'profile': profile['profile_id'], 'constraints': profile['constraints'],
    'target_library': str(library), 'target_library_sha256': sha(library),
    'files_sha256': {str(p.relative_to(root)): sha(p) for p in sorted(files)},
    'exclusions': ['full Route-A synthesis', 'storage cost', 'full timing closure', 'PPA', 'system net benefit'],
}
with (root / 'manifest.json').open('x') as f:
    json.dump(manifest, f, indent=2)
print('KVZAP_RD1_SCREEN_INPUT_PASS', flush=True)
PY
cd "$root"
exec "$KVZAP_DC_SHELL" -f "$root/scripts/screen_rd1_read_network.tcl"
