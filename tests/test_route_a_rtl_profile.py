import json
from pathlib import Path

import pytest

from kvpress.route_a_rtl_profile import (
    PAGE_GENERATION_WRAP_QUIESCENCE,
    PageAllocatorReference,
    PageState,
    ProfileViolation,
    TransportEndpointCreditReference,
    load_and_validate_profile,
    validate_profile,
)


PROFILE = Path("analysis/architecture_gate_a3_verification_small_v1.json")
RTL_PROFILE = Path("analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json")


def test_verification_profile_is_finite_and_explicitly_not_a_deployment_profile():
    summary = load_and_validate_profile(PROFILE)
    assert summary == {
        "profile_id": "verification_small_v1",
        "profile_class": "verification_only",
        "rid_namespace": 4,
        "incarnation_namespace": 4,
        "minimum_page_id_width": 2,
        "page_pool_pages": 4,
        "transport_endpoint_credit": 2,
        "fragment_bytes": 64,
        "core_data_width_bits": 512,
    }


def test_rtl_entry_profile_requires_complete_envelope_and_never_accepts_a_template():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["profile_class"] = "rtl_entry"
    profile["evidence_class"] = "rtl_boundary_parameter_contract_no_performance_or_ppa_claim"
    with pytest.raises(ProfileViolation, match="deployment envelope"):
        validate_profile(profile)


def test_profile_rejects_unexplained_width_or_256b_accounting_as_rtl_fragment_width():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["transaction_identity"]["max_live"] = 5
    with pytest.raises(ProfileViolation, match="RID namespace"):
        validate_profile(profile)
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["profile_class"] = "rtl_entry"
    profile["evidence_class"] = "rtl_boundary_parameter_contract_no_performance_or_ppa_claim"
    profile["transaction_identity"]["max_live"] = 3
    profile["direct_pending_endpoint"]["fragment_bytes"] = 256
    profile["direct_pending_endpoint"]["core_data_width_bits"] = 2048
    profile["deployment_envelope"] = {
        "max_context_tokens": 1,
        "max_concurrent_sequences": 1,
        "num_layers": 36,
        "num_kv_heads": 8,
        "max_packed_page_population": 64,
        "hot_window_tokens": 128,
        "kv_payload_bytes_per_token": 512,
        "position_sidecar_bytes_per_token": 8,
        "cold_capacity_policy": "keep_all_cold_records",
        "max_pending_resident_records": 1,
        "max_live_pending_transactions": 1,
        "max_inflight_migration_pages": 1,
        "max_live_read_requests": 1,
        "max_live_write_requests": 1,
        "max_live_source_groups": 1,
        "num_pending_endpoints": 1,
        "num_pack_engines": 1,
        "kv_head_group_parallelism": 1,
        "total_cold_kv_hbm_pool_bytes": 131072,
    }
    with pytest.raises(ProfileViolation, match="256-B"):
        validate_profile(profile)


def test_selected_rtl_entry_anchor_uses_checked_capacity_and_resource_relations_without_claiming_performance():
    summary = load_and_validate_profile(RTL_PROFILE)
    assert summary["profile_class"] == "rtl_entry"
    assert summary["page_pool_pages"] == 146880
    assert summary["max_packed_pages"] == 146880
    assert summary["required_cold_pool_bytes"] == 4888199680
    assert summary["core_data_width_bits"] == 512


def test_rtl_entry_rejects_compression_sized_pending_storage_or_insufficient_shared_pool():
    profile = json.loads(RTL_PROFILE.read_text(encoding="utf-8"))
    profile["deployment_envelope"]["max_pending_resident_records"] -= 1
    with pytest.raises(ProfileViolation, match="keep-all pending-resident"):
        validate_profile(profile)
    profile = json.loads(RTL_PROFILE.read_text(encoding="utf-8"))
    profile["deployment_envelope"]["total_cold_kv_hbm_pool_bytes"] = 4888199679
    with pytest.raises(ProfileViolation, match="shared cold-KV HBM pool"):
        validate_profile(profile)


def test_rtl_entry_binds_external_logical_retirement_and_page_generation_quiescence():
    profile = json.loads(RTL_PROFILE.read_text(encoding="utf-8"))
    assert profile["allocator"]["logical_retirement_owner"] == "external_runtime_session_manager"
    assert profile["allocator"]["physical_reclamation_owner"] == "kv_subsystem_after_quiescence"
    profile["allocator"]["generation_wrap_quiescence"].pop()
    with pytest.raises(ProfileViolation, match="page-generation wrap quiescence"):
        validate_profile(profile)


def test_allocator_requires_publish_no_live_reference_and_generation_advance_before_reuse():
    allocator = PageAllocatorReference(1)
    original = allocator.allocate()
    allocator.write_commit(original)
    allocator.metadata_publish(original)
    allocator.retain_live_reference(original)
    with pytest.raises(ProfileViolation, match="live references"):
        allocator.mark_no_live_reference(original)
    allocator.release_live_reference(original)
    allocator.mark_no_live_reference(original)
    assert allocator.state(original) is PageState.RECLAIMABLE
    allocator.reclaim(original)
    with pytest.raises(ProfileViolation, match="stale or free"):
        allocator.state(original)
    reused = allocator.allocate()
    assert reused.page_id == original.page_id
    assert reused.generation == original.generation + 1


def test_allocator_rejects_publication_before_write_commit_and_pool_overallocation():
    allocator = PageAllocatorReference(1)
    page = allocator.allocate()
    with pytest.raises(ProfileViolation, match="write commit"):
        allocator.metadata_publish(page)
    with pytest.raises(ProfileViolation, match="no reusable"):
        allocator.allocate()


def test_finite_page_generation_wrap_requires_explicit_quiescence_authorization():
    allocator = PageAllocatorReference(1, generation_width=2)
    for _ in range(3):
        page = allocator.allocate()
        allocator.write_commit(page)
        allocator.metadata_publish(page)
        allocator.mark_no_live_reference(page)
        allocator.reclaim(page)

    wrapping = allocator.allocate()
    allocator.write_commit(wrapping)
    allocator.metadata_publish(wrapping)
    allocator.mark_no_live_reference(wrapping)
    with pytest.raises(ProfileViolation, match="wrap requires"):
        allocator.reclaim(wrapping)
    allocator.authorize_generation_wrap(wrapping, PAGE_GENERATION_WRAP_QUIESCENCE)
    allocator.reclaim(wrapping)
    assert allocator.allocate().generation == 0


def test_transport_endpoint_credit_is_lossless_and_distinct_from_metadata_credit():
    credits = TransportEndpointCreditReference(2)
    credits.reserve("direct:17")
    credits.reserve("s2:S2-A")
    with pytest.raises(ProfileViolation, match="unavailable"):
        credits.reserve("direct:23")
    credits.release("direct:17")
    credits.reserve("direct:23")
    assert credits.state() == (2, ("direct:23", "s2:S2-A"))
