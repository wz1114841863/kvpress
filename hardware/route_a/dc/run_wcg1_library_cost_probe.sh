#!/usr/bin/env bash
# Library metadata only: no design inputs, mapping or clock changes.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "Usage: bash run_wcg1_library_cost_probe.sh NEW_RUN_ROOT PROBE_TCL ENV_SH"
  exit 0
fi
[[ $# == 3 ]]
run_root=$1
probe_tcl=$2
env_sh=$3
[[ ! -e "$run_root" && -f "$probe_tcl" && -f "$env_sh" ]]
source "$env_sh"
expected_db=5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d
actual_db=$(sha256sum "$KVZAP_DC_TARGET_LIBRARY" | cut -d ' ' -f 1)
[[ "$actual_db" == "$expected_db" ]]
mkdir -p "$run_root"
exec > >(tee "$run_root/launcher.log") 2>&1
export KVZAP_WCG1_LIBRARY_OUT="$run_root/metadata"
sha256sum "$KVZAP_DC_TARGET_LIBRARY" "$probe_tcl" "$env_sh" > "$run_root/input_sha256.txt"
ulimit -s unlimited
cd "$run_root"
set +e
"$KVZAP_DC_SHELL" -f "$probe_tcl" > native.log 2>&1
native_status=$?
set -e
echo "KVZAP_WCG1_LIBRARY_NATIVE_EXIT=$native_status"
status=$native_status
if [[ $status == 0 ]]; then
  if python3 - "$run_root" <<'PY'
import csv,re,sys
from pathlib import Path
r=Path(sys.argv[1]); log=(r/'native.log').read_text(errors='replace')
assert 'KVZAP_WCG1_LIBRARY_METADATA_PASS cells=16 gates=10' in log
assert not re.search(r'^\s*(?:Error:|Fatal:)',log,re.M)
rows=list(csv.DictReader((r/'metadata/cells.tsv').open(),delimiter='\t'))
assert len(rows)==16 and all(float(row['area'])>0 for row in rows)
for name in ['lib_cell_attributes.rpt','lib_pin_attributes.rpt','library_identity.tsv']:
    assert (r/'metadata'/name).stat().st_size>0,name
for report in (r/'metadata').iterdir():
    assert not re.search(r'^\s*(?:Error:|Fatal:)',report.read_text(errors='replace'),re.M),report
print('KVZAP_WCG1_LIBRARY_POSTCHECK_PASS')
PY
  then status=0; else status=1; fi
fi
echo "KVZAP_WCG1_LIBRARY_OUTER_EXIT=$status"
exit "$status"
