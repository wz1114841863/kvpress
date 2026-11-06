"""Fail-closed input/STA accounting checks; no simulator or EDA invocation."""
import sys
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare_wcg1_wrapper_mapping as PREP
import check_wcg1_wrapper_mapping as CHECK


@pytest.mark.parametrize('status', [0, 1])
def test_shared_native_gate_command_checks_all_instances_and_return_status(status):
    text = (ROOT / 'hardware/route_a/dc/screen_wcg1_wrapper_sta.tcl').read_text()
    line = next(x.strip() for x in text.splitlines() if 'if {![set_size_only' in x)
    script = '''proc set_size_only {args} {
      if {[lindex $args 0] ne "-all_instances"} {error UID-192}
      return %d
    }
    set gates native_shared_leaf
    ''' % status
    script += '\nif {[catch {' + line + '} message]} {puts stderr $message; exit 1}\n'
    result = subprocess.run(['tclsh'], input=script, text=True, capture_output=True)
    assert (result.returncode == 0) == bool(status)


def test_inline_resource_can_be_explicitly_closed_but_not_silently_changed(tmp_path):
    helper = ROOT / 'hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteACompactWordClocking.scala'
    modules = {}
    canonical, emitted = PREP.bind_inline(modules, helper)
    assert not emitted and PREP.NATIVE in modules[PREP.GATE][1]
    modules[PREP.GATE] = (helper, PREP.header(canonical) + '\nendmodule')
    PREP.bind_inline(modules, helper)
    modules[PREP.GATE] = (helper, canonical.replace('enable_low = enable', 'enable_low = 0'))
    with pytest.raises(AssertionError):
        PREP.bind_inline(modules, helper)


def test_all_record_fields_and_rows_are_required():
    fields = {'logical_position': 15, 'payload_ref': 64}
    registers = {'membershipEntries_{}_{}_{}'.format(b, r, f): w
                 for b in range(36) for r in range(64) for f, w in fields.items()}
    PREP.data_shape(registers, 'reference', 'member')
    registers.pop('membershipEntries_35_63_payload_ref')
    with pytest.raises(AssertionError):
        PREP.data_shape(registers, 'reference', 'member')


def test_full_suffix_width_cannot_be_silently_reduced():
    fields = {'transaction_identity_request_id': 3, 'transaction_identity_incarnation': 2,
              'payload_handle_or_address': 64, 'source_generation': 8, 'destination_endpoint': 3}
    registers = {'suffixWord{}_{}'.format('_' + str(r) if r else '', f): w
                 for r in range(2304) for f, w in fields.items()}
    PREP.data_shape(registers, 'gated', 'suffix')
    registers['suffixWord_payload_handle_or_address'] = 16
    with pytest.raises(AssertionError):
        PREP.data_shape(registers, 'gated', 'suffix')


