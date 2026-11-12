#!/usr/bin/env bash
# Compose accepted immutable components, fail-closed preflight, then full paired DC.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo 'Usage: bash run_rd1_pm1_freeze_and_dc.sh NEW_STEM NEW_RUN_ID SCRIPT_BUNDLE'
  exit 0
fi
[[ $# == 3 ]]
stem=$1
run_id=$2
bundle=$3
source_root=/home/yaz80/wz_project/chisel_projects/kvpress/artifacts
baseline=$source_root/rd1_shared_e5d3107_p15_paired_input
pm1=$source_root/pm1_contextual_6dc1671_p19/split/route_a_page_manager_pm1.sv
[[ ! -e "$stem" ]]
(cd "$bundle" && sha256sum -c SHA256SUMS)
trap 'status=$?; echo "KVZAP_RD1_PM1_FREEZE_DC_OUTER_EXIT=$status"' EXIT
[[ $(sha256sum "${baseline}.tar.gz" | cut -d ' ' -f1) == 9494f1dc4b47f1bfbcffe655b75e20a0d4c9cd75fb9802b5d454f870ae02dc5b ]]
python3 "$bundle/freeze_rd1_pm1_input.py" "$baseline" "$pm1" "$stem"
python3 "$bundle/check_r5_descriptor_externalization_successor.py" --root "$stem" --report "$stem/r5_check.json"
python3 "$bundle/check_control_refinement_successor.py" --root "$stem" --baseline-root "$baseline" --report "$stem/state_check.json"
python3 - "$stem/state_check.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
def state_shape(s):
 return {name:(v['state_bits'],v['state_objects']) for name,v in s['per_module'].items()}
assert r['pass'] and state_shape(r['current']['state'])==state_shape(r['baseline']['state']), 'state capacity changed'
print('KVZAP_RD1_PM1_STATE_IDENTITY_PASS')
PY
export KVZAP_DC_SCRIPTS="$bundle"
bash "$bundle/materialize_control_refinement_proxy.sh" "$stem" "$baseline" "$stem" "$source_root/rd1_shared_e5d3107_p15_dc_array_proxy_manifest.json"
python3 - "$bundle/dc_feasibility_fair_rd1_shared_v1.json" "$stem" <<'PY'
import hashlib,json,sys
from pathlib import Path
profile=json.load(open(sys.argv[1]));stem=Path(sys.argv[2])
profile['source_successor']=stem.name
profile['source_freeze']='analysis/hardware_reports/04_area_timing_optimization_and_design_review.md'
profile['status']='approved_rd1_pm1_same_fair_v1_pending_native_result'
profile['integrity']['hdl_archive_sha256']=hashlib.sha256(Path(str(stem)+'_paired_input.tar.gz').read_bytes()).hexdigest()
(stem/'dc_profile.json').write_text(json.dumps(profile,indent=2)+'\n')
PY
export KVZAP_DC_SCRIPT_DIR="$bundle"
export KVZAP_DC_HDL_ROOT="${stem}_paired_input"
export KVZAP_DC_HDL_ARCHIVE="${stem}_paired_input.tar.gz"
export KVZAP_DC_HDL_ARCHIVE_SHA256
KVZAP_DC_HDL_ARCHIVE_SHA256=$(sha256sum "$KVZAP_DC_HDL_ARCHIVE" | cut -d ' ' -f1)
export KVZAP_DC_PROXY_ROOT="${stem}_dc_array_proxy_r1"
export KVZAP_DC_ARRAY_PROXY_MANIFEST="${stem}_dc_array_proxy_manifest.json"
export KVZAP_DC_CONSTRAINT_MANIFEST="$stem/dc_profile.json"
export KVZAP_DC_ENTRY_ID_DRIVER_POLICY=r3_entry_id_driver_v1
echo KVZAP_RD1_PM1_FREEZE_PASS_STARTING_FULL_PAIRED_DC
ulimit -s unlimited
bash "$bundle/run_kvzap_control_projection_dc_feasibility.sh" "$run_id"
(cd "$bundle" && sha256sum -c SHA256SUMS)
