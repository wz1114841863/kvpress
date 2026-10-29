#!/usr/bin/env bash
# Usage (on dc-server):
#   source hardware/route_a/dc/env_kvzap_control_projection_dc.sh
#   hardware/route_a/dc/run_kvzap_control_projection_dc_feasibility.sh <immutable-run-id>
#
# The caller must provide a new immutable run id.  This runs each selected
# control projection under the identical dc_feasibility_fair_v1 constraints.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env_kvzap_control_projection_dc.sh
source "$script_dir/env_kvzap_control_projection_dc.sh"

fail() { printf 'KVZAP_DC_FEASIBILITY_FAIL: %s\n' "$*" >&2; exit 1; }
run_id="${1:-}"
[[ "$run_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail "supply a safe immutable run id"
base="$KVZAP_DC_RUN_ROOT/$run_id"
[[ ! -e "$base" ]] || fail "run id already exists: $base"
[[ -x "$KVZAP_DC_SHELL" ]] || fail "missing dc_shell: $KVZAP_DC_SHELL"
[[ -f "$KVZAP_DC_TARGET_LIBRARY" ]] || fail "missing target library: $KVZAP_DC_TARGET_LIBRARY"
[[ -d "$KVZAP_DC_PROXY_ROOT" ]] || fail "missing checked proxy root: $KVZAP_DC_PROXY_ROOT"

python3 - "$KVZAP_DC_PROXY_ROOT" "$KVZAP_DC_HDL_ARCHIVE" <<'PY'
import hashlib
import json
import os
import sys

root, archive = sys.argv[1:]
for name in ('dc_array_proxy_materialization_report.json', 'dc_array_proxy_check_report.json'):
    path = os.path.join(root, name)
    if not os.path.isfile(path):
        raise SystemExit('missing proxy evidence: ' + path)
    if not json.load(open(path)).get('pass'):
        raise SystemExit('proxy evidence did not pass: ' + path)
materialization = json.load(open(os.path.join(root, 'dc_array_proxy_materialization_report.json')))
observed = hashlib.sha256(open(archive, 'rb').read()).hexdigest()
if materialization.get('input_hdl_archive_sha256') != observed:
    raise SystemExit('proxy materialization archive identity differs from frozen archive')
print('KVZAP_DC_PROXY_EVIDENCE_PASS boundaries=%d' % len(materialization.get('boundaries', [])))
PY

mkdir -p "$base"
export KVZAP_DC_CONSTRAINT_COVERAGE_REPORT="$base/static_constraint_coverage.json"
"$script_dir/check_kvzap_control_projection_dc_feasibility_fair_v1.sh"

cp "$KVZAP_DC_CONSTRAINT_MANIFEST" "$base/dc_feasibility_fair_v1.json"
cp "$script_dir/constraints_control_projection.tcl" "$base/constraints_control_projection.tcl"
cp "$KVZAP_DC_ARRAY_PROXY_MANIFEST" "$base/array_proxy_manifest.json"
cp "$KVZAP_DC_PROXY_ROOT/dc_array_proxy_materialization_report.json" "$base/array_proxy_materialization.json"
cp "$KVZAP_DC_PROXY_ROOT/dc_array_proxy_check_report.json" "$base/array_proxy_check.json"
sha256sum "$KVZAP_DC_TARGET_LIBRARY" "$KVZAP_DC_HDL_ARCHIVE" \
  "$KVZAP_DC_PROXY_ROOT/dc_array_proxy_materialization_report.json" \
  "$KVZAP_DC_PROXY_ROOT/dc_array_proxy_check_report.json" > "$base/input_sha256.txt"

run_top() {
  local id="$1" top="$2" list_rel="$3" root_rel="$4" modules="$5"
  local list_root="$KVZAP_DC_PROXY_ROOT/$root_rel"
  local filelist="$KVZAP_DC_PROXY_ROOT/$list_rel"
  local run_dir="$base/$id"
  [[ -f "$filelist" ]] || fail "missing $id filelist: $filelist"
  [[ -d "$list_root" ]] || fail "missing $id filelist root: $list_root"
  mkdir -p "$run_dir"
  python3 - "$run_dir/manifest.json" "$id" "$top" "$filelist" "$list_root" "$modules" <<'PY'
import json
import os
import sys

path, side, top, filelist, root, modules = sys.argv[1:]
json.dump({
    'schema_version': 'kvzap-dc-feasibility-run-v1',
    'profile_id': os.environ['KVZAP_DC_CONSTRAINT_PROFILE'],
    'side': side,
    'top_module': top,
    'proxy_filelist': filelist,
    'proxy_filelist_root': root,
    'array_proxy_modules': modules.split(','),
    'target_library': os.environ['KVZAP_DC_TARGET_LIBRARY'],
    'clock_period_ns': os.environ['KVZAP_DC_CLOCK_PERIOD_NS'],
    'setup_uncertainty_ns': os.environ['KVZAP_DC_CLOCK_SETUP_UNCERTAINTY_NS'],
    'hold_uncertainty_ns': os.environ['KVZAP_DC_CLOCK_HOLD_UNCERTAINTY_NS'],
    'input_delay_ns': os.environ['KVZAP_DC_INPUT_DELAY_NS'],
    'output_delay_ns': os.environ['KVZAP_DC_OUTPUT_DELAY_NS'],
    'input_transition_ns': os.environ['KVZAP_DC_INPUT_TRANSITION_NS'],
    'output_load_pf': os.environ['KVZAP_DC_OUTPUT_LOAD_PF'],
    'scope': 'DC feasibility only; no macro, CACTI, PPA or external-service-zero-cost claim',
}, open(path, 'w'), indent=2, sort_keys=True)
PY
  set +e
  (
    cd "$run_dir"
    export KVZAP_DC_TOP="$top"
    export KVZAP_DC_FILELIST="$filelist"
    export KVZAP_DC_FILELIST_ROOT="$list_root"
    export KVZAP_DC_REPORT_DIR="$run_dir"
    export KVZAP_DC_ARRAY_PROXY_MODULES="$modules"
    # DC 2018's parser must receive enough process stack for the frozen,
    # generated control HDL.  This is an execution-environment setting only;
    # it does not waive the prohibition on synthesizing functional-reference
    # storage as ordinary logic.
    ulimit -s unlimited 2>/dev/null || true
    "$KVZAP_DC_SHELL" -f "$script_dir/run_kvzap_control_projection_dc_feasibility.tcl"
  ) 2>&1 | tee "$run_dir/dc_shell.log"
  local rc=${PIPESTATUS[0]}
  set -e
  printf 'KVZAP_DC_FEASIBILITY_%s_EXIT=%s\n' "${id^^}" "$rc" | tee -a "$run_dir/dc_shell.log"
  [[ "$rc" -eq 0 ]] || return "$rc"
}

run_top full_kv full_kv_control_projection "$KVZAP_DC_FULL_FILELIST" '' \
  full_kv_s2_payload_array_boundary || exit $?
run_top route_a route_a_control_projection \
  "$KVZAP_DC_ROUTE_FILELIST" \
  "$KVZAP_DC_ROUTE_FILELIST_ROOT" \
  route_a_m2_entry_array_boundary,route_a_p3_stage_array_boundary,route_a_r5_availability_array_boundary,route_a_s2_payload_sidecar_array_boundary || exit $?
printf 'KVZAP_DC_FEASIBILITY_RUN_PASS run_id=%s\n' "$run_id" | tee -a "$base/run.log"
