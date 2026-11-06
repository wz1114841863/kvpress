#!/usr/bin/env bash
# Independent, immutable functional validation. No native EDA or full top DC.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo 'Usage: bash run_wcg1_wrapper_validation.sh NEW_ROOT SOURCE_TAR SOURCE_SHA256'
  exit 0
fi
[[ $# == 3 ]]
root=$1
archive=$2
expected=$3
[[ ! -e "$root" && -f "$archive" ]]
[[ $(sha256sum "$archive" | cut -d ' ' -f1) == "$expected" ]]
mkdir -p "$root/workspace"
trap 'status=$?; echo "KVZAP_WCG1_WRAPPER_VALIDATION_OUTER_EXIT=$status"; echo "$status" > "$root/exit_status"' EXIT
tar -xf "$archive" -C "$root/workspace"
export CHISEL_PROJECT_ROOT="$root/workspace/hardware/route_a/chisel"
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export CHISEL_FIRTOOL_PATH=/home/yaz80/.cache/llvm-firtool/1.158.0/bin
export _JAVA_OPTIONS='-Xmx3g -XX:ActiveProcessorCount=2'
python3 - "$root" "$archive" "$expected" <<'PY'
from pathlib import Path
import hashlib,json,os,sys
root=Path(sys.argv[1]);project=Path(os.environ['CHISEL_PROJECT_ROOT'])
memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
assert int(memory['MemAvailable'].split()[0]) >= 16*1024*1024, 'less than 16 GiB available for serial validation'
files={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(project.rglob('*')) if p.is_file()}
assert not any('RD2' in p or 'RecordReadDecode' in p for p in files), 'RD2 must be excluded'
(root/'input_manifest.json').write_text(json.dumps(dict(schema='wcg1-wrapper-functional-input-1',archive=sys.argv[2],archive_sha256=sys.argv[3],workspace=str(project),source_sha256=files,scope='baseline regression plus candidate actual-wrapper differential assertions; no DC or STA',candidate_geometry=[36,64,79,80],build_jobs=1),indent=2)+'\n')
print('KVZAP_WCG1_WRAPPER_INPUT_PASS',flush=True)
PY
ulimit -s unlimited
/home/yaz80/wz_project/chisel_platform/bin/chisel-sbt \
  'Test / compile' \
  'testOnly kvpress.routea.rtl3.RouteARTL39AMaterializationSpec kvpress.routea.rtl3.RouteAWCG1WrapperSpec' \
  2>&1 | tee "$root/test.log"
python3 - "$root" <<'PY'
from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path(sys.argv[1]);manifest=json.loads((root/'input_manifest.json').read_text());project=Path(manifest['workspace'])
for name,expected in manifest['source_sha256'].items():assert hashlib.sha256((project/name).read_bytes()).hexdigest()==expected,name
assert hashlib.sha256(Path(manifest['archive']).read_bytes()).hexdigest()==manifest['archive_sha256']
results={}
for suite in ('RouteARTL39AMaterializationSpec','RouteAWCG1WrapperSpec'):
 p=project/f'target/test-reports/TEST-kvpress.routea.rtl3.{suite}.xml'
 report=ET.parse(p).getroot()
 assert int(report.attrib['tests'])==4 and all(int(report.attrib.get(k,'0'))==0 for k in ('failures','errors','skipped')),suite
 results[suite]=dict(tests=4,xml_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
assert 'All tests passed.' in (root/'test.log').read_text()
(root/'result.json').write_text(json.dumps(dict(schema='wcg1-wrapper-functional-result-1',suites=results,scope='eight directed tests, candidate reference miter, not formal universal equivalence or STA',source_sha256=manifest['source_sha256']),indent=2)+'\n')
print('KVZAP_WCG1_WRAPPER_POSTCHECK_PASS tests=8')
PY
echo KVZAP_WCG1_WRAPPER_FUNCTIONAL_RUN_PASS
