#!/usr/bin/env python3
"""Validate full-top WCG1 artifacts while keeping timing/area verdicts separate."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from check_wcg1_bank_mapping import native_area, precision_slack, saved_constraints


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def native_errors(text, side):
    errors = re.findall(r'^\s*(?:Error:|Fatal:).*$', text, re.M)
    allowed = [v for v in errors if side == 'full_kv' and re.search(
        r"full_kv_control_projection\.sv:\d+: Unable to open file `layers-route_a_core_side_arbiter-Verification\.sv'.*\(VER-41\)", v)]
    assert len(allowed) <= 1 and len(allowed) == len(errors), errors
    return allowed


def check(root):
    out = dict(schema='rd1-wcg1-full-paired-result-1',sides={},scope='logic_only_control_mapping_not_PPA')
    for side in ('full_kv','route_a'):
        d = root/side
        assert (d/'exit_status').read_text().strip() == '0'
        log = (d/'native.log').read_text(errors='replace')
        top = side+'_control_projection'
        assert 'KVZAP_RD1_WCG1_SIDE_PASS top='+top in log
        allowed = native_errors(log,side)
        for p in d.rglob('*.rpt'):
            assert not re.search(r'^\s*(?:Error:|Fatal:)',p.read_text(errors='replace'),re.M),str(p)
        out['sides'][side] = dict(retained_baseline_diagnostics=allowed,stages={})
        for stage in ('primary_raw','propagated_raw','propagated_hold_repaired'):
            p = d/stage
            names = ['area','qor','references','check_design','check_timing','constraints','clocks','clock_net','gating','setup','hold']
            if side == 'route_a':
                names += ['gate_setup','gate_hold','entry_id_driver_check']
                if stage != 'primary_raw':names += ['gated_data_hold']
            for name in [n+'.rpt' for n in names]+['mapped.ddc','mapped.v','mapped.sdc','metrics.tsv']:
                assert (p/name).stat().st_size > 0,str(p/name)
            m = {r['metric']:r['value'] for r in csv.DictReader((p/'metrics.tsv').open(),delimiter='\t')}
            assert float(m['period_ns']) == 2 and int(m['clock_gates']) == (4608 if side=='route_a' else 0)
            assert int(m['propagated']) == int(stage!='primary_raw')
            sdc = (p/'mapped.sdc').read_text()
            if stage == 'primary_raw':
                assert 'set_propagated_clock' not in sdc
                # Validate all other saved boundaries with the same parser.
                saved_constraints(sdc+'\nset_propagated_clock [get_clocks kvzap_control_clk]\n')
            else:
                saved_constraints(sdc)
            area = native_area((p/'area.rpt').read_text())
            timing = {kind:precision_slack((p/(kind+'.rpt')).read_text()) for kind in ('setup','hold')}
            for key,kind in [('max_slack_ns','setup'),('min_slack_ns','hold')]:
                assert abs(float(m[key])-timing[kind])<=1e-5
            qor = (p/'qor.rpt').read_text()
            counts = {}
            for kind,prefix in [('setup',r'Design\s+WNS'),('hold',r'Design \(Hold\)\s+WNS')]:
                a = re.findall(prefix+r':\s*(\S+)\s+TNS:\s*(\S+)\s+Number of Violating Paths:\s*(\d+)',qor)
                assert len(a)==1
                w,t,c = a[0];counts[kind]=dict(native_WNS=float(w),native_TNS=float(t),violating_paths=int(c))
                if timing[kind]>=0:assert float(t)==0 and int(c)==0
            if side=='route_a':
                assert int(m['data_flops'])==366336
                assert 'checked_bits=48 undriven_bits=0' in (p/'entry_id_driver_check.rpt').read_text()
                for kind in ('setup','hold'):
                    text=(p/('gate_'+kind+'.rpt')).read_text()
                    assert 'clock gating '+kind in text.lower()
                    timing['gate_'+kind]=precision_slack(text)
                if stage!='primary_raw':
                    text=(p/'gated_data_hold.rpt').read_text()
                    arcs=re.findall(r'/Q\s+\(CKLNQ\w+\)\s+(\S+)\s+(\S+)\s+(\S+)',text)
                    assert arcs and all(float(incr)>0 for _,incr,_ in arcs)
            lint=(p/'check_design.rpt').read_text()
            assert not re.search(r'\(LINT-(?:3|5)\)',lint)
            timing_warnings = re.findall(r'^\s*Warning:.*$', (p/'check_timing.rpt').read_text(), re.M)
            assert all('(TIM-134)' in line for line in timing_warnings), timing_warnings
            warns=re.findall(r'^Warning:.*?\((LINT-\d+)\)',lint,re.M)
            out['sides'][side]['stages'][stage]=dict(area=area,timing_slack_ns=timing,qor=counts,
                timing_closed=all(v>=0 for v in timing.values()),
                lint_warning_counts={c:warns.count(c) for c in sorted(set(warns))})
    # The unchanged Full-KV primary compile must reproduce the accepted area.
    assert abs(out['sides']['full_kv']['stages']['primary_raw']['area']['total_area']-23091.432498)<2e-6
    out['area_ratios']={s:out['sides']['route_a']['stages'][s]['area']['total_area']/out['sides']['full_kv']['stages'][s]['area']['total_area'] for s in ('primary_raw','propagated_raw','propagated_hold_repaired')}
    out['artifact_sha256']={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and p.suffix in ('.ddc','.v','.sdc','.rpt','.tsv')}
    out['tool_artifact_closure']='PASS'
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    a=p.parse_args()
    result=check(a.root)
    (a.root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('KVZAP_RD1_WCG1_POSTCHECK_PASS_TOOL_ARTIFACT_ONLY')


if __name__=='__main__':main()
