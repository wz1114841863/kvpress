from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_activation_manifest import RTL2ActivationManifestError, load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis" / "rtl2_0_activation_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl2_activation_manifest.py"


def test_rtl2_0_inventory_names_all_required_events_and_does_not_false_pass():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert len(manifest["event_records"]) == 14
    assert len(manifest["carrier_records"]) == 20
    assert manifest["review_disposition"]["rtl2_0_pass"] is False
    assert manifest["scoreboard_schema"]["state"] == "required_before_first_behavioral_activation"


def test_write_terminal_and_metadata_commit_cannot_be_collapsed_into_one_untyped_path():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    write = next(record for record in manifest["event_records"] if record["event"] == "write_commit")
    write["carrier_ids"] = ["r1_to_r3_packed_write_terminal"]
    with pytest.raises(RTL2ActivationManifestError, match="distinguish R3 payload and R5 descriptor terminals"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    publish = next(record for record in manifest["event_records"] if record["event"] == "metadata_publish_commit")
    publish["carrier_ids"] = ["r3_publication_ack_to_r6"]
    with pytest.raises(RTL2ActivationManifestError, match="retain both frozen nested outputs"):
        validate_manifest(manifest)


def test_inert_carrier_without_amendment_and_premature_pass_are_rejected():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    carrier = next(record for record in manifest["carrier_records"] if record["id"] == "admission_to_r3_p3_claim")
    carrier["amendment_id"] = None
    with pytest.raises(RTL2ActivationManifestError, match="inactive carrier lacks an explicit amendment"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["review_disposition"]["rtl2_0_pass"] = True
    with pytest.raises(RTL2ActivationManifestError, match="must not pass"):
        validate_manifest(manifest)


def test_typed_router_must_bind_exact_rtl2_0d_endpoint_closure():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    router = next(record for record in manifest["required_amendments"] if record["id"] == "typed_delivery_router")
    router["closure_artifact"] = "analysis/rtl2_0c_r2_ingress_delivery_context_contract.md"
    with pytest.raises(RTL2ActivationManifestError, match="RTL2.0d endpoint-descriptor closure"):
        validate_manifest(manifest)


def test_r3_r5_durability_prerequisite_must_bind_exact_rtl2_0e_closure():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    durability = next(record for record in manifest["required_amendments"] if record["id"] == "r3_r5_durability_prerequisite_interface")
    durability["closure_status"] = "unreviewed"
    with pytest.raises(RTL2ActivationManifestError, match="RTL2.0e closure"):
        validate_manifest(manifest)


def test_source_packet_adapter_must_bind_exact_rtl2_0f_source_owner_ingress():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    carrier = next(record for record in manifest["carrier_records"] if record["id"] == "source_owner_to_packet_adapter")
    carrier["producer"] = "route_a_source_service_packet_adapter"
    with pytest.raises(RTL2ActivationManifestError, match="RTL2.0f source-owner ingress"):
        validate_manifest(manifest)


def test_r4_stub_provider_must_bind_exact_rtl2_0g_testbench_boundary():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    stub = next(record for record in manifest["required_amendments"] if record["id"] == "r4_result_stub_provider")
    stub["closure_artifact"] = "analysis/rtl1_6_r4_packet_boundary_contract.md"
    with pytest.raises(RTL2ActivationManifestError, match="RTL2.0g closure"):
        validate_manifest(manifest)


def test_validator_cli_supports_help_and_default_manifest():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "RTL2.0 activation manifest passed" in result.stdout
