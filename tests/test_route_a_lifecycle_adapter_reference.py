import pytest

from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.route_a_lifecycle_adapter_reference import (
    INIT_ACKS,
    RETIRE_DRAIN_ACKS,
    AdapterBackpressure,
    AdapterState,
    AttentionServiceRequest,
    AuthorityState,
    KVArrival,
    LifecycleAdapterViolation,
    MaturityDisposition,
    RetentionDisposition,
    RouteALifecycleAdapterReference,
    SessionRetireRequest,
    SessionStart,
)


def _initialized_active() -> RouteALifecycleAdapterReference:
    adapter = RouteALifecycleAdapterReference()
    for acknowledgement in sorted(INIT_ACKS):
        adapter.acknowledge_init(acknowledgement)
    adapter.session_start(SessionStart(0, 32_768))
    return adapter


def _arrival(*, position: int, layer: int = 0, kv_head: int = 0, payload_ref: int | None = None) -> KVArrival:
    return KVArrival(
        entry_id=RouteALifecycleAdapterReference.derived_entry_id(layer=layer, kv_head=kv_head, logical_position=position),
        layer=layer,
        kv_head=kv_head,
        logical_position=position,
        payload_ref=position if payload_ref is None else payload_ref,
    )


def _fill_through(adapter: RouteALifecycleAdapterReference, *, position: int) -> None:
    for current in range(position + 1):
        adapter.kv_arrival(_arrival(position=current))


def test_init_handshake_and_generic_port_inventory_exclude_predictor_score_and_threshold():
    adapter = RouteALifecycleAdapterReference()
    with pytest.raises(LifecycleAdapterViolation, match="initialized idle"):
        adapter.session_start(SessionStart(0, 32_768))
    for acknowledgement in sorted(INIT_ACKS):
        adapter.acknowledge_init(acknowledgement)
    assert adapter.state is AdapterState.IDLE
    names = adapter.public_port_field_names()
    assert {"session_id", "entry_id", "layer", "kv_head", "logical_position", "payload_ref", "disposition", "identity", "query_position"} <= names
    assert not {"score", "threshold", "predictor", "mask_logit"} & names


def test_entry_id_is_coordinate_derived_and_arrival_is_exactly_once_and_stream_monotonic():
    adapter = _initialized_active()
    arrival = _arrival(position=0)
    adapter.kv_arrival(arrival)
    with pytest.raises(LifecycleAdapterViolation, match="exactly once"):
        adapter.kv_arrival(arrival)
    bad = KVArrival(arrival.entry_id + 1, 0, 0, 1, 1)
    with pytest.raises(LifecycleAdapterViolation, match="does not match"):
        adapter.kv_arrival(bad)


def test_ready_low_delays_generic_arrival_without_creating_or_reordering_an_entry():
    adapter = _initialized_active()
    arrival = _arrival(position=0)
    adapter.set_stall("kv_arrival", stalled=True)
    with pytest.raises(AdapterBackpressure, match="ready-low"):
        adapter.kv_arrival(arrival)
    assert adapter.authority(arrival.entry_id) is None
    adapter.set_stall("kv_arrival", stalled=False)
    adapter.kv_arrival(arrival)
    assert adapter.authority(arrival.entry_id) is AuthorityState.HOT


def test_frontend_disposition_is_stable_and_adapter_preserves_hot_drop_pending_packed_authority():
    adapter = _initialized_active()
    _fill_through(adapter, position=129)
    retain = _arrival(position=0).entry_id
    drop = _arrival(position=1).entry_id
    assert adapter.maturity_disposition(MaturityDisposition(retain, RetentionDisposition.RETAIN)) is AuthorityState.PENDING
    assert adapter.authority(retain) is AuthorityState.PENDING
    adapter.atomic_publication(entry_id=retain)
    assert adapter.authority(retain) is AuthorityState.PACKED
    assert adapter.maturity_disposition(MaturityDisposition(drop, RetentionDisposition.DROP)) is None
    assert adapter.authority(drop) is None
    with pytest.raises(LifecycleAdapterViolation, match="not live"):
        adapter.maturity_disposition(MaturityDisposition(drop, RetentionDisposition.RETAIN))


