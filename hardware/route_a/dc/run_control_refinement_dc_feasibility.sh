#!/usr/bin/env bash
# Run the refined paired successor under the unchanged fair-v1 contract.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
artifact_root=${KVZAP_CONTROL_REFINEMENT_ARTIFACT_ROOT:-/home/yaz80/wz_project/chisel_projects/kvpress/artifacts}
stem=$artifact_root/control_refine_a6acd4a_p6

export KVZAP_DC_HDL_ROOT="${stem}_paired_input"
export KVZAP_DC_HDL_ARCHIVE="${stem}_paired_input.tar.gz"
export KVZAP_DC_HDL_ARCHIVE_SHA256=1b5ac01cd35c77c37c6d7a08843c8554ec2458eb25cc9d7d6cafbefc873ec33d
export KVZAP_DC_PROXY_ROOT="${stem}_dc_array_proxy_r2"
export KVZAP_DC_ARRAY_PROXY_MANIFEST="${stem}_dc_array_proxy_manifest.json"
export KVZAP_DC_CONSTRAINT_MANIFEST="$script_dir/dc_feasibility_fair_control_refinement_v1.json"

exec "$script_dir/run_kvzap_control_projection_dc_feasibility.sh" "$@"
