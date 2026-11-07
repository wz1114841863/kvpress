#!/usr/bin/env python3
"""Freeze only a context-verified WCG1 wrapper and inline gate onto RD1."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile

from prepare_wcg1_wrapper_mapping import state, data_shape, bind_inline, GATE


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def normalized(text):
    return re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/|\s+',
                  lambda m: m.group(1) or '', text, flags=re.S)


def header(text):
    start = text.index('module ')
    return normalized(text[start:text.index(');', start) + 2])


def compact_shape(text, side):
    regs = state(text)
    selected = {}
    for kind in ('member', 'suffix'):
        if side == 'reference':
            prefix = 'membershipEntries_' if kind == 'member' else 'membershipPayloadBindings_'
            data = {n:w for n,w in regs.items() if n.startswith(prefix)}
        else:
            data = {n:w for n,w in regs.items() if re.match(kind + r'Word(?:_\d+)?_', n)}
        data_shape(data, side, kind)
        assert sum(data.values()) == (182016 if kind == 'member' else 184320)
        selected.update(data)
    return {n:w for n,w in regs.items() if n not in selected}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--context-root', type=Path, required=True)
    p.add_argument('--accepted-launch', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists()
    archive = Path(str(a.baseline) + '.tar.gz')
    assert sha(archive) == '9494f1dc4b47f1bfbcffe655b75e20a0d4c9cd75fb9802b5d454f870ae02dc5b'
    entries = (a.baseline/'route_a_control_projection_successor.f').read_text().splitlines()
    assert len(entries) == len(set(entries)) == 48
    required = set(entries) | {'full_kv_control_projection.sv', 'full_kv_control_projection.f', 'route_a_control_projection_successor.f'}
    seen = set()
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            if member.name not in required:
                continue
            h = hashlib.sha256()
            with tar.extractfile(member) as f:
                for b in iter(lambda:f.read(1048576), b''):
                    h.update(b)
            assert sha(a.baseline/member.name) == h.hexdigest(), member.name
            seen.add(member.name)
    assert seen == required
    assert (a.context_root/'exit_status').read_text().strip() == '0'
    workspace = a.context_root/'workspace'
    accepted = json.loads(a.accepted_launch.read_text())['freeze']
    exceptions = {
        'hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAMeasurementDut.scala',
        'hardware/route_a/chisel/src/main/scala/kvpress/routea/top/SynthesisControlProjectionGenerators.scala',
    }
    source_verified = 0
    for name,h in accepted['files_sha256'].items():
        if not name.startswith('hardware/route_a/chisel/') or name in exceptions:
            continue
        assert sha(workspace/name) == h, 'functional source drift: '+name
        source_verified += 1
    rel = 'route_a_control_projection_split/route_a_m2_p3_wrapper.sv'
    old = (a.baseline/rel).read_text()
    refpath = a.context_root/'split/reference/route_a_m2_p3_wrapper.sv'
    newpath = a.context_root/'split/gated/route_a_m2_p3_wrapper.sv'
    ref, new = refpath.read_text(), newpath.read_text()
    assert normalized(ref) == normalized(old), 'context reference differs from immutable RD1 wrapper'
    assert header(new) == header(old), 'contextual candidate port mismatch'
    assert compact_shape(new, 'gated') == compact_shape(old, 'reference'), 'non-table state changed'
    assert len(re.findall(r'\b'+GATE+r'\s+\w+\s*\(',new)) == 4608
    helper = workspace/'hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteACompactWordClocking.scala'
    emitted = a.context_root/'split/gated'/ (GATE+'.sv')
    modules = {GATE:(emitted,emitted.read_text())} if emitted.exists() else {}
    canonical,_ = bind_inline(modules, helper)
    gate_text = canonical+'\n'
    assert hashlib.sha256(gate_text.encode()).hexdigest() == 'aeb38a91977e96c1ea8a7b686d712c39bcd902a4489aedfcb0bb4810b2c1fc28'
    shutil.copytree(a.baseline,a.output)
    shutil.copyfile(newpath,a.output/rel)
    gate_rel = 'route_a_control_projection_split/'+GATE+'.sv'
    (a.output/gate_rel).write_text(gate_text)
    new_entries = entries + [gate_rel]
    (a.output/'route_a_control_projection_successor.f').write_text('\n'.join(new_entries)+'\n')
    changed = [n for n in entries if sha(a.output/n)!=sha(a.baseline/n)]
    assert changed == [rel]
    for n in ('full_kv_control_projection.sv','full_kv_control_projection.f'):
        assert sha(a.output/n)==sha(a.baseline/n)
    pm = a.output/'route_a_control_projection_split/route_a_page_manager.sv'
    assert sha(pm)=='f5e3299f9af08b05ac1de3c2a09967303fa2294f4c31dc2b81f7dccb3bde97b4'
    record = dict(schema='rd1-wcg1-composed-input-1',baseline=str(a.baseline),context_root=str(a.context_root),
        changed_compilation_units=changed,added_compilation_units=[gate_rel],unchanged_route_units=47,
        route_file_count=49,full_kv='byte_identical',PM1=False,RD2=False,data_bits=366336,native_gates=4608,
        functional_sources_verified=source_verified,reference_normalized_equal_RD1=True,typed_header_equal=True,
        non_table_state_equal=True,inline_sha256=sha(a.output/gate_rel),reference_sha256=sha(refpath),
        baseline_wrapper_sha256=sha(a.baseline/rel),candidate_sha256=sha(a.output/rel),
        route_files_sha256={n:sha(a.output/n) for n in new_entries})
    (a.output/'composition.json').write_text(json.dumps(record,indent=2)+'\n')
    print('KVZAP_RD1_WCG1_COMPOSITION_PASS unchanged=47 changed=1 added=1 files=49 bits=366336 gates=4608 PM1=false RD2=false')


if __name__ == '__main__':
    main()
