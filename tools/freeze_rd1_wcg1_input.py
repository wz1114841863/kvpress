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

# These are different, independently accepted representations. Never compare
# helper materialization with the raw firtool file's generated-comment hash.
BASELINE_ARCHIVE_SHA256 = '9494f1dc4b47f1bfbcffe655b75e20a0d4c9cd75fb9802b5d454f870ae02dc5b'
PAGE_MANAGER_SHA256 = 'f5e3299f9af08b05ac1de3c2a09967303fa2294f4c31dc2b81f7dccb3bde97b4'
HELPER_SOURCE_SHA256 = '4bea447a12560a2430b798267447ee3028293f3769b82aedfa191a10985cf394'
CANONICAL_INLINE_SHA256 = 'fbc839539af641e061f13ecb9311288b86bae53afa1639093b8e546040aa4556'
RAW_EMITTED_INLINE_SHA256 = 'aeb38a91977e96c1ea8a7b686d712c39bcd902a4489aedfcb0bb4810b2c1fc28'


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
    return text[start:text.index(');', start) + 2]


def verified_inline(modules, helper):
    """Check pinned source/body, recording raw-file and canonical hashes apart."""
    helper_hash = sha(helper)
    assert helper_hash == HELPER_SOURCE_SHA256, (
        'inline helper source drift: path={} expected={} actual={}'.format(
            helper, HELPER_SOURCE_SHA256, helper_hash))
    raw = {}
    if GATE in modules:
        path, actual = modules[GATE]
        starts = list(re.finditer(r'^\s*module\s+\w+\b', actual, re.M))
        assert len(starts) == 1, 'expected exactly one inline gate module: '+str(path)
        prefix = actual[:actual.index('module ')]
        assert re.fullmatch(r'(?:\s|//[^\n]*(?:\n|$)|/\*.*?\*/)*', prefix, re.S), (
            'unexpected logic/directive before inline gate: '+str(path))
        raw = dict(path=str(path), bytes=path.stat().st_size,
                   sha256=sha(path), accepted_raw_sha256=RAW_EMITTED_INLINE_SHA256)
        raw['matches_accepted_raw_representation'] = raw['sha256'] == RAW_EMITTED_INLINE_SHA256
    try:
        canonical, emitted = bind_inline(modules, helper)
    except AssertionError as error:
        raise AssertionError('inline body rejected: helper={} helper_sha256={} raw={} reason={}'.format(
            helper, helper_hash, raw, error)) from error
    gate_text = canonical+'\n'
    actual_hash = hashlib.sha256(gate_text.encode('utf-8')).hexdigest()
    assert actual_hash == CANONICAL_INLINE_SHA256, (
        'canonical inline mismatch: helper={} helper_sha256={} bytes={} expected={} actual={} raw={}'.format(
            helper, helper_hash, len(gate_text.encode('utf-8')),
            CANONICAL_INLINE_SHA256, actual_hash, raw))
    return gate_text, dict(helper_source_sha256=helper_hash,
        canonical_sha256=actual_hash, canonical_bytes=len(gate_text.encode('utf-8')),
        emitted=emitted, raw_emitted=raw,
        authority='accepted wrapper r2 prepared input, not raw emitted file')


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
    assert sha(archive) == BASELINE_ARCHIVE_SHA256
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
    new = newpath.read_text()
    assert refpath.read_bytes() == (a.baseline/rel).read_bytes(), 'context reference differs from immutable RD1 wrapper'
    assert header(new) == header(old), 'contextual candidate port mismatch'
    assert compact_shape(new, 'gated') == compact_shape(old, 'reference'), 'non-table state changed'
    assert len(re.findall(r'\b'+GATE+r'\s+\w+\s*\(',new)) == 4608
    helper = workspace/'hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteACompactWordClocking.scala'
    emitted = a.context_root/'split/gated'/ (GATE+'.sv')
    modules = {GATE:(emitted,emitted.read_text())} if emitted.exists() else {}
    gate_text, inline_evidence = verified_inline(modules, helper)
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
    assert sha(pm) == PAGE_MANAGER_SHA256
    record = dict(schema='rd1-wcg1-composed-input-1',baseline=str(a.baseline),context_root=str(a.context_root),
        changed_compilation_units=changed,added_compilation_units=[gate_rel],unchanged_route_units=47,
        route_file_count=49,full_kv='byte_identical',PM1=False,RD2=False,data_bits=366336,native_gates=4608,
        functional_sources_verified=source_verified,reference_normalized_equal_RD1=True,
        reference_byte_equal_RD1=True,typed_header_equal=True,inline_evidence=inline_evidence,
        non_table_state_equal=True,inline_sha256=sha(a.output/gate_rel),reference_sha256=sha(refpath),
        baseline_wrapper_sha256=sha(a.baseline/rel),candidate_sha256=sha(a.output/rel),
        route_files_sha256={n:sha(a.output/n) for n in new_entries})
    (a.output/'composition.json').write_text(json.dumps(record,indent=2)+'\n')
    print('KVZAP_RD1_WCG1_COMPOSITION_PASS unchanged=47 changed=1 added=1 files=49 bits=366336 gates=4608 PM1=false RD2=false')


if __name__ == '__main__':
    main()
