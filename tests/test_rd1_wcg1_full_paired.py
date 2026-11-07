"""Fail-closed full-top composition/policy gates without EDA execution."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import freeze_rd1_wcg1_input as FREEZE
import check_rd1_wcg1_full_paired as CHECK
_spec = importlib.util.spec_from_file_location('wcg1_fixture_helpers', ROOT/'tests/test_wcg1_wrapper_mapping.py')
_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers)
wrapper_fixture = _helpers.fixture


def test_reference_normalization_preserves_literals_and_logic():
    assert FREEZE.normalized('a = 1; // comment\nb = "x // y";') == 'a=1;b="x // y";'
    assert FREEZE.normalized('a = 1;') != FREEZE.normalized('a = 0;')
    assert FREEZE.normalized('b="x y";') != FREEZE.normalized('b="xy";')


def test_original_compile_procedure_boundary_is_extracted_without_running():
    script = '''set f [open {%s} r]
set original [read $f]; close $f
set marker "if \\{\\[catch \\{kvzap_dc_main\\}"
set boundary [string first $marker $original]
if {$boundary < 0} {error missing}
eval [string range $original 0 [expr {$boundary-1}]]
if {[info procs kvzap_dc_main] eq ""} {error missing_proc}
puts ORIGINAL_PROCEDURES_ONLY_PASS
''' % (ROOT/'hardware/route_a/dc/run_kvzap_control_projection_dc_feasibility.tcl')
    result = subprocess.run(['tclsh'], input=script, text=True, capture_output=True)
    assert result.returncode == 0 and not result.stderr
    assert 'ORIGINAL_PROCEDURES_ONLY_PASS' in result.stdout


def fixture(tmp_path):
    old = wrapper_fixture(tmp_path/'wrapper')
    root = tmp_path/'full'
    for side, original in [('full_kv','reference'),('route_a','gated')]:
        d = root/side
        d.mkdir(parents=True)
        (d/'exit_status').write_text('0\n')
        (d/'native.log').write_text('KVZAP_RD1_WCG1_SIDE_PASS top='+side+'_control_projection\n')
        for stage, src in [('primary_raw','raw'),('propagated_raw','raw'),('propagated_hold_repaired','repaired')]:
            dest = d/stage
            shutil.copytree(old/original/src,dest)
            (dest/'entry_id.rpt').rename(dest/'entry_id_driver_check.rpt')
            total = 23091.432498 if side=='full_kv' else 20000
            (dest/'area.rpt').write_text('Total cell area: {}\nCombinational area: 40\nNoncombinational area: {}\nBuf/Inv area: 2\n'.format(total,total-40))
            p=dest/'metrics.tsv'
            p.write_text(p.read_text().replace('propagated\ttrue','propagated\t'+str(int(stage!='primary_raw'))))
            if stage=='primary_raw':
                p=dest/'mapped.sdc'
                p.write_text(p.read_text().replace('set_propagated_clock [get_clocks kvzap_control_clk]\n',''))
    return root


def test_primary_and_supplements_have_separate_area_and_timing_verdicts(tmp_path):
    root=fixture(tmp_path)
    d=root/'route_a/propagated_hold_repaired'
    p=d/'metrics.tsv';p.write_text(p.read_text().replace('min_slack_ns\t0.01','min_slack_ns\t-0.01'))
    (d/'hold.rpt').write_text('slack (VIOLATED) -0.01\n')
    result=CHECK.check(root)
    assert result['tool_artifact_closure']=='PASS'
    assert not result['sides']['route_a']['stages']['propagated_hold_repaired']['timing_closed']


@pytest.mark.parametrize('fault',['primary_propagated','supplement_ideal','period','gate_arc','driver','data','gates','timing_coverage','native_error','baseline_area'])
def test_broken_full_top_evidence_rejects(tmp_path,fault):
    root=fixture(tmp_path)
    d=root/'route_a/propagated_raw'
    if fault in ('primary_propagated','supplement_ideal','period'):
        p=(root/'route_a/primary_raw' if fault=='primary_propagated' else d)/'mapped.sdc'
        t=p.read_text()
        if fault=='primary_propagated':t+='set_propagated_clock [get_clocks kvzap_control_clk]\n'
        elif fault=='supplement_ideal':t=t.replace('set_propagated_clock [get_clocks kvzap_control_clk]','')
        else:t=t.replace('-period 2','-period 3')
        p.write_text(t)
    elif fault=='gate_arc':
        (d/'gated_data_hold.rpt').write_text('x/Q (CKLNQD1BWP12T30P140LVT) 0.05 0 0.03 r\n')
    elif fault=='driver':
        (d/'entry_id_driver_check.rpt').write_text('checked_bits=48 undriven_bits=1\n')
    elif fault in ('data','gates'):
        p=d/'metrics.tsv';p.write_text(p.read_text().replace('366336','366335') if fault=='data' else p.read_text().replace('4608','4607'))
    elif fault=='timing_coverage':
        (d/'check_timing.rpt').write_text('Warning: unconstrained endpoint\n')
    elif fault=='baseline_area':
        p=root/'full_kv/primary_raw/area.rpt';p.write_text(p.read_text().replace('23091.432498','24091.432498').replace('23051.432498','24051.432498'))
    else:
        (d/'check_design.rpt').write_text('Error: redirected native failure\n')
    with pytest.raises(AssertionError):CHECK.check(root)


def test_only_the_exact_retained_full_kv_error_is_allowed():
    known="Error: /input/full_kv_control_projection.sv:6646: Unable to open file `layers-route_a_core_side_arbiter-Verification.sv': No such file or directory. (VER-41)"
    assert CHECK.native_errors(known,'full_kv') == [known]
    for text,side in [(known,'route_a'),(known.replace('VER-41','OTHER'),'full_kv'),(known+'\n'+known,'full_kv')]:
        with pytest.raises(AssertionError):CHECK.native_errors(text,side)
