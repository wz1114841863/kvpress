#!/usr/bin/env bash
# New isolated workspace only. Long generation/native work stays in own tmux.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo 'Usage: bash run_wcg1_wrapper_mapping.sh NEW_ROOT FROZEN_ARCHIVE SHA256'
  exit 0
fi
[[ $# == 3 ]]
root=$1
archive=$2
expected=$3
[[ ! -e "$root" && -f "$archive" ]]
[[ $(sha256sum "$archive" | cut -d ' ' -f1) == "$expected" ]]
mkdir -p "$root/workspace"
exec > >(tee "$root/launcher.log") 2>&1
trap 'status=$?; echo "KVZAP_WCG1_WRAPPER_MAPPING_OUTER_EXIT=$status"; echo "$status" > "$root/exit_status"' EXIT
tar -xf "$archive" -C "$root/workspace"
cd "$root/workspace"
sha256sum -c SHA256SUMS
scripts=$root/workspace/hardware/route_a/dc
source "$scripts/env_kvzap_control_projection_dc.sh"
export KVZAP_WCG1_SCRIPTS=$scripts
[[ $(sha256sum "$KVZAP_DC_TARGET_LIBRARY" | cut -d ' ' -f1) == 5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d ]]
python3 - <<'PY'
import os
from pathlib import Path
assert int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))) >= 16*1024*1024
for k,v in {'CLOCK_PERIOD_NS':2.,'CLOCK_SETUP_UNCERTAINTY_NS':.1,'CLOCK_HOLD_UNCERTAINTY_NS':.02,'INPUT_DELAY_NS':.2,'OUTPUT_DELAY_NS':.2,'INPUT_TRANSITION_NS':.05,'OUTPUT_LOAD_PF':.005}.items():
 assert float(os.environ['KVZAP_DC_'+k])==v,k
PY
sha256sum "$archive" "$KVZAP_DC_TARGET_LIBRARY" > "$root/input_sha256.txt"
export CHISEL_PROJECT_ROOT=$root/workspace/hardware/route_a/chisel
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export CHISEL_FIRTOOL_PATH=/home/yaz80/.cache/llvm-firtool/1.158.0/bin
export _JAVA_OPTIONS='-Xmx3g -XX:ActiveProcessorCount=2'
ulimit -s unlimited
"$CHISEL_FIRTOOL_PATH/firtool" --version > "$root/generation_toolchain.txt"
sha256sum "$CHISEL_FIRTOOL_PATH/firtool" >> "$root/generation_toolchain.txt"
echo KVZAP_WCG1_WRAPPER_GENERATION_START
nice -n 10 /home/yaz80/wz_project/chisel_platform/bin/chisel-sbt \
  "runMain kvpress.routea.top.EmitWCG1WrapperChirrtl $root/chirrtl"
mkdir "$root/raw"
for side in reference gated; do
  mkdir "$root/raw/$side"
  nice -n 10 "$CHISEL_FIRTOOL_PATH/firtool" "$root/chirrtl/$side/wrapper.fir" \
    --format=fir -O=debug --mlir-disable-threading --strip-debug-info \
    --lowering-options=locationInfoStyle=none,emittedLineLength=160 \
    --split-verilog -o "$root/raw/$side"
done
python3 tools/prepare_wcg1_wrapper_mapping.py --raw-root "$root/raw" --output-dir "$root/inputs" \
  --helper "$CHISEL_PROJECT_ROOT/src/main/scala/kvpress/routea/incremental/RouteACompactWordClocking.scala"
export KVZAP_WCG1_INPUTS=$root/inputs
(cd "$root/inputs" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
export KVZAP_WCG1_SIDE=gated KVZAP_WCG1_SIDE_OUT=$root/native_binding
mkdir "$KVZAP_WCG1_SIDE_OUT"
echo KVZAP_WCG1_WRAPPER_NATIVE_BINDING_START
KVZAP_WCG1_PREFLIGHT_ONLY=1 nice -n 10 "$KVZAP_DC_SHELL" -f "$scripts/screen_wcg1_wrapper_sta.tcl" > "$root/native_binding/native.log" 2>&1
grep -q 'KVZAP_WCG1_WRAPPER_NATIVE_BINDING_PASS side=gated gates=4608 P3_proxies=1' "$root/native_binding/native.log"
if grep -Eq '^[[:space:]]*(Error:|Fatal:)' "$root/native_binding/native.log"; then exit 7; fi
if grep -ERq '^[[:space:]]*(Error:|Fatal:)' "$root/native_binding"/*.rpt; then exit 7; fi
echo KVZAP_WCG1_WRAPPER_BINDING_CLOSED_STARTING_MATCHED_MAPPING
unset KVZAP_WCG1_PREFLIGHT_ONLY
for side in reference gated; do
  export KVZAP_WCG1_SIDE=$side KVZAP_WCG1_SIDE_OUT=$root/$side
  mkdir "$KVZAP_WCG1_SIDE_OUT"
  status=0
  nice -n 10 "$KVZAP_DC_SHELL" -f "$scripts/screen_wcg1_wrapper_sta.tcl" > "$KVZAP_WCG1_SIDE_OUT/native.log" 2>&1 || status=$?
  echo "$status" > "$KVZAP_WCG1_SIDE_OUT/exit_status"
  echo "KVZAP_WCG1_WRAPPER_MAPPING_NATIVE_EXIT side=$side exit=$status"
  [[ $status == 0 ]]
done
python3 tools/check_wcg1_wrapper_mapping.py "$root"
sha256sum -c SHA256SUMS
(cd "$root/inputs" && sha256sum -c SHA256SUMS)
sha256sum -c "$root/input_sha256.txt"
echo KVZAP_WCG1_WRAPPER_MAPPING_RUN_PASS_TOOL_INPUT_ARTIFACT_ONLY
