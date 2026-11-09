#!/usr/bin/env bash
# Isolated current-RTL simulation probes. This script runs no synthesis or STA.
set -euo pipefail

if [[ ${1:-} == --help ]]; then
  echo 'Usage: bash run_stage_a_continuation_probes.sh NEW_ROOT SOURCE_TAR SOURCE_SHA256'
  exit 0
fi
[[ $# == 3 ]]
root=$1
archive=$2
expected=$3
runner=$0
[[ ! -e "$root" && -f "$archive" ]]
[[ $(sha256sum "$archive" | cut -d ' ' -f1) == "$expected" ]]
mkdir -p "$root/workspace"
exec > >(tee "$root/runner.log") 2>&1
trap 'status=$?; echo "$status" > "$root/exit_status"; echo "KVZAP_STAGE_A_PROBES_OUTER_EXIT=$status"' EXIT
tar -xf "$archive" -C "$root/workspace"

export CHISEL_PROJECT_ROOT="$root/workspace/hardware/route_a/chisel"
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export CHISEL_FIRTOOL_PATH=/home/yaz80/.cache/llvm-firtool/1.158.0/bin
export _JAVA_OPTIONS='-Xmx4g -XX:ActiveProcessorCount=2'
export MAKEFLAGS=-j1
export PYTHONDONTWRITEBYTECODE=1
ulimit -s unlimited

python3 - "$root" "$archive" "$expected" "$runner" <<'PY'
from pathlib import Path
import hashlib, json, sys
root=Path(sys.argv[1]); workspace=root/'workspace'
manifest_path=workspace/'source_manifest.json'
manifest=json.loads(manifest_path.read_text())
assert manifest['schema']=='stage-a-continuation-probe-source-1'
assert manifest['production_RTL_changed'] is False
for relative, entry in manifest['files'].items():
    data=(workspace/relative).read_bytes()
    assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'], relative
runner_name='hardware/route_a/dc/run_stage_a_continuation_probes.sh'
assert hashlib.sha256(Path(sys.argv[4]).read_bytes()).hexdigest()==manifest['files'][runner_name]['sha256']
memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
assert int(memory['MemAvailable'].split()[0]) >= 16*1024*1024, 'less than 16 GiB available'
record=dict(schema='stage-a-continuation-probe-input-1',archive=sys.argv[2],archive_sha256=sys.argv[3],source_commit=manifest['source_commit'],source_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),files=manifest['files'],scope='current functional RTL diagnostic probes; no new RTL, DC, STA or numeric datapath',gateCompactMembershipWords=False,fixture_r5StreamSlots=16,java_max_heap_gib=4,active_processors=2,make_jobs=1)
(root/'input_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print('KVZAP_STAGE_A_PROBES_INPUT_PASS files=%d' % len(manifest['files']),flush=True)
PY

launcher=/home/yaz80/wz_project/chisel_platform/bin/chisel-sbt
echo KVZAP_STAGE_A_PROBES_COMPILE_BEGIN
set +e
"$launcher" 'Test / compile' 2>&1 | tee "$root/compile.log"
compile_status=${PIPESTATUS[0]}
set -e
echo "$compile_status" > "$root/compile_exit_status"
[[ $compile_status == 0 ]] || exit "$compile_status"
echo KVZAP_STAGE_A_PROBES_COMPILE_PASS

echo KVZAP_STAGE_A_PROBES_SIMULATION_BEGIN
set +e
"$launcher" 'testOnly kvpress.routea.RouteAStageAContinuationProbeSpec' 2>&1 | tee "$root/test.log"
test_status=${PIPESTATUS[0]}
set -e
echo "$test_status" > "$root/test_exit_status"
[[ $test_status == 0 ]] || exit "$test_status"
python3 "$root/workspace/tools/check_stage_a_continuation_probes.py" "$root"
echo KVZAP_STAGE_A_PROBES_DIAGNOSTIC_RUN_PASS_NOT_CONTINUOUS_FUNCTIONAL_PASS