def test_maturity_cannot_precede_the_frozen_hot_window_boundary():
    adapter = _initialized_active()
    _fill_through(adapter, position=127)
    with pytest.raises(LifecycleAdapterViolation, match="hot-window"):
        adapter.maturity_disposition(MaturityDisposition(_arrival(position=0).entry_id, RetentionDisposition.RETAIN))


def test_attention_request_exposes_only_existing_route_a_sources_in_canonical_order_without_full_kv_fallback():
    adapter = _initialized_active()
    _fill_through(adapter, position=129)
    packed = _arrival(position=0).entry_id
    pending = _arrival(position=1).entry_id
    adapter.maturity_disposition(MaturityDisposition(packed, RetentionDisposition.RETAIN))
    adapter.atomic_publication(entry_id=packed)
    adapter.maturity_disposition(MaturityDisposition(pending, RetentionDisposition.RETAIN))
    plan = adapter.attention_service_request(AttentionServiceRequest(TransactionIdentity(0, 0), 0, 0, 130))
    assert plan.sources == ("hot", "pending", "packed")
    assert "full_kv" not in plan.sources
    with pytest.raises(LifecycleAdapterViolation, match="not be reallocated"):
        adapter.attention_service_request(AttentionServiceRequest(TransactionIdentity(0, 0), 0, 0, 130))
    adapter.mark_gqa_updates_committed(TransactionIdentity(0, 0))
    assert adapter.terminal_attention(TransactionIdentity(0, 0), success=True) == "success"


def test_r4_numeric_fault_has_one_top_level_consumer_only_after_gqa_updates_commit():
    adapter = _initialized_active()
    _fill_through(adapter, position=0)
    identity = TransactionIdentity(0, 0)
    adapter.attention_service_request(AttentionServiceRequest(identity, 0, 0, 1))
    with pytest.raises(LifecycleAdapterViolation, match="all GQA updates"):
        adapter.merge_numeric_fault(identity)
    adapter.mark_gqa_updates_committed(identity)
    assert adapter.merge_numeric_fault(identity) == "fault"
    with pytest.raises(LifecycleAdapterViolation, match="not live"):
        adapter.terminal_attention(identity, success=False)


def test_retirement_stops_new_work_and_ack_requires_attention_and_all_module_drains():
    adapter = _initialized_active()
    _fill_through(adapter, position=0)
    adapter.attention_service_request(AttentionServiceRequest(TransactionIdentity(1, 0), 0, 0, 1))
    retirement = SessionRetireRequest(0, TransactionIdentity(2, 1))
    adapter.session_retire(retirement)
    with pytest.raises(LifecycleAdapterViolation, match="active session"):
        adapter.kv_arrival(_arrival(position=1))
    with pytest.raises(LifecycleAdapterViolation, match="attention drain"):
        adapter.retire_ack()
    assert adapter.terminal_attention(TransactionIdentity(1, 0), success=False) == "fault"
    for acknowledgement in sorted(RETIRE_DRAIN_ACKS):
        adapter.acknowledge_drain(acknowledgement)
    assert adapter.retire_ack() == retirement
    assert adapter.state is AdapterState.RETIRED
    with pytest.raises(LifecycleAdapterViolation, match="initialized idle"):
        adapter.session_start(SessionStart(0, 32_768))


def test_destructive_reset_requires_all_init_acks_before_a_new_session():
    adapter = _initialized_active()
    adapter.destructive_reset()
    with pytest.raises(LifecycleAdapterViolation, match="initialized idle"):
        adapter.session_start(SessionStart(0, 32_768))
    for acknowledgement in sorted(INIT_ACKS):
        adapter.acknowledge_init(acknowledgement)
    adapter.session_start(SessionStart(0, 32_768))
    assert adapter.state is AdapterState.ACTIVE
