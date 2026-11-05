#!/usr/bin/env bash
# Validate an immutable RD2 source archive in an isolated EDA-server workspace.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "usage: $0 NEW_OUTPUT_ROOT SOURCE_TAR EXPECTED_SOURCE_SHA256"
  exit 0
fi
[[ $# == 3 ]] || { echo "expected output root, source tar and hash" >&2; exit 2; }
root=$1
archive=$2
expected_sha=$3
platform=${KVZAP_CHISEL_PLATFORM:-/home/yaz80/wz_project/chisel_platform}
[[ ! -e $root ]] || { echo "refusing to overwrite $root" >&2; exit 3; }
[[ -f $archive && -x $platform/bin/chisel-sbt ]]
export JAVA_HOME="${KVZAP_RD2_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}"
export CHISEL_FIRTOOL_PATH=/home/yaz80/.cache/llvm-firtool/1.158.0/bin
export _JAVA_OPTIONS="-Xmx4g -XX:ActiveProcessorCount=2"
[[ -x $JAVA_HOME/bin/java && -x $CHISEL_FIRTOOL_PATH/firtool ]]
"$JAVA_HOME/bin/java" -version
python3 - "$archive" "$expected_sha" <<'PY'
import hashlib
from pathlib import Path
import sys
archive = Path(sys.argv[1])
assert hashlib.sha256(archive.read_bytes()).hexdigest() == sys.argv[2], 'source archive hash mismatch'
mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
available_kib = int(mem['MemAvailable'].split()[0])
assert available_kib >= 30 * 1024 * 1024, f'less than 30 GiB available: {available_kib} KiB'
print(f'KVZAP_RD2_REMOTE_PREFLIGHT_PASS available_kib={available_kib}', flush=True)
PY
mkdir -p "$root/workspace"
tar -xf "$archive" -C "$root/workspace"
export CHISEL_PROJECT_ROOT="$root/workspace/hardware/route_a/chisel"
[[ -s $CHISEL_PROJECT_ROOT/build.sbt ]]
python3 - "$root" "$archive" "$expected_sha" "$platform" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sys
root, archive, expected, platform = sys.argv[1:]
project = Path(os.environ['CHISEL_PROJECT_ROOT'])
files = sorted(path for path in project.rglob('*') if path.is_file())
manifest = {
    'schema': 'kvzap-rd2-remote-validation-v1',
    'source_archive': archive, 'source_archive_sha256': expected,
    'workspace': str(project), 'platform': platform,
    'java_home': os.environ['JAVA_HOME'],
    'firtool_path': os.environ['CHISEL_FIRTOOL_PATH'],
    'geometry': [[4, 8], [36, 64]],
    'build_jobs': 1, 'verilate_jobs': 2,
    'source_hashes': {str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
    'scope': 'differential tests and paired RTL emission only; no DC',
}
with (Path(root) / 'input_manifest.json').open('x') as handle:
    json.dump(manifest, handle, indent=2)
print('KVZAP_RD2_REMOTE_INPUT_PASS', flush=True)
PY
ulimit -s unlimited
echo "KVZAP_RD2_REMOTE_STACK_PASS stack_kb=$(ulimit -s)"
set +e
"$platform/bin/chisel-sbt" \
  'testOnly kvpress.routea.rtl3.RouteARD2ReadDecodeSpec' \
  "Test / runMain kvpress.routea.rtl3.RouteARD2ReadNetworkEmitter $root/inputs" \
  2>&1 | tee "$root/test_emit.log"
statuses=("${PIPESTATUS[@]}")
set -e
code=${statuses[0]}
if (( statuses[1] != 0 )); then code=9; fi
if (( code == 0 )); then
  set +e
  python3 - "$root" <<'PY' 2>&1 | tee -a "$root/test_emit.log"
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
root = Path(sys.argv[1])
manifest = json.loads((root / 'input_manifest.json').read_text())
project = Path(manifest['workspace'])
for relative, expected in manifest['source_hashes'].items():
    assert hashlib.sha256((project / relative).read_bytes()).hexdigest() == expected, relative
report = ET.parse(project / 'target/test-reports/TEST-kvpress.routea.rtl3.RouteARD2ReadDecodeSpec.xml').getroot()
assert int(report.attrib['tests']) == 2
assert int(report.attrib.get('failures', 0)) == 0 and int(report.attrib.get('errors', 0)) == 0
assert int(report.attrib.get('skipped', 0)) == 0
headers = []
hashes = {}
for side in ('rd1', 'decoded'):
    path = root / f'inputs/rd2_{side}_read_network.sv'
    sv = path.read_text()
    match = re.search(rf'module\s+rd2_{side}_read_network\s*\((.*?)\n\);', sv, re.S)
    assert match, f'missing module header: {side}'
    headers.append(re.sub(r'\s+', ' ', match.group(1)).strip())
    hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
assert headers[0] == headers[1], 'paired port headers differ'
log = (root / 'test_emit.log').read_text()
assert 'RD2_SCREEN_INPUT_EMIT_PASS' in log and 'All tests passed.' in log
with (root / 'output_manifest.json').open('x') as handle:
    json.dump({'tests': 2, 'failures': 0, 'paired_ports_identical': True, 'sv_sha256': hashes}, handle, indent=2)
print('KVZAP_RD2_REMOTE_POSTCHECK_PASS tests=2 paired_ports_identical=true')
PY
  post_statuses=("${PIPESTATUS[@]}")
  set -e
  if (( post_statuses[0] != 0 || post_statuses[1] != 0 )); then code=8; fi
fi
echo "KVZAP_RD2_REMOTE_VALIDATION_EXIT=$code" | tee -a "$root/test_emit.log"
exit "$code"
