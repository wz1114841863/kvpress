"""Finite RTL-boundary profile validation for Route-A Gate-A3.

The module is a pure-software schema and allocator-safety reference.  It does
not model RTL cycles, HBM commands, macro ports, timing, throughput, or PPA.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


PROFILE_SCHEMA = "route-a-rtl-boundary-profile-1"

_PROFILE_SCOPE = {
    "semantic_interface": "retention_kv_semantic_interface_v1",
    "evidence_scope": "route_a_qwen3_8b_anchor_only",
}

PAGE_GENERATION_WRAP_QUIESCENCE = frozenset(
    {
        "no_live_page_reference",
        "no_outstanding_old_page_response",
        "no_s2_old_page_association",
        "no_direct_pending_old_page_association",
        "no_metadata_old_page_reference",
    }
)


class ProfileViolation(AssertionError):
    """A profile or allocator event lacks a finite A3-safe interpretation."""


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ProfileViolation(f"{field} must be a positive integer")
    return value


def _ceil_log2(value: int) -> int:
    return max(1, (value - 1).bit_length())


def load_and_validate_profile(path: Path) -> dict[str, Any]:
    return validate_profile(json.loads(path.read_text(encoding="utf-8")))


def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Validate one complete A3 profile; templates are intentionally rejected."""
    if profile.get("schema_version") != PROFILE_SCHEMA:
        raise ProfileViolation("unsupported profile schema")
    profile_class = profile.get("profile_class")
    if profile_class not in {"verification_only", "rtl_entry"}:
        raise ProfileViolation("profile_class must be verification_only or rtl_entry")
    if not isinstance(profile.get("profile_id"), str) or not profile["profile_id"]:
        raise ProfileViolation("profile_id is required")
    expected_evidence = (
        "verification_only_pure_software_rtl_boundary_contract"
        if profile_class == "verification_only"
        else "rtl_boundary_parameter_contract_no_performance_or_ppa_claim"
    )
    if profile.get("evidence_class") != expected_evidence:
        raise ProfileViolation("profile evidence_class does not match profile_class")
    if profile.get("profile_scope") != _PROFILE_SCOPE:
        raise ProfileViolation("profile scope must retain the Route-A Qwen3-8B anchor boundary")
    frozen = profile.get("frozen_interface")
    if frozen != {"page_tokens": 64, "s2_slots": 2, "gqa_consumers": 4, "pending_delivery": "direct_pending_endpoint_v1"}:
        raise ProfileViolation("profile must preserve the frozen Route-A interface")

    identity = profile.get("transaction_identity")
    allocator = profile.get("allocator")
    endpoint = profile.get("direct_pending_endpoint")
    clock = profile.get("clock_wrapper")
    fault = profile.get("fault")
    if not all(isinstance(section, dict) for section in (identity, allocator, endpoint, clock, fault)):
        raise ProfileViolation("profile lacks a required finite interface section")

    rid_width = _positive_int(identity.get("rid_width"), "transaction_identity.rid_width")
    incarnation_width = _positive_int(identity.get("incarnation_width"), "transaction_identity.incarnation_width")
    max_live = _positive_int(identity.get("max_live"), "transaction_identity.max_live")
    if identity.get("mode") != "epoch_reuse" or identity.get("live_rid_unique") is not True:
        raise ProfileViolation("A3 RTL profile requires epoch_reuse with unique live RID")
    if max_live > 2**rid_width:
        raise ProfileViolation("max_live exceeds finite RID namespace")
    quiescence = identity.get("wrap_quiescence")
    required_quiescence = {
        "no_live_request",
        "no_outstanding_old_response",
        "no_s2_old_association",
        "no_direct_pending_old_association",
    }
    if not isinstance(quiescence, list) or set(quiescence) != required_quiescence:
        raise ProfileViolation("epoch wrap quiescence predicate is incomplete")

    pool_pages = _positive_int(allocator.get("page_pool_pages"), "allocator.page_pool_pages")
    page_id_width = _positive_int(allocator.get("page_id_width"), "allocator.page_id_width")
    generation_width = _positive_int(allocator.get("generation_width"), "allocator.generation_width")
    max_live_refs = _positive_int(allocator.get("max_live_refs"), "allocator.max_live_refs")
    if page_id_width < _ceil_log2(pool_pages) or max_live_refs > pool_pages:
        raise ProfileViolation("allocator width or live-reference bound is invalid")
    if allocator.get("reclamation") != "explicit_no_live_reference_then_generation_advance":
        raise ProfileViolation("allocator reclamation lifecycle is not closed")
    page_quiescence = allocator.get("generation_wrap_quiescence")
    if not isinstance(page_quiescence, list) or set(page_quiescence) != PAGE_GENERATION_WRAP_QUIESCENCE:
        raise ProfileViolation("page-generation wrap quiescence predicate is incomplete")
    if allocator.get("logical_retirement_owner") != "external_runtime_session_manager":
        raise ProfileViolation("logical retirement must be owned by the external runtime")
    if allocator.get("physical_reclamation_owner") != "kv_subsystem_after_quiescence":
        raise ProfileViolation("physical reclamation owner is incomplete")

    transport_credit = _positive_int(endpoint.get("transport_endpoint_credit"), "direct_pending_endpoint.transport_endpoint_credit")
    max_fragments = _positive_int(endpoint.get("max_live_fragments"), "direct_pending_endpoint.max_live_fragments")
    max_records = _positive_int(endpoint.get("max_records_in_flight"), "direct_pending_endpoint.max_records_in_flight")
    fragment_bytes = _positive_int(endpoint.get("fragment_bytes"), "direct_pending_endpoint.fragment_bytes")
    core_data_width_bits = _positive_int(endpoint.get("core_data_width_bits"), "direct_pending_endpoint.core_data_width_bits")
    if max_fragments > transport_credit or max_records > transport_credit:
        raise ProfileViolation("endpoint in-flight bounds exceed transport credit")
    if endpoint.get("holding_owner") != "transport_endpoint" or endpoint.get("full_action") != "backpressure_only":
        raise ProfileViolation("endpoint transient ownership/backpressure is incomplete")
    if core_data_width_bits != fragment_bytes * 8:
        raise ProfileViolation("core data width must match the selected fragment width")
    if fragment_bytes == 256 and profile_class != "verification_only":
        raise ProfileViolation("the 256-B accounting beat cannot select an RTL fragment width")
    if clock != {"boundary": "abstract_core_clk", "claim": "no_hbm_timing_or_controller_model"}:
        raise ProfileViolation("clock wrapper boundary is incomplete")
    if fault != {"policy": "fail_closed", "upward_status": True, "full_kv_fallback": False}:
        raise ProfileViolation("fault policy is incomplete")

    envelope = profile.get("deployment_envelope")
    if profile_class == "rtl_entry":
        required_envelope = {
            "max_context_tokens",
            "max_concurrent_sequences",
            "num_layers",
            "num_kv_heads",
            "max_packed_page_population",
            "hot_window_tokens",
            "kv_payload_bytes_per_token",
            "position_sidecar_bytes_per_token",
            "cold_capacity_policy",
            "max_pending_resident_records",
            "max_live_pending_transactions",
            "max_inflight_migration_pages",
            "max_live_read_requests",
            "max_live_write_requests",
            "max_live_source_groups",
            "num_pending_endpoints",
            "num_pack_engines",
            "kv_head_group_parallelism",
            "total_cold_kv_hbm_pool_bytes",
        }
        if not isinstance(envelope, dict) or set(envelope) != required_envelope:
            raise ProfileViolation("rtl_entry requires a complete deployment envelope")
        numeric_envelope_fields = required_envelope - {"cold_capacity_policy"}
        for key in numeric_envelope_fields:
            _positive_int(envelope[key], f"deployment_envelope.{key}")
        if envelope["num_layers"] != 36 or envelope["num_kv_heads"] != 8 or envelope["max_packed_page_population"] != 64:
            raise ProfileViolation("rtl_entry must state the frozen Qwen3-8B anchor fields")
        if envelope["hot_window_tokens"] != 128 or envelope["kv_payload_bytes_per_token"] != 512 or envelope["position_sidecar_bytes_per_token"] != 8:
            raise ProfileViolation("rtl_entry must state the frozen Route-A storage anchors")
        if envelope["cold_capacity_policy"] != "keep_all_cold_records":
            raise ProfileViolation("rtl_entry must use the keep-all cold capacity guard")
        required_live = envelope["max_live_read_requests"] + envelope["max_live_write_requests"] + envelope["max_live_source_groups"]
        if required_live > max_live:
            raise ProfileViolation("deployment live request bound exceeds transaction namespace")
        if envelope["max_live_pending_transactions"] != envelope["num_pending_endpoints"]:
            raise ProfileViolation("live pending transactions must equal the selected pending endpoint count")
        expected_reads = 2 + envelope["num_pending_endpoints"] + envelope["num_pack_engines"]
        if envelope["max_live_read_requests"] != expected_reads:
            raise ProfileViolation("live read bound must enumerate S2, pending-endpoint, and packing destinations")
        if envelope["max_live_write_requests"] != envelope["num_pack_engines"]:
            raise ProfileViolation("live write bound must equal the selected pack-engine count")
        expected_source_groups = envelope["max_concurrent_sequences"] * envelope["kv_head_group_parallelism"]
        if envelope["max_live_source_groups"] != expected_source_groups:
            raise ProfileViolation("source-group bound must match selected sequence and KV-head-group parallelism")

        cold_tokens_per_sequence = envelope["max_context_tokens"] - envelope["hot_window_tokens"]
        if cold_tokens_per_sequence <= 0:
            raise ProfileViolation("context envelope must exceed the frozen hot window")
        max_pending_bound = cold_tokens_per_sequence * envelope["max_concurrent_sequences"] * envelope["num_layers"] * envelope["num_kv_heads"]
        if envelope["max_pending_resident_records"] != max_pending_bound:
            raise ProfileViolation("keep-all pending-resident bound must cover every cold layer-head record")
        pages_per_stream = (cold_tokens_per_sequence + envelope["max_packed_page_population"] - 1) // envelope["max_packed_page_population"]
        max_packed_pages = pages_per_stream * envelope["max_concurrent_sequences"] * envelope["num_layers"] * envelope["num_kv_heads"]
        if pool_pages < max_packed_pages or page_id_width < _ceil_log2(pool_pages):
            raise ProfileViolation("page pool/ID width does not cover the checked packed-page envelope")
        page_storage_bytes = envelope["max_packed_page_population"] * (
            envelope["kv_payload_bytes_per_token"] + envelope["position_sidecar_bytes_per_token"]
        )
        required_cold_pool_bytes = (max_packed_pages + envelope["max_inflight_migration_pages"]) * page_storage_bytes
        if envelope["total_cold_kv_hbm_pool_bytes"] < required_cold_pool_bytes:
            raise ProfileViolation("shared cold-KV HBM pool cannot cover retained records plus migration reserve")
    elif envelope is not None:
        raise ProfileViolation("verification_only profile must not carry a deployment envelope")

    return {
        "profile_id": profile["profile_id"],
        "profile_class": profile_class,
        "rid_namespace": 2**rid_width,
        "incarnation_namespace": 2**incarnation_width,
        "minimum_page_id_width": _ceil_log2(pool_pages),
        "page_pool_pages": pool_pages,
        "transport_endpoint_credit": transport_credit,
        "fragment_bytes": fragment_bytes,
        "core_data_width_bits": core_data_width_bits,
        **(
            {
                "max_packed_pages": max_packed_pages,
                "required_cold_pool_bytes": required_cold_pool_bytes,
            }
            if profile_class == "rtl_entry"
            else {}
        ),
    }


