from __future__ import annotations
import copy, subprocess, sys
from pathlib import Path
import pytest
from kvpress.rtl2_admission_group_builder_manifest import RTL2AdmissionGroupBuilderError, load_manifest, validate_manifest
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"analysis/rtl2_0b_admission_group_builder_manifest.json"
VALIDATOR=ROOT/"tools/validate_rtl2_admission_group_builder_manifest.py"
def test_group_builder_freezes_group_order_and_non_authoritative_owner():
    manifest=load_manifest(MANIFEST); validate_manifest(manifest)
    assert manifest["anchor"]["max_group_members"]==64
    assert manifest["child"]["name"]=="route_a_admission_publication_ingress_adapter"
def test_group_builder_rejects_span_reconstruction_and_p3_owner_drift():
    manifest=copy.deepcopy(load_manifest(MANIFEST)); manifest["anchor"]["forbidden"].remove("contiguous first-entry-plus-count reconstruction")
    with pytest.raises(RTL2AdmissionGroupBuilderError,match="forbid span reconstruction"): validate_manifest(manifest)
    manifest=copy.deepcopy(load_manifest(MANIFEST)); claim=next(x for x in manifest["carriers"] if x["id"]=="adapter_to_r3_p3_claim"); claim["rule"]="issue once"
    with pytest.raises(RTL2AdmissionGroupBuilderError,match="P3 claim owner provenance"): validate_manifest(manifest)
def test_validator_cli_supports_help_and_default_manifest():
    help_result=subprocess.run([sys.executable,str(VALIDATOR),"--help"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert "--manifest" in help_result.stdout
    result=subprocess.run([sys.executable,str(VALIDATOR)],cwd=ROOT,text=True,capture_output=True,check=True)
    assert "RTL2.0b group-builder manifest passed" in result.stdout
