#!/usr/bin/env python3
"""Accept tool/artifact closure separately from real-wrapper timing outcome."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from check_wcg1_bank_mapping import saved_constraints


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def precise(text):
    values = re.findall(r'slack \((?:MET|VIOLATED)\)\s+([-+0-9.eE]+)', text)
    assert values, 'missing precision slack'
    return min(float(x) for x in values)


def check(root):
    result = dict(scope='isolated_actual_wrapper_logic_mapping_not_full_top_or_physical_signoff', sides={})
    for side in ('reference', 'gated'):
        out = root / side
        assert (out / 'exit_status').read_text().strip() == '0'
        log = (out / 'native.log').read_text(errors='replace')
        assert 'KVZAP_WCG1_WRAPPER_SIDE_RUN_PASS side=' + side in log
        for p in [out / 'native.log'] + list(out.rglob('*.rpt')):
            assert not re.search(r'^\s*(?:Error:|Fatal:)', p.read_text(errors='replace'), re.M), str(p)
        result['sides'][side] = {}
        for stage in ('raw', 'repaired'):
            dest = out / stage
            names = ['area', 'references', 'qor', 'check_design', 'check_timing', 'constraints', 'clocks', 'gating', 'clock_net', 'setup', 'hold', 'entry_id']
            if side == 'gated':
                names += ['gate_setup', 'gate_hold', 'gated_data_hold']
            for n in [x + '.rpt' for x in names] + ['mapped.ddc', 'mapped.v', 'mapped.sdc', 'metrics.tsv']:
                assert (dest / n).stat().st_size > 0, str(dest / n)
            rows = list(csv.DictReader((dest / 'metrics.tsv').open(), delimiter='\t'))
            m = {r['metric']: r['value'] for r in rows}
            assert len(rows) == len(m)
            assert int(m['data_flops']) == 366336
            assert int(m['clock_gates']) == (4608 if side == 'gated' else 0)
            assert float(m['period_ns']) == 2 and m['propagated'] == 'true'
            area = (dest / 'area.rpt').read_text()
            for key, label in [('total_area', 'Total cell area'), ('combinational_area', 'Combinational area'), ('sequential_area', 'Noncombinational area')]:
                values = re.findall(r'^' + label + r':\s+(\S+)\s*$', area, re.M)
                assert len(values) == 1
                assert abs(float(m[key]) - float(values[0])) < 1e-5
                m[key] = float(values[0])
            assert m['total_area'] > 0 and abs(m['total_area'] - m['combinational_area'] - m['sequential_area']) < 1e-5
            assert 'checked_bits=48 undriven_bits=0' in (dest / 'entry_id.rpt').read_text()
            assert not re.search(r'^\s*Warning:', (dest / 'check_timing.rpt').read_text(), re.M), 'timing coverage warning'
            mapped = (dest / 'mapped.v').read_text()
            assert not re.search(r'\b(?:GTECH_\w+|SEQGEN)\b', mapped)
            sdc = (dest / 'mapped.sdc').read_text()
            saved_constraints(sdc)
            for key, report in [('max_slack_ns', 'setup'), ('min_slack_ns', 'hold')] + ([('gate_max_slack_ns', 'gate_setup'), ('gate_min_slack_ns', 'gate_hold')] if side == 'gated' else []):
                value = precise((dest / (report + '.rpt')).read_text())
                assert abs(float(m[key]) - value) <= 1e-5
                m[key] = value
            if side == 'gated':
                assert 'clock gating setup' in (dest / 'gate_setup.rpt').read_text().lower()
                assert 'clock gating hold' in (dest / 'gate_hold.rpt').read_text().lower()
                hold = (dest / 'gated_data_hold.rpt').read_text()
                arcs = re.findall(r'/Q\s+\(CKLNQ\w+\)\s+(\S+)\s+(\S+)\s+(\S+)', hold)
                assert arcs and all(float(incr) > 0 for _, incr, _ in arcs), 'missing positive capture gate arc'
            qor = (dest / 'qor.rpt').read_text()
            for kind, prefix in [('setup', r'Design\s+WNS'), ('hold', r'Design \(Hold\)\s+WNS')]:
                values = re.findall(prefix + r':\s*(\S+)\s+TNS:\s*(\S+)\s+Number of Violating Paths:\s*(\d+)', qor)
                assert len(values) == 1
                wns, tns, count = values[0]
                m[kind + '_qor'] = dict(wns=float(wns), tns=float(tns), paths=int(count))
            m['timing_closed'] = m['max_slack_ns'] >= 0 and m['min_slack_ns'] >= 0
            if side == 'gated':
                m['timing_closed'] = m['timing_closed'] and min(m['gate_max_slack_ns'], m['gate_min_slack_ns']) >= 0
            if m['timing_closed']:
                assert all(m[k + '_qor']['tns'] == 0 and m[k + '_qor']['paths'] == 0 for k in ('setup', 'hold'))
            lint = re.findall(r'\((LINT-\d+)\)', (dest / 'check_design.rpt').read_text())
            m['lint_counts'] = {x: lint.count(x) for x in set(lint)}
            assert 'LINT-3' not in lint and 'LINT-5' not in lint, 'undriven structure'
            result['sides'][side][stage] = m
    result['comparison'] = {}
    for stage in ('raw', 'repaired'):
        a, b = [result['sides'][s][stage] for s in ('reference', 'gated')]
        result['comparison'][stage] = dict(saved_area=a['total_area'] - b['total_area'], reduction_percent=100 * (1 - b['total_area'] / a['total_area']), both_timing_closed=a['timing_closed'] and b['timing_closed'])
    result['artifact_closure'] = 'PASS'
    result['artifact_sha256'] = {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file() and p.suffix in ('.ddc', '.v', '.sdc', '.rpt', '.tsv')}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    a = p.parse_args()
    result = check(a.root)
    (a.root / 'mapping_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('KVZAP_WCG1_WRAPPER_POSTCHECK_PASS_TOOL_INPUT_ARTIFACT_ONLY')


if __name__ == '__main__':
    main()
