from __future__ import annotations
import copy,subprocess,sys
from pathlib import Path
import pytest
from kvpress.rtl2_r2_ingress_delivery_context_manifest import RTL2R2IngressDeliveryContextError,load_manifest,validate_manifest
ROOT=Path(__file__).resolve().parents[1];MANIFEST=ROOT/"analysis/rtl2_0c_r2_ingress_delivery_context_manifest.json";VALIDATOR=ROOT/"tools/validate_rtl2_r2_ingress_delivery_context_manifest.py"
def test_r2_ingress_keeps_six_classes_r2_arbitration_and_opaque_context_owner():
 m=load_manifest(MANIFEST);validate_manifest(m);assert len(m["candidate_classes"])==6;assert m["delivery_context_registry"]["owner"]=="route_a_delivery_context_registry"
def test_external_selection_or_context_reuse_rules_are_rejected():
 m=copy.deepcopy(load_manifest(MANIFEST));m["logical_ingress"]["same_opportunity_rule"]="top selects an input"
 with pytest.raises(RTL2R2IngressDeliveryContextError,match="permits external selection"):validate_manifest(m)
 m=copy.deepcopy(load_manifest(MANIFEST));m["delivery_context_registry"]["forbidden"].remove("ref reuse while live")
 with pytest.raises(RTL2R2IngressDeliveryContextError,match="safety prohibitions"):validate_manifest(m)
def test_validator_cli_supports_help_and_default_manifest():
 h=subprocess.run([sys.executable,str(VALIDATOR),"--help"],cwd=ROOT,text=True,capture_output=True,check=True);assert "--manifest" in h.stdout
 r=subprocess.run([sys.executable,str(VALIDATOR)],cwd=ROOT,text=True,capture_output=True,check=True);assert "RTL2.0c R2 ingress/context manifest passed" in r.stdout
