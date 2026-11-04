#!/usr/bin/env bash
# Same HDL, library and numerical fair-v1 constraints; explicit result-net
# preservation repairs the unused internal entry_id interface driver.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  echo "usage: $0 IMMUTABLE_RUN_ID"
  echo "Runs paired fair-v1 DC with r3_entry_id_driver_v1 result-net preservation."
  exit 0
fi
export KVZAP_DC_ENTRY_ID_DRIVER_POLICY=r3_entry_id_driver_v1
exec "$script_dir/run_m2p3_compact_dc_feasibility.sh" "$@"
