#!/usr/bin/env bash
# Generate a versioned full-profile PM1 Page Manager child for a controlled
# saved-DDC replacement screen. This script performs no DC invocation.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 OUTPUT_ROOT BASELINE_SUCCESSOR_ROOT" >&2
  exit 2
fi

output_root=$1
baseline_root=$2
project_root=${KVZAP_CHISEL_PROJECT_ROOT:-/home/yaz80/wz_project/chisel_projects/kvpress}
workspace=${KVZAP_CHISEL_WORKSPACE:-$project_root/workspace}
platform=${KVZAP_CHISEL_PLATFORM:-/home/yaz80/wz_project/chisel_platform}
firtool=${KVZAP_FIRTOOL:-/home/yaz80/.cache/llvm-firtool/1.158.0/bin/firtool}
source_commit=${KVZAP_SOURCE_COMMIT:-unknown}
chirrtl_root=$output_root/chirrtl
split_root=$output_root/split
baseline_sv=$baseline_root/route_a_control_projection_split/route_a_page_manager.sv
candidate_sv=$split_root/route_a_page_manager_pm1.sv

[[ ! -e $output_root ]] || { echo "refusing to overwrite $output_root" >&2; exit 3; }
[[ -f $baseline_sv ]] || { echo "missing baseline Page Manager SV: $baseline_sv" >&2; exit 4; }
[[ -x $firtool ]] || { echo "missing firtool: $firtool" >&2; exit 5; }
mkdir -p "$chirrtl_root" "$split_root"
printf 'source_commit=%s\nfirtool=%s\nbaseline_sv=%s\n' \
  "$source_commit" "$firtool" "$baseline_sv" > "$output_root/generation_provenance.txt"

cd "$workspace"
ulimit -s unlimited
CHISEL_PROJECT_ROOT=$workspace "$platform/bin/chisel-sbt" \
  "runMain kvpress.routea.top.EmitPM1PageManagerChirrtl $chirrtl_root"

fir=$chirrtl_root/route_a_page_manager_pm1.fir
[[ -s $fir ]] || { echo "missing PM1 Page Manager CHIRRTL" >&2; exit 6; }
"$firtool" "$fir" \
  --format=fir \
  -O=debug \
  --mlir-disable-threading \
  --strip-debug-info \
  --lowering-options=locationInfoStyle=none,emittedLineLength=160 \
  --split-verilog \
  -o "$split_root"
[[ -s $candidate_sv ]] || { echo "missing PM1 Page Manager SV" >&2; exit 7; }

python3 - "$baseline_sv" "$candidate_sv" <<'PY'
import re
import sys
from pathlib import Path

baseline, candidate = map(Path, sys.argv[1:])

def header(path: Path, module: str) -> str:
    text = path.read_text()
    match = re.search(rf"module\s+{re.escape(module)}\s*\((.*?)\n\);", text, re.S)
    if not match:
        raise SystemExit(f"cannot locate module header in {path}")
    return re.sub(r"\s+", " ", match.group(1)).strip()

old = header(baseline, "route_a_page_manager")
new = header(candidate, "route_a_page_manager_pm1")
if old != new:
    raise SystemExit("PM1 Page Manager port header differs from frozen baseline")
print("KVZAP_PM1_PAGE_MANAGER_PORT_IDENTITY_PASS")
PY

find "$split_root" -maxdepth 1 -type f -name '*.sv' -printf '%f\n' | LC_ALL=C sort \
  > "$output_root/split_files.txt"
sha256sum "$fir" "$candidate_sv" "$baseline_sv" "$output_root/split_files.txt" \
  > "$output_root/input_sha256.txt"
printf 'PM1_PAGE_MANAGER_SV_FILES=%s\n' "$(wc -l < "$output_root/split_files.txt")"
printf 'KVZAP_PM1_PAGE_MANAGER_SUCCESSOR_PASS output=%s\n' "$output_root"
