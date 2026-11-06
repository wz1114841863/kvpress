#!/usr/bin/env python3
"""Close real-wrapper split HDL and proxy only P3 bytes; no EDA invocation."""
import argparse
import hashlib
import json
import re
from pathlib import Path

TOP = 'route_a_m2_p3_wrapper'
ARRAY = 'route_a_p3_stage_array_boundary'
GATE = 'route_a_compact_word_clock_gate'
NATIVE = 'CKLNQD1BWP12T30P140LVT'
REG = re.compile(r'^\s*reg\s+(?:\[(\d+):(\d+)\]\s*)?(\w+)\s*;', re.M)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def header(text):
    start = text.index('module ')
    return text[start:text.index(');', start) + 2]


def state(text):
    return {n: abs(int(a) - int(b)) + 1 if a else 1
            for a, b, n in REG.findall(text)}


def data_shape(data, side, kind):
    fields = {'logical_position': 15, 'payload_ref': 64} if kind == 'member' else {
        'transaction_identity_request_id': 3, 'transaction_identity_incarnation': 2,
        'payload_handle_or_address': 64, 'source_generation': 8, 'destination_endpoint': 3}
    actual = set()
    for name, width in data.items():
        if side == 'reference':
            prefix = 'membershipEntries' if kind == 'member' else 'membershipPayloadBindings'
            match = re.fullmatch(prefix + r'_(\d+)_(\d+)_(.+)', name)
            assert match, name
            bank, row, field = match.groups()
            ordinal = int(bank) * 64 + int(row)
            assert int(bank) < 36 and int(row) < 64
        else:
            match = re.fullmatch(kind + r'Word(?:_(\d+))?_(.+)', name)
            assert match, name
            ordinal, field = match.groups()
            ordinal = int(ordinal or 0)
        actual.add((ordinal, field, width))
    expected = {(row, field, width) for row in range(2304) for field, width in fields.items()}
    assert actual == expected and len(data) == len(expected), (side, kind, 'field/row shape mismatch')


def bind_inline(modules, helper):
    """CHIRRTL APIs may omit resource-file annotations; freeze explicit bytes."""
    canonical = helper.read_text().split('"""', 2)[1].strip()
    emitted = GATE in modules
    if emitted:
        actual = modules[GATE][1]
        actual = actual[actual.index('module '):].strip()
        if actual != canonical:
            # Only an empty matching external declaration can be completed.
            assert re.sub(r'\s+', '', header(actual)) == re.sub(r'\s+', '', header(canonical)), 'inline header mismatch'
            assert actual[actual.index(');') + 2:].strip() == 'endmodule', 'unexpected generated inline body'
    modules[GATE] = (helper, canonical + '\n')
    return canonical, emitted


def prepare(raw_root, dest, helper):
    assert not dest.exists(), 'new input root required'
    sides = {}
    texts = {}
    for side in ('reference', 'gated'):
        raw = raw_root / side
        modules = {}
        for p in raw.glob('*.sv'):
            text = p.read_text()
            names = re.findall(r'^module\s+(\w+)\b', text, re.M)
            assert len(names) == 1, str(p)
            assert names[0] not in modules
            modules[names[0]] = (p, text)
        assert TOP in modules and ARRAY in modules
        text = modules[TOP][1]
        texts[side] = text
        regs = state(text)
        if side == 'reference':
            data = {n: w for n, w in regs.items() if n.startswith(('membershipEntries_', 'membershipPayloadBindings_'))}
            member = {n: w for n, w in data.items() if n.startswith('membershipEntries_')}
            suffix = {n: w for n, w in data.items() if n.startswith('membershipPayloadBindings_')}
            assert GATE not in modules
        else:
            member = {n: w for n, w in regs.items() if re.match(r'memberWord(?:_\d+)?_', n)}
            suffix = {n: w for n, w in regs.items() if re.match(r'suffixWord(?:_\d+)?_', n)}
            data = dict(member, **suffix)
            expected_gate, emitted_inline = bind_inline(modules, helper)
            assert '`ifdef SYNTHESIS' in expected_gate and NATIVE in expected_gate
            assert '.TE(1\'b0)' in expected_gate and 'enable_low = enable' in expected_gate
            assert len(re.findall(r'\b' + GATE + r'\s+\w+\s*\(', text)) == 4608
        assert sum(member.values()) == 182016, (side, 'member', sum(member.values()))
        assert sum(suffix.values()) == 184320, (side, 'suffix', sum(suffix.values()))
        data_shape(member, side, 'member')
        data_shape(suffix, side, 'suffix')
        assert sum(data.values()) == 366336
        # P3 memory helpers must not enter the compilation closure after its
        # exact same-header child body is replaced. Every real parent remains.
        reachable = set()
        def visit(name):
            if name in reachable:
                return
            reachable.add(name)
            if name == ARRAY:
                return
            body = modules[name][1]
            for child in modules:
                if child != name and re.search(r'\b' + re.escape(child) + r'\s+\w+\s*\(', body):
                    visit(child)
        visit(TOP)
        assert ARRAY in reachable
        assert (GATE in reachable) == (side == 'gated')
        out = dest / side
        out.mkdir(parents=True)
        files = []
        for name in sorted(reachable - {TOP}) + [TOP]:
            body = modules[name][1]
            if name == ARRAY:
                body = '(* syn_black_box = 1 *)\n' + header(body) + '\nendmodule\n'
            path = out / (name + '.sv')
            path.write_text(body)
            files.append(path.name)
        (out / 'sources.f').write_text('\n'.join(files) + '\n')
        sides[side] = dict(files=files, file_sha256={n: sha(out / n) for n in files},
                           member_bits=sum(member.values()), suffix_bits=sum(suffix.values()),
                           parent_declared_reg_bits=sum(regs.values()),
                           other_state={n: w for n, w in regs.items() if n not in data},
                           header_sha256=hashlib.sha256(header(text).encode()).hexdigest())
        if side == 'gated':
            sides[side]['inline_source'] = 'exact_frozen_helper_string_materialized_explicitly'
            sides[side]['raw_inline_emitted'] = emitted_inline
    assert header(texts['reference']) == header(texts['gated']), 'typed top interfaces differ'
    assert sides['reference']['other_state'] == sides['gated']['other_state'], 'non-table state changed'
    common = set(sides['reference']['files']) & set(sides['gated']['files']) - {TOP + '.sv'}
    assert all((dest / 'reference' / n).read_bytes() == (dest / 'gated' / n).read_bytes() for n in common)
    report = dict(schema='wcg1-real-wrapper-input-1', status='STATIC_INPUT_CLOSURE_PASS',
                  top=TOP, data_bits=366336, expected_native_gates=4608,
                  proxy=ARRAY, proxy_cost='nonzero_unestimated', native_gate=NATIVE,
                  native_binding='SYNTHESIS branch TE tied zero; DC link gate still mandatory',
                  sides=sides, scope='real same-profile wrapper; no numeric datapath or full-top claim')
    (dest / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print('WCG1_WRAPPER_STATIC_INPUT_PASS bits=366336 gates=4608')
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-root', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--helper', type=Path, required=True)
    a = p.parse_args()
    prepare(a.raw_root, a.output_dir, a.helper)


if __name__ == '__main__':
    main()
