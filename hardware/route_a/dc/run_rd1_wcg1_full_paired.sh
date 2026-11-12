#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo 'Usage: bash run_rd1_wcg1_full_paired.sh NEW_STEM NEW_RUN_ID FROZEN_BUNDLE CONTEXT_ROOT'
  exit 0
fi
[[ $# == 4 ]]
stem=$1
run_id=$2
bundle=$3
context=$4
[[ "$run_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]
source_root=/home/yaz80/wz_project/chisel_projects/kvpress/artifacts
baseline=$source_root/rd1_shared_e5d3107_p15_paired_input
result=/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/$run_id
[[ ! -e "$stem" && ! -e "$result" ]]
mkdir -p "$result"
trap 'status=$?; echo "$status" > "$result/exit_status"; echo "KVZAP_RD1_WCG1_OUTER_EXIT=$status"' EXIT
(cd "$bundle" && sha256sum -c SHA256SUMS)
ulimit -s unlimited
awk '/MemAvailable:/ {if ($2 < 33554432) exit 1}' /proc/meminfo
export KVZAP_DC_SCRIPT_DIR=$bundle
source "$bundle/env_kvzap_control_projection_dc.sh"
[[ $(sha256sum "$KVZAP_DC_TARGET_LIBRARY" | cut -d ' ' -f1) == 5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d ]]
python3 "$bundle/freeze_rd1_wcg1_input.py" --baseline "$baseline" --context-root "$context" --accepted-launch "$bundle/accepted_wcg1_launch.json" --output "$stem"
python3 "$bundle/check_r5_descriptor_externalization_successor.py" --root "$stem" --report "$stem/r5_check.json"
python3 "$bundle/check_control_refinement_successor.py" --root "$stem" --baseline-root "$baseline" --report "$stem/state_check.json"
export KVZAP_DC_SCRIPTS=$bundle
bash "$bundle/materialize_control_refinement_proxy.sh" "$stem" "$baseline" "$stem" "$source_root/rd1_shared_e5d3107_p15_dc_array_proxy_manifest.json"
python3 - "$bundle/dc_feasibility_fair_rd1_shared_v1.json" "$stem" <<'PY'
from pathlib import Path
import hashlib,json,sys
p=json.load(open(sys.argv[1]));s=Path(sys.argv[2])
p['source_successor']=s.name
p['source_freeze']='analysis/hardware_reports/04_area_timing_optimization_and_design_review.md'
p['status']='approved_RD1_WCG1_PM1_off_RD2_excluded_pending_result'
p['integrity']['hdl_archive_sha256']=hashlib.sha256(Path(str(s)+'_paired_input.tar.gz').read_bytes()).hexdigest()
p['tops']['route_a']['expected_file_count']=49
(s/'dc_profile.json').write_text(json.dumps(p,indent=2)+'\n')
PY
export KVZAP_DC_HDL_ROOT=${stem}_paired_input
export KVZAP_DC_HDL_ARCHIVE=${stem}_paired_input.tar.gz
export KVZAP_DC_HDL_ARCHIVE_SHA256
KVZAP_DC_HDL_ARCHIVE_SHA256=$(sha256sum "$KVZAP_DC_HDL_ARCHIVE" | cut -d ' ' -f1)
export KVZAP_DC_PROXY_ROOT=${stem}_dc_array_proxy_r1
export KVZAP_DC_ARRAY_PROXY_MANIFEST=${stem}_dc_array_proxy_manifest.json
export KVZAP_DC_CONSTRAINT_MANIFEST=$stem/dc_profile.json
export KVZAP_DC_ROUTE_FILELIST_COUNT=49
export KVZAP_DC_ENTRY_ID_DRIVER_POLICY=r3_entry_id_driver_v1
export KVZAP_DC_CONSTRAINT_COVERAGE_REPORT=$result/static_constraint_coverage.json
bash "$bundle/check_kvzap_control_projection_dc_feasibility_fair_v1.sh"
cp "$stem/composition.json" "$result/composition.json"
cp "$stem/dc_profile.json" "$result/dc_feasibility_fair_v1.json"
cp "$KVZAP_DC_ARRAY_PROXY_MANIFEST" "$result/array_proxy_manifest.json"
cp "$KVZAP_DC_PROXY_ROOT/dc_array_proxy_materialization_report.json" "$result/array_proxy_materialization.json"
cp "$KVZAP_DC_PROXY_ROOT/dc_array_proxy_check_report.json" "$result/array_proxy_check.json"
cp "$bundle/constraints_control_projection.tcl" "$result/constraints_control_projection.tcl"
sha256sum "$KVZAP_DC_HDL_ARCHIVE" "$KVZAP_DC_TARGET_LIBRARY" "$KVZAP_DC_ARRAY_PROXY_MANIFEST" "$bundle/run_rd1_wcg1_full_paired.tcl" > "$result/input_sha256.txt"
(cd "$KVZAP_DC_PROXY_ROOT" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$result/proxy_source_sha256.txt"
echo KVZAP_RD1_WCG1_INPUT_FREEZE_PASS_STARTING_PAIRED_DC
export KVZAP_DC_TOP=route_a_control_projection
export KVZAP_DC_REPORT_DIR=$result/native_binding
export KVZAP_DC_FILELIST_ROOT=$KVZAP_DC_PROXY_ROOT
export KVZAP_DC_FILELIST=$KVZAP_DC_PROXY_ROOT/route_a_control_projection_successor.f
export KVZAP_DC_ARRAY_PROXY_MODULES=route_a_m2_entry_array_boundary,route_a_p3_stage_array_boundary,route_a_r5_availability_array_boundary,route_a_s2_payload_sidecar_array_boundary
mkdir "$KVZAP_DC_REPORT_DIR"
echo KVZAP_RD1_WCG1_FULL_NATIVE_BINDING_START
(cd "$KVZAP_DC_REPORT_DIR" && KVZAP_WCG1_BINDING_ONLY=1 nice -n 10 "$KVZAP_DC_SHELL" -f "$bundle/run_rd1_wcg1_full_paired.tcl") > "$KVZAP_DC_REPORT_DIR/native.log" 2>&1
grep -q '^KVZAP_RD1_WCG1_FULL_NATIVE_BINDING_PASS gates=4608 proxies=4 period_ns=2' "$KVZAP_DC_REPORT_DIR/native.log"
if grep -Eq '^[[:space:]]*(Error:|Fatal:)' "$KVZAP_DC_REPORT_DIR/native.log" "$KVZAP_DC_REPORT_DIR"/*.rpt; then exit 7; fi
echo KVZAP_RD1_WCG1_NATIVE_BINDING_CLOSED_STARTING_FORMAL_PAIR
for side in full_kv route_a; do
  export KVZAP_DC_TOP=${side}_control_projection
  export KVZAP_DC_REPORT_DIR=$result/$side
  export KVZAP_DC_FILELIST_ROOT=$KVZAP_DC_PROXY_ROOT
  if [[ $side == full_kv ]]; then
    export KVZAP_DC_FILELIST=$KVZAP_DC_PROXY_ROOT/full_kv_control_projection.f
    export KVZAP_DC_ARRAY_PROXY_MODULES=full_kv_s2_payload_array_boundary
  else
    export KVZAP_DC_FILELIST=$KVZAP_DC_PROXY_ROOT/route_a_control_projection_successor.f
    export KVZAP_DC_ARRAY_PROXY_MODULES=route_a_m2_entry_array_boundary,route_a_p3_stage_array_boundary,route_a_r5_availability_array_boundary,route_a_s2_payload_sidecar_array_boundary
  fi
  mkdir "$KVZAP_DC_REPORT_DIR"
  echo "KVZAP_RD1_WCG1_SIDE_START side=$side"
  status=0
  (cd "$KVZAP_DC_REPORT_DIR" && nice -n 10 "$KVZAP_DC_SHELL" -f "$bundle/run_rd1_wcg1_full_paired.tcl") > "$KVZAP_DC_REPORT_DIR/native.log" 2>&1 || status=$?
  echo "$status" > "$KVZAP_DC_REPORT_DIR/exit_status"
  echo "KVZAP_RD1_WCG1_SIDE_EXIT side=$side exit=$status"
  [[ $status == 0 ]]
  python3 - "$KVZAP_DC_REPORT_DIR" "$side" "$bundle" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0,sys.argv[3])
from check_rd1_wcg1_full_paired import native_errors
d=Path(sys.argv[1]);native_errors((d/'native.log').read_text(errors='replace'),sys.argv[2])
for p in d.rglob('*.rpt'):
 import re
 assert not re.search(r'^\s*(?:Error:|Fatal:)',p.read_text(errors='replace'),re.M),str(p)
PY
done
python3 "$bundle/check_rd1_wcg1_full_paired.py" "$result"
sha256sum -c "$result/input_sha256.txt"
(cd "$KVZAP_DC_PROXY_ROOT" && sha256sum -c "$result/proxy_source_sha256.txt")
(cd "$bundle" && sha256sum -c SHA256SUMS)
echo KVZAP_RD1_WCG1_FULL_PAIRED_RUN_PASS_TOOL_ARTIFACT_ONLY
