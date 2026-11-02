#!/usr/bin/env bash
# Build a versioned paired HDL archive and typed-array proxy tree.
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 ROUTE_SUCCESSOR_ROOT RAW_FULL_KV_ROOT OUTPUT_STEM BASE_MANIFEST" >&2
  exit 2
fi

ROUTE_ROOT=$1
FULL_KV_ROOT=$2
OUTPUT_STEM=$3
BASE_MANIFEST=$4
DC_SCRIPTS=${KVZAP_DC_SCRIPTS:-/home/yaz80/wz_project/chisel_projects/kvpress/dc_scripts}
PACKAGE_ROOT=${OUTPUT_STEM}_paired_input
ARCHIVE=${OUTPUT_STEM}_paired_input.tar.gz
MANIFEST=${OUTPUT_STEM}_dc_array_proxy_manifest.json
PROXY_ROOT=${OUTPUT_STEM}_dc_array_proxy_r1
PROXY_REPORT=$PROXY_ROOT/dc_array_proxy_check_report.json

for target in "$PACKAGE_ROOT" "$ARCHIVE" "$MANIFEST" "$PROXY_ROOT"; do
  if [[ -e $target ]]; then
    echo "refusing to overwrite existing output: $target" >&2
    exit 3
  fi
done
for source in \
  "$ROUTE_ROOT/route_a_control_projection_split" \
  "$ROUTE_ROOT/route_a_control_projection_successor.f" \
  "$FULL_KV_ROOT/full_kv_control_projection.sv" \
  "$FULL_KV_ROOT/full_kv_control_projection.f" \
  "$BASE_MANIFEST"; do
  if [[ ! -e $source ]]; then
    echo "missing required source: $source" >&2
    exit 4
  fi
done

mkdir -p "$PACKAGE_ROOT"
cp -a --reflink=auto "$FULL_KV_ROOT/full_kv_control_projection.sv" "$PACKAGE_ROOT/"
cp -a --reflink=auto "$FULL_KV_ROOT/full_kv_control_projection.f" "$PACKAGE_ROOT/"
cp -a --reflink=auto "$ROUTE_ROOT/route_a_control_projection_split" "$PACKAGE_ROOT/"
cp -a --reflink=auto "$ROUTE_ROOT/route_a_control_projection_successor.f" "$PACKAGE_ROOT/"

tar -C "$PACKAGE_ROOT" -czf "$ARCHIVE" \
  full_kv_control_projection.sv \
  full_kv_control_projection.f \
  route_a_control_projection_split \
  route_a_control_projection_successor.f

ARCHIVE_SHA=$(sha256sum "$ARCHIVE" | awk '{print $1}')
ROUTE_FILES=$(grep -cve '^[[:space:]]*$' "$PACKAGE_ROOT/route_a_control_projection_successor.f")
python3 - "$BASE_MANIFEST" "$MANIFEST" "$ARCHIVE_SHA" "$ROUTE_FILES" "$OUTPUT_STEM" <<'PY'
import json
import sys

base, output, archive_sha, route_files, output_stem = sys.argv[1:]
with open(base, "r") as handle:
    manifest = json.load(handle)
manifest["schema_version"] = "kvzap-dc-array-proxy-control-refinement-v1"
manifest["status"] = "control_refinement_successor_typed_array_proxy_materialization"
manifest["input_hdl_archive_sha256"] = archive_sha
manifest["source_freeze"] = "generated-artifact:" + output_stem
for item in manifest["filelists"]:
    if item["top"] == "route_a":
        item["expected_entries"] = int(route_files)
with open(output, "w") as handle:
    json.dump(manifest, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

python3 "$DC_SCRIPTS/materialize_dc_array_proxies.py" \
  --archive "$ARCHIVE" \
  --manifest "$MANIFEST" \
  --output "$PROXY_ROOT"
python3 "$DC_SCRIPTS/check_dc_array_proxy_materialization.py" \
  --manifest "$MANIFEST" \
  --proxy-root "$PROXY_ROOT" \
  --report "$PROXY_REPORT"

printf 'PAIRED_ARCHIVE_SHA256=%s\n' "$ARCHIVE_SHA"
printf 'ROUTE_A_FILELIST_ENTRIES=%s\n' "$ROUTE_FILES"
printf 'CONTROL_REFINEMENT_ARRAY_PROXY_PASS root=%s\n' "$PROXY_ROOT"
