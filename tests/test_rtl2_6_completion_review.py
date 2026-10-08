import copy, subprocess, sys
from pathlib import Path
import pytest
from kvpress.rtl2_6_completion_review import RTL26CompletionReviewError, load_review, validate_entry_audit, validate_source_hashes
ROOT=Path(__file__).resolve().parents[1]; REVIEW=ROOT/"analysis/rtl2_6_completion_review_manifest.json"; SCHEMA=ROOT/"analysis/rtl2_scoreboard_event_schema.json"; OVERLAY=ROOT/"analysis/rtl2_scoreboard_event_phase_reconciliation_01.json"; VALIDATOR=ROOT/"tools/validate_rtl2_6_completion_review.py"
def payloads():
 import json
 return load_review(REVIEW), json.loads(SCHEMA.read_text()), json.loads(OVERLAY.read_text())
def test_entry_audit_exactly_records_current_bound_and_missing_event_sets():
 r,s,o=payloads(); validate_entry_audit(r,s,o); assert len(r["bound_events"])==4 and len(r["missing_event_bindings"])==10
def test_entry_audit_rejects_false_pass_or_event_inventory_drift():
 r,s,o=payloads(); bad=copy.deepcopy(r); bad["complete_retained_transaction_witness"]=True
 with pytest.raises(RTL26CompletionReviewError): validate_entry_audit(bad,s,o)
 bad=copy.deepcopy(r); bad["bound_events"].pop()
 with pytest.raises(RTL26CompletionReviewError): validate_entry_audit(bad,s,o)
def test_entry_audit_hash_binds_reviewed_sources():
 r,_,_=payloads(); validate_source_hashes(r,ROOT); bad=copy.deepcopy(r); bad["source_sha256"]["analysis/README.md"]="0"*64
 with pytest.raises(RTL26CompletionReviewError): validate_source_hashes(bad,ROOT)
def test_entry_audit_cli_has_help_and_validates_default():
 assert "--phase-overlay" in subprocess.run([sys.executable,str(VALIDATOR),"--help"],cwd=ROOT,text=True,capture_output=True,check=True).stdout
 assert "entry audit passed" in subprocess.run([sys.executable,str(VALIDATOR)],cwd=ROOT,text=True,capture_output=True,check=True).stdout
