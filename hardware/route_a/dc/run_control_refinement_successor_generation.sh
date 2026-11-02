#!/usr/bin/env bash
# Generate and source-check a versioned Route-A split successor on the EDA host.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 OUTPUT_ROOT BASELINE_ROOT" >&2
  exit 2
fi

OUTPUT_ROOT=$1
BASELINE_ROOT=$2
PROJECT_ROOT=${KVZAP_CHISEL_PROJECT_ROOT:-/home/yaz80/wz_project/chisel_projects/kvpress}
WORKSPACE=${KVZAP_CHISEL_WORKSPACE:-$PROJECT_ROOT/workspace}
PLATFORM=${KVZAP_CHISEL_PLATFORM:-/home/yaz80/wz_project/chisel_platform}
FIRTOOL=${KVZAP_FIRTOOL:-/home/yaz80/.cache/llvm-firtool/1.158.0/bin/firtool}
DC_SCRIPTS=${KVZAP_DC_SCRIPTS:-$PROJECT_ROOT/dc_scripts}
SOURCE_COMMIT=${KVZAP_SOURCE_COMMIT:-unknown}
CHIRRTL_ROOT=$OUTPUT_ROOT/chirrtl
SPLIT_ROOT=$OUTPUT_ROOT/route_a_control_projection_split
SUCCESSOR_FILELIST=$OUTPUT_ROOT/route_a_control_projection_successor.f

if [[ -e $OUTPUT_ROOT ]]; then
  echo "refusing to overwrite existing output root: $OUTPUT_ROOT" >&2
  exit 3
fi
if [[ ! -d $BASELINE_ROOT/route_a_control_projection_split ]]; then
  echo "missing baseline split successor: $BASELINE_ROOT" >&2
  exit 4
fi
if [[ ! -x $FIRTOOL ]]; then
  echo "missing firtool: $FIRTOOL" >&2
  exit 5
fi

mkdir -p "$CHIRRTL_ROOT" "$SPLIT_ROOT"
printf 'source_commit=%s\nfirtool=%s\n' "$SOURCE_COMMIT" "$FIRTOOL" > "$OUTPUT_ROOT/generation_provenance.txt"

cd "$WORKSPACE"
ulimit -s unlimited
CHISEL_PROJECT_ROOT=$WORKSPACE "$PLATFORM/bin/chisel-sbt" \
  "runMain kvpress.routea.top.EmitControlProjectionChirrtl $CHIRRTL_ROOT route_a_control_projection"

FIR=$CHIRRTL_ROOT/route_a_control_projection.fir
test -s "$FIR"
"$FIRTOOL" "$FIR" \
  --format=fir \
  -O=debug \
  --mlir-disable-threading \
  --strip-debug-info \
  --lowering-options=locationInfoStyle=none,emittedLineLength=160 \
  --split-verilog \
  -o "$SPLIT_ROOT"

find "$SPLIT_ROOT" -maxdepth 1 -type f -name '*.sv' -printf '%f\n' \
  | LC_ALL=C sort \
  | sed 's#^#route_a_control_projection_split/#' \
  > "$SUCCESSOR_FILELIST"
test -s "$SUCCESSOR_FILELIST"

python3 "$DC_SCRIPTS/check_r5_descriptor_externalization_successor.py" \
  --root "$OUTPUT_ROOT" \
  --report "$OUTPUT_ROOT/r5_descriptor_successor_check.json"
python3 "$DC_SCRIPTS/check_control_refinement_successor.py" \
  --root "$OUTPUT_ROOT" \
  --baseline-root "$BASELINE_ROOT" \
  --report "$OUTPUT_ROOT/control_refinement_successor_check.json"

sha256sum "$FIR" "$SUCCESSOR_FILELIST" > "$OUTPUT_ROOT/generation_sha256.txt"
printf 'SV_FILES=%s\n' "$(wc -l < "$SUCCESSOR_FILELIST")"
printf 'SV_BYTES=%s\n' "$(find "$SPLIT_ROOT" -maxdepth 1 -type f -name '*.sv' -printf '%s\n' | awk '{sum += $1} END {print sum + 0}')"
printf 'CONTROL_REFINEMENT_SUCCESSOR_GENERATION_PASS output=%s\n' "$OUTPUT_ROOT"
