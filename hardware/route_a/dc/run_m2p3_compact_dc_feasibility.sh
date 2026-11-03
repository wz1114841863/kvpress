#!/usr/bin/env bash
# Run the compact-membership paired successor under the unchanged fair-v1 contract.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
artifact_root=${KVZAP_M2P3_COMPACT_ARTIFACT_ROOT:-/home/yaz80/wz_project/chisel_projects/kvpress/artifacts}
stem=$artifact_root/m2p3_compact_7bcd652_p9

export KVZAP_DC_HDL_ROOT="${stem}_paired_input"
export KVZAP_DC_HDL_ARCHIVE="${stem}_paired_input.tar.gz"
export KVZAP_DC_HDL_ARCHIVE_SHA256=61d4e51cafea3c96167f371c41b31af051ca5844fd93f58ccba127b681cf7008
export KVZAP_DC_PROXY_ROOT="${stem}_dc_array_proxy_r1"
export KVZAP_DC_ARRAY_PROXY_MANIFEST="${stem}_dc_array_proxy_manifest.json"
export KVZAP_DC_CONSTRAINT_MANIFEST="$script_dir/dc_feasibility_fair_m2p3_compact_v1.json"

exec "$script_dir/run_kvzap_control_projection_dc_feasibility.sh" "$@"
