#!/usr/bin/env bash
# Freeze/verify the approved numerical baseline and emit static per-top timing
# coverage.  This intentionally does not invoke dc_shell.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env_kvzap_control_projection_dc.sh
source "$script_dir/env_kvzap_control_projection_dc.sh"

fail() { printf 'KVZAP_DC_FAIR_V1_FAIL: %s\n' "$*" >&2; exit 1; }
manifest="$KVZAP_DC_CONSTRAINT_MANIFEST"
coverage_output="${KVZAP_DC_CONSTRAINT_COVERAGE_REPORT:-$KVZAP_DC_HDL_ROOT/dc_feasibility_fair_v1_constraint_coverage.json}"
[[ -f "$manifest" ]] || fail "missing manifest: $manifest"
[[ -f "$KVZAP_DC_HDL_ARCHIVE" ]] || fail "missing archive: $KVZAP_DC_HDL_ARCHIVE"
[[ -f "$KVZAP_DC_TARGET_LIBRARY" ]] || fail "missing library: $KVZAP_DC_TARGET_LIBRARY"

python3 "$script_dir/check_kvzap_control_projection_constraint_coverage.py" \
  --manifest "$manifest" \
  --archive "$KVZAP_DC_HDL_ARCHIVE" \
  --constraints "$script_dir/constraints_control_projection.tcl" \
  --library "$KVZAP_DC_TARGET_LIBRARY" \
  --output "$coverage_output"

python3 - "$manifest" "$coverage_output" \
  "$KVZAP_DC_CONSTRAINT_PROFILE" "$KVZAP_DC_CLOCK_PERIOD_NS" \
  "$KVZAP_DC_CLOCK_SETUP_UNCERTAINTY_NS" "$KVZAP_DC_CLOCK_HOLD_UNCERTAINTY_NS" \
  "$KVZAP_DC_INPUT_DELAY_NS" "$KVZAP_DC_OUTPUT_DELAY_NS" \
  "$KVZAP_DC_INPUT_TRANSITION_NS" "$KVZAP_DC_OUTPUT_LOAD_PF" <<'PY'
import json
import sys
manifest = json.load(open(sys.argv[1]))
report = json.load(open(sys.argv[2]))
observed = sys.argv[3:]
expected = [manifest['profile_id']] + [str(manifest['constraints'][key]) for key in [
    'clock_period_ns', 'setup_uncertainty_ns', 'hold_uncertainty_ns',
    'input_delay_ns', 'output_delay_ns', 'input_transition_ns', 'output_load_pf']]
if observed != expected:
    raise SystemExit('environment values differ from frozen dc_feasibility_fair_v1 manifest')
if not report.get('pass'):
    raise SystemExit('coverage report did not pass')
for top in report['tops'].values():
    if top['unconstrained_inputs'] or top['unconstrained_outputs']:
        raise SystemExit('unexpected unconstrained top-level port')
print('KVZAP_DC_FAIR_V1_PASS: numerical baseline and static per-top coverage frozen; DC ignored-constraint evidence remains deferred until an authorized run.')
PY
