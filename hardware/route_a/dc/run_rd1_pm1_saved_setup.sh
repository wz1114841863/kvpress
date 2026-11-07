#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo 'Usage: bash run_rd1_pm1_saved_setup.sh NEW_ROOT FROZEN_TCL TCL_SHA256'
  exit 0
fi
[[ $# == 3 ]]
diag_root=$1
diag_tcl=$2
diag_sha=$3
[[ ! -e "$diag_root" && -f "$diag_tcl" ]]
[[ $(sha256sum "$diag_tcl" | cut -d ' ' -f1) == "$diag_sha" ]]
mkdir -p "$diag_root"
exec > >(tee "$diag_root/launcher.log") 2>&1
trap 'status=$?; echo "$status" > "$diag_root/exit_status"; echo "KVZAP_RD1_PM1_SETUP_OUTER_EXIT=$status"' EXIT
ulimit -s unlimited
export LM_LICENSE_FILE=${LM_LICENSE_FILE:-27000@ercesi413}
export KVZAP_DIAG_LIBRARY=/home/yaz80/wz_project/dc_project/pdk/TSMC28/tcbn28hpcplusbwp12t30p140lvtssg0p81v125c.db
[[ $(sha256sum "$KVZAP_DIAG_LIBRARY" | cut -d ' ' -f1) == 5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d ]]
awk '/MemAvailable:/ {if ($2 < 16777216) exit 1}' /proc/meminfo
diag_runs=/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs
for side in rd1 rd1_pm1; do
  if [[ $side == rd1 ]]; then
    diag_id=dc_feasibility_fair_rd1_shared_20261105_r1
    diag_ddc_sha=86993ae45bd58463ba4a18b67f12bc2fac864cd146004fd3c9a3c5a8481b5673
  else
    diag_id=dc_feasibility_fair_rd1_pm1_20261106_r1
    diag_ddc_sha=cb160cfb13219c6cca2c8b99ebe498214d5048556c4113b7746944884ef8e73a
  fi
  export KVZAP_DIAG_DDC=$diag_runs/$diag_id/route_a/route_a_control_projection.ddc
  export KVZAP_DIAG_OUT=$diag_root/$side
  [[ $(sha256sum "$KVZAP_DIAG_DDC" | cut -d ' ' -f1) == "$diag_ddc_sha" ]]
  mkdir "$KVZAP_DIAG_OUT"
  sha256sum "$KVZAP_DIAG_DDC" "$KVZAP_DIAG_LIBRARY" "$diag_tcl" > "$KVZAP_DIAG_OUT/input_sha256.txt"
  echo "KVZAP_RD1_PM1_SETUP_START side=$side"
  status=0
  (cd "$KVZAP_DIAG_OUT" && nice -n 10 /opt/synopsys/dc2018/O-2018.06-SP1/bin/dc_shell -f "$diag_tcl") > "$KVZAP_DIAG_OUT/native.log" 2>&1 || status=$?
  echo "$status" > "$KVZAP_DIAG_OUT/exit_status"
  [[ $status == 0 ]]
  grep -q '^KVZAP_RD1_PM1_SAVED_SETUP_PASS ' "$KVZAP_DIAG_OUT/native.log"
  if grep -Eq '^[[:space:]]*(Error:|Fatal:)' "$KVZAP_DIAG_OUT/native.log"; then exit 7; fi
  if grep -Eq '^[[:space:]]*(Error:|Fatal:)' "$KVZAP_DIAG_OUT"/*.rpt; then exit 7; fi
  sha256sum -c "$KVZAP_DIAG_OUT/input_sha256.txt"
  echo "KVZAP_RD1_PM1_SETUP_SIDE_EXIT side=$side exit=0"
done
echo KVZAP_RD1_PM1_SETUP_RUN_PASS_TOOL_ARTIFACT_ONLY
