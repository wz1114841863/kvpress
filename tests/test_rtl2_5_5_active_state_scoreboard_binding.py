import copy, json, subprocess, sys
from pathlib import Path
import pytest
from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.rtl2_reclaim_scoreboard_binding import ReclaimScoreboardBindingError, ReclaimScoreboardObservation, RouteARTL2ReclaimScoreboardAdapter, validate_binding
ROOT = Path(__file__).resolve().parents[1]; BINDING=ROOT/"analysis/rtl2_5_5_active_state_scoreboard_binding.json"; SCHEMA=ROOT/"analysis/rtl2_scoreboard_event_schema.json"; OVERLAY=ROOT/"analysis/rtl2_scoreboard_event_phase_reconciliation_01.json"; VALIDATOR=ROOT/"tools/validate_rtl2_5_5_active_state_scoreboard_binding.py"
def obs(name, **fields): return ReclaimScoreboardObservation(name, fields)
def test_reclaim_events_require_exact_old_ref_durable_order_and_no_replay():
    a=RouteARTL2ReclaimScoreboardAdapter(ROOT); ref=a.arm_reclaim()
    with pytest.raises(ReclaimScoreboardBindingError): a.dispatch(obs("page_free", page_ref=ref.page_id, generation=ref.generation))
    a.dispatch(obs("descriptor_invalidate", page_ref=ref.page_id, generation=ref.generation, descriptor_operation=2, delivery_context_ref=0))
    a.dispatch(obs("page_free", page_ref=ref.page_id, generation=ref.generation))
    with pytest.raises(ReclaimScoreboardBindingError): a.dispatch(obs("page_free", page_ref=ref.page_id, generation=ref.generation))
def test_reclaim_rejects_stale_generation_and_retire_ack_is_exactly_once():
    a=RouteARTL2ReclaimScoreboardAdapter(ROOT); ref=a.arm_reclaim()
    with pytest.raises(ReclaimScoreboardBindingError): a.dispatch(obs("descriptor_invalidate", page_ref=ref.page_id, generation=ref.generation+1, descriptor_operation=2, delivery_context_ref=0))
    a.arm_retire_ack(TransactionIdentity(3,1)); a.dispatch(obs("retire_ack", session_id=0, request_id=3, incarnation=1))
    with pytest.raises(ReclaimScoreboardBindingError): a.dispatch(obs("retire_ack", session_id=0, request_id=3, incarnation=1))
def test_binding_rejects_owner_drift_and_cli_validates():
    binding=json.loads(BINDING.read_text()); schema=json.loads(SCHEMA.read_text()); overlay=json.loads(OVERLAY.read_text()); bad=copy.deepcopy(binding); bad["events"][0]["required_fields"].pop()
    with pytest.raises(ReclaimScoreboardBindingError): validate_binding(bad,schema,overlay)
    assert "--phase-overlay" in subprocess.run([sys.executable,str(VALIDATOR),"--help"],cwd=ROOT,text=True,capture_output=True,check=True).stdout
    assert "passed" in subprocess.run([sys.executable,str(VALIDATOR)],cwd=ROOT,text=True,capture_output=True,check=True).stdout
