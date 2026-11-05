#!/usr/bin/env bash
# Run the isolated RD2 incremental-read experiment with copied frozen inputs.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "usage: $0 PREPARED_NEW_ROOT"
  echo "Root requires inputs/*.sv and scripts/{environment,constraints,profile,screen}."
  exit 0
fi
[[ $# == 1 ]] || { echo "expected one prepared new root" >&2; exit 2; }
root=$(realpath "$1")
[[ -d $root/inputs && -d $root/scripts && -d $root/source ]]
[[ ! -e $root/manifest.json && ! -e $root/rd1 && ! -e $root/decoded ]]
source "$root/scripts/env_kvzap_control_projection_dc.sh"
export KVZAP_RD2_SCREEN_ROOT="$root"
python3 - "$root" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1])
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
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
library = Path(os.environ['KVZAP_DC_TARGET_LIBRARY'])
assert sha(library) == profile['integrity']['target_library_sha256']
assert sha(root / 'scripts/constraints_control_projection.tcl') == profile['integrity']['constraint_tcl_sha256']
for side in ('rd1', 'decoded'):
    assert (root / f'inputs/rd2_{side}_read_network.sv').is_file()
files = [p for sub in ('inputs', 'scripts', 'source') for p in (root / sub).rglob('*') if p.is_file()]
manifest = {
    'schema': 'kvzap-rd2-isolated-read-network-v1',
    'scope': 'both retain RD1 M/S/O; compare remaining C/F/B member and M/C suffix readers',
    'geometry': [36, 64, 79, 80],
    'legal_domain': 'all layers < 36, ordinals < 64; RD1 same-bank M/S/O exclusion only',
    'raw_reads': 'all four remaining reads observable continuously, including valid-low cycles',
    'profile': profile['profile_id'], 'constraints': profile['constraints'],
    'target_library': str(library), 'target_library_sha256': sha(library),
    'files_sha256': {str(p.relative_to(root)): sha(p) for p in sorted(files)},
    'exclusions': ['storage cost', 'production wrapper integration', 'complete top DC', 'PPA', 'system benefit'],
}
with (root / 'manifest.json').open('x') as handle:
    json.dump(manifest, handle, indent=2)
print('KVZAP_RD2_SCREEN_INPUT_PASS', flush=True)
PY
ulimit -s unlimited
[[ $(ulimit -s) == unlimited ]]
echo KVZAP_RD2_SCREEN_STACK_PASS
cd "$root"
failed=0
for side in rd1 decoded; do
  export KVZAP_RD2_SCREEN_SIDE="$side"
  set +e
  "$KVZAP_DC_SHELL" -f "$root/scripts/screen_rd2_read_network.tcl" 2>&1 | tee "$root/${side}_dc_shell.log"
  statuses=("${PIPESTATUS[@]}")
  set -e
  code=${statuses[0]}
  if (( statuses[1] != 0 )); then code=9; fi
  echo "KVZAP_RD2_SCREEN_SIDE_EXIT side=$side code=$code"
  if (( code != 0 )); then failed=1; fi
done
if (( failed != 0 )); then exit 1; fi
python3 - "$root" <<'PY'
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
manifest = json.loads((root / 'manifest.json').read_text())
import hashlib
for relative, expected in manifest['files_sha256'].items():
    assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, relative
for side in ('rd1', 'decoded'):
    log = (root / f'{side}_dc_shell.log').read_text(errors='replace')
    assert not re.search(r'^\s*(?:Error|Fatal):', log, re.M), f'native error: {side}'
    assert f'KVZAP_RD2_SCREEN_SIDE_PASS side={side}' in log
    out = root / side
    top = f'rd2_{side}_read_network'
    for name in ('resources_precompile.rpt', 'check_design.rpt', 'check_timing.rpt',
                 'clocks.rpt', 'qor.rpt', 'area.rpt', 'timing_setup.rpt',
                 'timing_hold.rpt', 'constraints.rpt', 'summary.tsv',
                 f'{top}.ddc', f'{top}_mapped.v'):
        path = out / name
        assert path.is_file() and path.stat().st_size > 0, path
    assert (out / 'summary.tsv').read_text() == f'metric\tvalue\nside\t{side}\nregisters\t0\n'
print('KVZAP_RD2_SCREEN_POSTCHECK_PASS')
PY
echo KVZAP_RD2_READ_NETWORK_SCREEN_PASS
