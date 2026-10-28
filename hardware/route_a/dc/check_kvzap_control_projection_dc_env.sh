#!/usr/bin/env bash
# Read-only preflight for the paired KVZap control-projection DC environment.
# It does not run analyze, elaborate, link, compile, or any PPA command.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env_kvzap_control_projection_dc.sh
source "$script_dir/env_kvzap_control_projection_dc.sh"

fail() { printf 'KVZAP_DC_ENVIRONMENT_FAIL: %s\n' "$*" >&2; exit 1; }
note() { printf 'KVZAP_DC_ENVIRONMENT: %s\n' "$*"; }
require_file() { [[ -f "$1" ]] || fail "missing file: $1"; }
require_dir() { [[ -d "$1" ]] || fail "missing directory: $1"; }

require_file "$KVZAP_DC_SHELL"
[[ -x "$KVZAP_DC_SHELL" ]] || fail "dc_shell is not executable: $KVZAP_DC_SHELL"
require_dir "$KVZAP_DC_PDK_ROOT"
require_file "$KVZAP_DC_TARGET_LIBRARY"
require_dir "$KVZAP_DC_HDL_ROOT"
require_file "$KVZAP_DC_HDL_ARCHIVE"

full_filelist="$KVZAP_DC_HDL_ROOT/full_kv_control_projection.f"
route_dir="$KVZAP_DC_HDL_ROOT/route_a_control_projection_split"
route_filelist="$route_dir/route_a_control_projection.f"
require_file "$KVZAP_DC_HDL_ROOT/full_kv_control_projection.sv"
require_file "$full_filelist"
require_dir "$route_dir"
require_file "$route_dir/route_a_control_projection.sv"
require_file "$route_filelist"

check_filelist() {
  local root=$1 list=$2 expected_count=$3 top=$4
  local line count=0
  declare -A seen=()
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ -f "$root/$line" ]] || fail "$top filelist refers to missing SV: $root/$line"
    [[ -z "${seen[$line]+x}" ]] || fail "$top filelist has a duplicate SV: $line"
    seen[$line]=1
    count=$((count + 1))
  done < "$list"
  [[ $count -eq $expected_count ]] || fail "$top filelist count is $count, expected $expected_count"
  grep -Eq "^module ${top}(\\s|\\(|$)" "$root/${top}.sv" || fail "missing top module ${top}"
  note "$top filelist_count=$count top_present=yes"
}

check_filelist "$KVZAP_DC_HDL_ROOT" "$full_filelist" 1 full_kv_control_projection
check_filelist "$route_dir" "$route_filelist" 182 route_a_control_projection

archive_expected=335942f0f01c24124b1fda56c6ebbd8b3425afdb2c31220cac04ff871aa94310
archive_actual=$(sha256sum "$KVZAP_DC_HDL_ARCHIVE" | awk '{print $1}')
[[ "$archive_actual" == "$archive_expected" ]] || fail "HDL archive SHA-256 differs: $archive_actual"

set +e
dc_version=$("$KVZAP_DC_SHELL" -version 2>&1)
dc_version_status=$?
set -e
# The installed O-2018.06-SP1 dc_shell prints a complete version/site banner
# but exits 1 for `-version` without a Tcl invocation.  Treat the documented
# banner as the availability proof and record the unusual status; do not mask
# an actual missing binary or a different tool release.
printf '%s\n' "$dc_version" | grep -Fq 'dc_shell version    -  O-2018.06-SP1' || {
  printf '%s\n' "$dc_version" >&2
  fail "dc_shell did not return the expected version banner"
}
printf '%s\n' "$dc_version" | grep -Fq 'O-2018.06-SP1' || fail "unexpected DC version output"

note "dc_shell=$KVZAP_DC_SHELL"
note "dc_shell_version_exit_status=$dc_version_status (expected for O-2018.06-SP1 -version)"
note "target_library=$KVZAP_DC_TARGET_LIBRARY"
note "target_library_sha256=$(sha256sum "$KVZAP_DC_TARGET_LIBRARY" | awk '{print $1}')"
note "hdl_archive_sha256=$archive_actual"
note "run_root_not_created=$KVZAP_DC_RUN_ROOT"
note "ARRAY_BLACKBOX_TREATMENT=unselected"
note "EXTERNAL_SERVICE_STUB_TREATMENT=unselected"
note "CLOCK_RESET_CONSTRAINTS=unselected"
printf '%s\n' 'KVZAP_DC_ENVIRONMENT_PASS: tools, feasibility-library candidate, and independent HDL inputs are present; this does not authorize or launch DC.'