class PageState(str, Enum):
    FREE = "free"
    ALLOCATED_UNPUBLISHED = "allocated_unpublished"
    WRITE_COMMITTED = "write_committed"
    LIVE_PACKED = "live_packed"
    RECLAIMABLE = "reclaimable"


@dataclass(frozen=True)
class PageRef:
    page_id: int
    generation: int


@dataclass
class _Page:
    generation: int = 0
    state: PageState = PageState.FREE
    live_references: int = 0


class PageAllocatorReference:
    """Safety lifecycle for page ID/generation reuse; no allocation policy model."""

    def __init__(self, page_pool_pages: int, *, generation_width: int | None = None) -> None:
        self._pages = [_Page() for _ in range(_positive_int(page_pool_pages, "page_pool_pages"))]
        self._generation_modulus = None if generation_width is None else 2 ** _positive_int(generation_width, "generation_width")
        self._wrap_authorized_page_ids: set[int] = set()

    def allocate(self) -> PageRef:
        for page_id, page in enumerate(self._pages):
            if page.state is PageState.FREE:
                page.state = PageState.ALLOCATED_UNPUBLISHED
                return PageRef(page_id, page.generation)
        raise ProfileViolation("allocator has no reusable page")

    def write_commit(self, ref: PageRef) -> None:
        page = self._resolve(ref)
        self._require(page.state is PageState.ALLOCATED_UNPUBLISHED, "write commit requires allocated unpublished page")
        page.state = PageState.WRITE_COMMITTED

    def metadata_publish(self, ref: PageRef) -> None:
        page = self._resolve(ref)
        self._require(page.state is PageState.WRITE_COMMITTED, "publication requires write commit")
        page.state = PageState.LIVE_PACKED

    def retain_live_reference(self, ref: PageRef) -> None:
        page = self._resolve(ref)
        self._require(page.state is PageState.LIVE_PACKED, "live reference requires published page")
        page.live_references += 1

    def release_live_reference(self, ref: PageRef) -> None:
        page = self._resolve(ref)
        self._require(page.state is PageState.LIVE_PACKED and page.live_references > 0, "invalid live reference release")
        page.live_references -= 1

    def mark_no_live_reference(self, ref: PageRef) -> None:
        page = self._resolve(ref)
        self._require(page.state is PageState.LIVE_PACKED and page.live_references == 0, "page still has live references")
        page.state = PageState.RECLAIMABLE

    def reclaim(self, ref: PageRef) -> None:
        page = self._resolve(ref)
        self._require(page.state is PageState.RECLAIMABLE and page.live_references == 0, "page is not reclaimable")
        if self._generation_modulus is not None and page.generation + 1 == self._generation_modulus:
            self._require(ref.page_id in self._wrap_authorized_page_ids, "page-generation wrap requires explicit quiescence")
            self._wrap_authorized_page_ids.remove(ref.page_id)
            page.generation = 0
        else:
            page.generation += 1
        page.state = PageState.FREE

    def authorize_generation_wrap(self, ref: PageRef, quiescence: set[str] | frozenset[str]) -> None:
        """Accept the externally checked safety predicate required before finite tag wrap."""
        page = self._resolve(ref)
        self._require(self._generation_modulus is not None, "unbounded reference generations do not wrap")
        self._require(page.state is PageState.RECLAIMABLE, "page-generation wrap requires reclaimable page")
        self._require(page.generation + 1 == self._generation_modulus, "page generation is not at wrap")
        self._require(set(quiescence) == PAGE_GENERATION_WRAP_QUIESCENCE, "page-generation wrap quiescence predicate is incomplete")
        self._wrap_authorized_page_ids.add(ref.page_id)

    def state(self, ref: PageRef) -> PageState:
        return self._resolve(ref).state

    def _resolve(self, ref: PageRef) -> _Page:
        if not isinstance(ref, PageRef) or not 0 <= ref.page_id < len(self._pages):
            raise ProfileViolation("invalid page reference")
        page = self._pages[ref.page_id]
        self._require(page.generation == ref.generation and page.state is not PageState.FREE, "stale or free page reference")
        return page

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise ProfileViolation(message)


class TransportEndpointCreditReference:
    """Lossless transient endpoint-credit reference; not an M2 queue model."""

    def __init__(self, capacity: int) -> None:
        self._capacity = _positive_int(capacity, "transport_endpoint_credit")
        self._owners: set[str] = set()

    def reserve(self, owner: str) -> None:
        if not owner or owner in self._owners:
            raise ProfileViolation("endpoint credit owner is invalid or duplicated")
        if len(self._owners) >= self._capacity:
            raise ProfileViolation("transport endpoint credit unavailable")
        self._owners.add(owner)

    def release(self, owner: str) -> None:
        if owner not in self._owners:
            raise ProfileViolation("endpoint credit release lacks ownership")
        self._owners.remove(owner)

    def state(self) -> tuple[int, tuple[str, ...]]:
        return self._capacity, tuple(sorted(self._owners))