def fixture(root):
    sdc = '''create_clock [get_ports clock] -name kvzap_control_clk -period 2 -waveform {0 1}
set_clock_uncertainty -setup 0.1 [get_clocks kvzap_control_clk]
set_clock_uncertainty -hold 0.02 [get_clocks kvzap_control_clk]
set_propagated_clock [get_clocks kvzap_control_clk]
set_input_delay -clock kvzap_control_clk 0.2 [get_ports reset]
set_output_delay -clock kvzap_control_clk 0.2 [get_ports result]
set_input_transition -max 0.05 [get_ports clock]
set_load -pin_load 0.005 [get_ports result]
'''
    for side in ('reference', 'gated'):
        out = root / side
        out.mkdir(parents=True)
        (out / 'exit_status').write_text('0\n')
        (out / 'native.log').write_text('KVZAP_WCG1_WRAPPER_SIDE_RUN_PASS side=' + side + '\n')
        for stage in ('raw', 'repaired'):
            dest = out / stage
            dest.mkdir()
            total = 100 if side == 'reference' else 90
            for name in ('references', 'check_design', 'check_timing', 'constraints', 'clocks', 'gating', 'clock_net'):
                (dest / (name + '.rpt')).write_text('report\n')
            (dest / 'area.rpt').write_text('Total cell area: {}\nCombinational area: 40\nNoncombinational area: {}\n'.format(total, total - 40))
            (dest / 'qor.rpt').write_text('Design WNS: 0 TNS: 0 Number of Violating Paths: 0\nDesign (Hold) WNS: 0 TNS: 0 Number of Violating Paths: 0\n')
            (dest / 'entry_id.rpt').write_text('checked_bits=48 undriven_bits=0\n')
            (dest / 'setup.rpt').write_text('slack (MET) 0.2\n')
            (dest / 'hold.rpt').write_text('slack (MET) 0.01\n')
            for name in ('mapped.ddc', 'mapped.v'):
                (dest / name).write_text('fixture\n')
            (dest / 'mapped.sdc').write_text(sdc)
            m = dict(data_flops=366336, clock_gates=4608 if side == 'gated' else 0,
                     period_ns=2, propagated='true', total_area=total, combinational_area=40,
                     sequential_area=total - 40, max_slack_ns=.2, min_slack_ns=.01)
            if side == 'gated':
                m.update(gate_max_slack_ns=.1, gate_min_slack_ns=.02)
                (dest / 'gate_setup.rpt').write_text('clock gating setup\nslack (MET) 0.1\n')
                (dest / 'gate_hold.rpt').write_text('clock gating hold\nslack (MET) 0.02\n')
                (dest / 'gated_data_hold.rpt').write_text('memberGate/native_gate/Q (CKLNQD1BWP12T30P140LVT) 0.05 0.01 0.03 r\n')
            (dest / 'metrics.tsv').write_text('metric\tvalue\n' + ''.join('{}\t{}\n'.format(k, v) for k, v in m.items()))
    return root


def test_negative_hold_is_an_outcome_not_tool_failure(tmp_path):
    root = fixture(tmp_path)
    p = root / 'gated/repaired/metrics.tsv'
    p.write_text(p.read_text().replace('min_slack_ns\t0.01', 'min_slack_ns\t-0.01'))
    (p.parent / 'hold.rpt').write_text('slack (VIOLATED) -0.01\n')
    r = CHECK.check(root)
    assert r['artifact_closure'] == 'PASS'
    assert not r['comparison']['repaired']['both_timing_closed']


@pytest.mark.parametrize('mutation', ['area', 'period', 'uncertainty', 'driver', 'gate_arc', 'native_error', 'propagated', 'timing_warning'])
def test_bad_native_or_boundary_evidence_is_rejected(tmp_path, mutation):
    root = fixture(tmp_path)
    dest = root / 'gated/raw'
    if mutation == 'area':
        (dest / 'area.rpt').write_text('Total area: 90\n')
    elif mutation in ('period', 'uncertainty'):
        p = dest / 'mapped.sdc'
        p.write_text(p.read_text().replace('-period 2', '-period 3') if mutation == 'period' else p.read_text().replace('-hold 0.02', '-hold 0.01'))
    elif mutation == 'driver':
        (dest / 'entry_id.rpt').write_text('checked_bits=48 undriven_bits=1\n')
    elif mutation == 'gate_arc':
        (dest / 'gated_data_hold.rpt').write_text('memberGate/native_gate/Q (CKLNQD1BWP12T30P140LVT) 0.05 0 0.03 r\n')
    elif mutation == 'native_error':
        (dest / 'gating.rpt').write_text('Error: redirected failure\n')
    elif mutation == 'propagated':
        p = dest / 'metrics.tsv'; p.write_text(p.read_text().replace('propagated\ttrue', 'propagated\tfalse'))
    else:
        (dest / 'check_timing.rpt').write_text('Warning: unconstrained endpoint\n')
    with pytest.raises(AssertionError):
        CHECK.check(root)
