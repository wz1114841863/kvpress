from __future__ import annotations

from struct import pack

import pytest

from kvpress.route_a_merge_numeric_reference import MergePacket, MergePartial
from kvpress.rtl3_3_r4_functional_profile import DEFAULT_R4_FUNCTIONAL_PROFILE
from kvpress.rtl3_4b_functional_r4_provider import (
    FunctionalR4TerminalStatus,
    R4AcceptedPacket,
    R4FunctionalProviderNotReady,
    R4FunctionalProviderViolation,
    R4MergeWork,
    R4TransactionIdentity,
    RouteAFunctionalR4MergeProvider,
)


def _partial(source_offset: float) -> MergePartial:
    return MergePartial.present(
        m=1.0 + source_offset,
        l=2.0 + source_offset,
        o=tuple(source_offset + lane / 128.0 for lane in range(128)),
    )


def _accepted(
    *,
    identity: R4TransactionIdentity,
    source: str,
    consumer: int,
    partial: MergePartial | None,
) -> R4AcceptedPacket:
    packet = MergePacket.from_partial(source=source, consumer_id=consumer, partial=partial)
    payload = b"".join(packet.value_fragments)
    return R4AcceptedPacket(
        transaction_identity=identity,
        source_kind={"hot": 0, "pending": 1, "packed": 2}[source],
        source_instance_coordinate=17 + {"hot": 0, "pending": 1, "packed": 2}[source],
        source_generation=3,
        consumer_id=consumer,
        header=packet.header.encode(),
        value_payload=payload.ljust(512, b"\0"),
    )


@pytest.mark.parametrize("presence", range(1, 8))
def test_functional_provider_derives_each_nonempty_source_mask_from_accepted_packet_bytes(presence: int) -> None:
    identity = R4TransactionIdentity(request_id=19, incarnation=2)
    consumer = 3
    partials = {
        "hot": _partial(0.0),
        "pending": _partial(0.5),
        "packed": _partial(1.0),
    }
    provider = RouteAFunctionalR4MergeProvider()
    for source, bit in (("hot", 1), ("pending", 2), ("packed", 4)):
        if presence & bit:
            provider.accept_packet(_accepted(identity=identity, source=source, consumer=consumer, partial=partials[source]))

    terminal = provider.complete(R4MergeWork(identity, presence, consumer))
    expected_packets = {
        source: MergePacket.from_partial(
            source=source,
            consumer_id=consumer,
            partial=partials[source] if presence & bit else None,
        )
        for source, bit in (("hot", 1), ("pending", 2), ("packed", 4))
    }
    expected = DEFAULT_R4_FUNCTIONAL_PROFILE.encode_normalized_value(
        DEFAULT_R4_FUNCTIONAL_PROFILE.merge_packets(expected_packets)
    )
    assert terminal.status is FunctionalR4TerminalStatus.SUCCESS
    assert terminal.transaction_identity == identity
    assert terminal.consumer_id == consumer
    assert terminal.normalized_value == expected


def test_missing_or_stale_packet_cannot_become_a_successful_terminal() -> None:
    provider = RouteAFunctionalR4MergeProvider()
    live = R4TransactionIdentity(request_id=7, incarnation=2)
    stale = R4TransactionIdentity(request_id=7, incarnation=1)
    provider.accept_packet(_accepted(identity=stale, source="hot", consumer=1, partial=_partial(0.0)))
    with pytest.raises(R4FunctionalProviderNotReady, match="hot"):
        provider.complete(R4MergeWork(live, 1, 1))


def test_header_sideband_consumer_mismatch_fails_before_numeric_evaluation() -> None:
    identity = R4TransactionIdentity(request_id=8, incarnation=0)
    packet = _accepted(identity=identity, source="pending", consumer=2, partial=_partial(0.0))
    with pytest.raises(R4FunctionalProviderViolation, match="consumer"):
        R4AcceptedPacket(
            transaction_identity=packet.transaction_identity,
            source_kind=packet.source_kind,
            source_instance_coordinate=packet.source_instance_coordinate,
            source_generation=packet.source_generation,
            consumer_id=1,
            header=packet.header,
            value_payload=packet.value_payload,
        )


def test_nonfinite_accepted_partial_maps_to_numeric_fault_without_payload() -> None:
    identity = R4TransactionIdentity(request_id=11, incarnation=3)
    packet = _accepted(identity=identity, source="hot", consumer=0, partial=_partial(0.0))
    header = bytearray(packet.header)
    header[0:4] = pack("<I", 0x7FC00000)  # NaN m, structurally 128-bit but numerically illegal.
    provider = RouteAFunctionalR4MergeProvider()
    provider.accept_packet(
        R4AcceptedPacket(
            transaction_identity=packet.transaction_identity,
            source_kind=packet.source_kind,
            source_instance_coordinate=packet.source_instance_coordinate,
            source_generation=packet.source_generation,
            consumer_id=packet.consumer_id,
            header=bytes(header),
            value_payload=packet.value_payload,
        )
    )
    terminal = provider.complete(R4MergeWork(identity, 1, 0))
    assert terminal.status is FunctionalR4TerminalStatus.NUMERIC_FAULT
    assert terminal.normalized_value is None


def test_duplicate_packet_or_terminal_is_rejected_without_reuse() -> None:
    identity = R4TransactionIdentity(request_id=21, incarnation=0)
    packet = _accepted(identity=identity, source="packed", consumer=2, partial=_partial(0.0))
    provider = RouteAFunctionalR4MergeProvider()
    provider.accept_packet(packet)
    with pytest.raises(R4FunctionalProviderViolation, match="duplicate"):
        provider.accept_packet(packet)
    provider.complete(R4MergeWork(identity, 4, 2))
    with pytest.raises(R4FunctionalProviderViolation, match="duplicate"):
        provider.complete(R4MergeWork(identity, 4, 2))
