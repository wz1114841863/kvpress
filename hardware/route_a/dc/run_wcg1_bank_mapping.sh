#!/usr/bin/env bash
# One bank, both sides sequential; independent immutable inputs and tmux.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo 'Usage: bash run_wcg1_bank_mapping.sh NEW_RUN_ROOT FROZEN_INPUT_DIR'
  exit 0
fi
[[ $# == 2 ]]
run_root=$1
input_dir=$2
[[ ! -e "$run_root" && -d "$input_dir" ]]
mkdir -p "$run_root"
exec > >(tee "$run_root/launcher.log") 2>&1
trap 'status=$?; echo "KVZAP_WCG1_MAPPING_OUTER_EXIT=$status"; echo "$status" > "$run_root/exit_status"' EXIT
(cd "$input_dir" && sha256sum -c SHA256SUMS)
source "$input_dir/env_kvzap_control_projection_dc.sh"
[[ $(sha256sum "$KVZAP_DC_TARGET_LIBRARY" | cut -d ' ' -f 1) == 5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d ]]
python3 - <<'PY'
import os
for key, expected in {
    'CLOCK_PERIOD_NS':2., 'CLOCK_SETUP_UNCERTAINTY_NS':.1,
    'CLOCK_HOLD_UNCERTAINTY_NS':.02, 'INPUT_DELAY_NS':.2,
    'OUTPUT_DELAY_NS':.2, 'INPUT_TRANSITION_NS':.05, 'OUTPUT_LOAD_PF':.005,
}.items():
    assert float(os.environ['KVZAP_DC_'+key])==expected, key
PY
sha256sum "$KVZAP_DC_TARGET_LIBRARY" "$input_dir/SHA256SUMS" > "$run_root/input_sha256.txt"
cp "$input_dir/manifest.json" "$run_root/input_manifest.json"
export KVZAP_WCG1_INPUTS="$input_dir"
ulimit -s unlimited
cd "$run_root"
for side in reference gated; do
  export KVZAP_WCG1_SIDE="$side" KVZAP_WCG1_SIDE_OUT="$run_root/$side"
  mkdir "$KVZAP_WCG1_SIDE_OUT"
  status=0
  nice -n 10 "$KVZAP_DC_SHELL" -f "$input_dir/screen_wcg1_bank_sta.tcl" > "$KVZAP_WCG1_SIDE_OUT/native.log" 2>&1 || status=$?
  echo "$status" > "$KVZAP_WCG1_SIDE_OUT/exit_status"
  echo "KVZAP_WCG1_MAPPING_NATIVE_EXIT side=$side exit=$status"
  [[ $status == 0 ]]
done
python3 "$input_dir/check_wcg1_bank_mapping.py" "$run_root"
(cd "$input_dir" && sha256sum -c SHA256SUMS)
sha256sum -c "$run_root/input_sha256.txt"
echo KVZAP_WCG1_MAPPING_RUN_PASS_TOOL_INPUT_ARTIFACT_ONLY
