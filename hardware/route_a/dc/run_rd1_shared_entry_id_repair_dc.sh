#!/usr/bin/env bash
# Run the frozen RD1 shared-read successor under the unchanged fair-v1
# contract and the accepted synthesis-only entry_id driver policy.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  echo "usage: $0 IMMUTABLE_RUN_ID"
  echo "Runs paired fair-v1 DC for rd1_shared_e5d3107_p15 with r3_entry_id_driver_v1."
  exit 0
fi

artifact_root=${KVZAP_RD1_ARTIFACT_ROOT:-/home/yaz80/wz_project/chisel_projects/kvpress/artifacts}
stem=$artifact_root/rd1_shared_e5d3107_p15

export KVZAP_DC_HDL_ROOT="${stem}_paired_input"
export KVZAP_DC_HDL_ARCHIVE="${stem}_paired_input.tar.gz"
export KVZAP_DC_HDL_ARCHIVE_SHA256=9494f1dc4b47f1bfbcffe655b75e20a0d4c9cd75fb9802b5d454f870ae02dc5b
export KVZAP_DC_PROXY_ROOT="${stem}_dc_array_proxy_r1"
export KVZAP_DC_ARRAY_PROXY_MANIFEST="${stem}_dc_array_proxy_manifest.json"
export KVZAP_DC_CONSTRAINT_MANIFEST="$script_dir/dc_feasibility_fair_rd1_shared_v1.json"
export KVZAP_DC_ENTRY_ID_DRIVER_POLICY=r3_entry_id_driver_v1

exec "$script_dir/run_kvzap_control_projection_dc_feasibility.sh" "$@"
