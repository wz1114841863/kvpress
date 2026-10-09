from __future__ import annotations

from math import exp, isclose, sqrt

import pytest

from kvpress.route_a_merge_numeric_reference import SourceOrdinal
from kvpress.rtl3_4b_functional_r4_provider import R4MergeWork, RouteAFunctionalR4MergeProvider, R4TransactionIdentity
from kvpress.rtl3_5b_functional_attention_partial_provider import (
    FunctionalAttentionQuery,
    FunctionalPartialProviderViolation,
    FunctionalSourceLease,
    FunctionalSourceRecord,
    QWEN_ATTENTION_SCALE,
    RouteAFunctionalAttentionPartialProvider,
)


IDENTITY = R4TransactionIdentity(request_id=5, incarnation=2)


def _query(*, consumer_id: int = 0, position: int = 9) -> FunctionalAttentionQuery:
    return FunctionalAttentionQuery(
        transaction_identity=IDENTITY,
        layer=2,
        kv_head=1,
        consumer_id=consumer_id,
        query_head=4 + consumer_id,
        query_position=position,
        query=tuple(0.25 + lane / 256.0 for lane in range(128)),
    )


def _source(kind: SourceOrdinal, *, positions: tuple[int, ...] = (2, 7)) -> FunctionalSourceLease:
    return FunctionalSourceLease(
        transaction_identity=IDENTITY,
        layer=2,
        kv_head=1,
        source_kind=kind,
        source_instance_coordinate=10 + int(kind),
        source_generation=3,
        records=tuple(
            FunctionalSourceRecord(
                logical_position=position,
                key=tuple((record_index + 1) * (lane + 1) / 4096.0 for lane in range(128)),
                value=tuple((10 * int(kind) + record_index) + lane / 128.0 for lane in range(128)),
            )
            for record_index, position in enumerate(positions)
        ),
    )


@pytest.mark.parametrize("kind", list(SourceOrdinal))
def test_provider_emits_one_present_eight_fragment_packet_with_exact_association(kind: SourceOrdinal):
    packet = RouteAFunctionalAttentionPartialProvider().produce(query=_query(consumer_id=2), source=_source(kind))
    assert packet.source_kind is kind
    assert packet.consumer_id == 2
    assert packet.packet.header.source_ordinal is kind
    assert packet.packet.header.consumer_id == 2
    assert packet.packet.header.present is True
    assert len(packet.packet.value_fragments) == 8
    assert all(len(fragment) == 64 for fragment in packet.packet.value_fragments)
    accepted = packet.as_r4_accepted_packet()
    assert accepted.transaction_identity == IDENTITY
    assert accepted.source_generation == 3
    assert accepted.decode_packet().decode_partial() == packet.packet.decode_partial()


def test_provider_matches_the_frozen_scaled_attention_partial_math():
    query = _query()
    source = _source(SourceOrdinal.HOT)
    packet = RouteAFunctionalAttentionPartialProvider().produce(query=query, source=source).packet.decode_partial()
    logits = [
        sum(q * k for q, k in zip(query.query, record.key, strict=True)) / sqrt(128.0)
        for record in source.records
    ]
    maximum = max(logits)
    weights = [exp(logit - maximum) for logit in logits]
    assert isclose(packet.m, maximum, rel_tol=1e-6, abs_tol=1e-6)
    assert isclose(packet.l, sum(weights), rel_tol=1e-6, abs_tol=1e-6)
    assert isclose(packet.o[31], sum(weight * record.value[31] for weight, record in zip(weights, source.records, strict=True)), rel_tol=1e-6, abs_tol=1e-6)
    assert QWEN_ATTENTION_SCALE == 1.0 / sqrt(128.0)


def test_three_source_packets_enter_existing_r4_functional_merge_provider_without_new_terminal_owner():
    partial_provider = RouteAFunctionalAttentionPartialProvider()
    r4_provider = RouteAFunctionalR4MergeProvider()
    for kind in SourceOrdinal:
        r4_provider.accept_packet(partial_provider.produce(query=_query(consumer_id=1), source=_source(kind)).as_r4_accepted_packet())
    terminal = r4_provider.complete(R4MergeWork(transaction_identity=IDENTITY, source_presence=0b111, consumer_id=1))
    assert terminal.status.value == "success"
    assert terminal.normalized_value is not None and len(terminal.normalized_value) == 512


def test_causal_position_violation_is_fail_closed_before_packet_production():
    with pytest.raises(FunctionalPartialProviderViolation, match="causal visibility"):
        RouteAFunctionalAttentionPartialProvider().produce(
            query=_query(position=1), source=_source(SourceOrdinal.HOT, positions=(2,))
        )


def test_unsorted_source_positions_are_rejected_before_provider_acceptance():
    with pytest.raises(FunctionalPartialProviderViolation, match="in exact increasing order"):
        _source(SourceOrdinal.HOT, positions=(7, 2))


def test_identity_and_gqa_mapping_mismatch_are_rejected_before_packet_production():
    source = _source(SourceOrdinal.PACKED)
    wrong_identity = FunctionalSourceLease(
        transaction_identity=R4TransactionIdentity(request_id=5, incarnation=3),
        layer=source.layer,
        kv_head=source.kv_head,
        source_kind=source.source_kind,
        source_instance_coordinate=source.source_instance_coordinate,
        source_generation=source.source_generation,
        records=source.records,
    )
    with pytest.raises(FunctionalPartialProviderViolation, match="identity mismatch"):
        RouteAFunctionalAttentionPartialProvider().produce(query=_query(), source=wrong_identity)
    with pytest.raises(FunctionalPartialProviderViolation, match="GQA mapping"):
        FunctionalAttentionQuery(
            transaction_identity=IDENTITY,
            layer=2,
            kv_head=1,
            consumer_id=0,
            query_head=99,
            query_position=9,
            query=(0.0,) * 128,
        )
