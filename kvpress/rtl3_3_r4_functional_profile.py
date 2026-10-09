"""RTL3.3 functional R4 profile and Python-oracle binding.

This module freezes/validates the observable packet and normalized-value
representation used by a later functional R4 provider.  It deliberately
delegates numeric semantics to the already frozen pure-software R4 reference;
it is not an exp implementation, a floating-point datapath, or RTL.
"""
from __future__ import annotations

from dataclasses import dataclass
from struct import pack, unpack
from typing import Mapping

from kvpress.route_a_architecture_reference import CANONICAL_SOURCE_ORDER
from kvpress.route_a_merge_numeric_reference import (
    BINARY32_BYTES,
    CORE_FRAGMENT_BYTES,
    MERGE_ATOL,
    MERGE_RTOL,
    QWEN_ANCHOR_GQA_CONSUMERS,
    QWEN_ANCHOR_HEAD_DIM,
    QWEN_ANCHOR_MERGE_INSTANCES,
    VALUE_FRAGMENT_COUNT,
    MergePacket,
    NumericMergeResult,
    NumericMergeViolation,
    SourceOrdinal,
    assert_matches_a2,
    merge_numeric_partials,
)


NORMALIZED_VALUE_BYTES = QWEN_ANCHOR_HEAD_DIM * BINARY32_BYTES
NORMALIZED_VALUE_BITS = NORMALIZED_VALUE_BYTES * 8
R4_PROFILE_STATUS = "complete_functional_profile_oracle_binding_pre_rtl3_4"


class R4FunctionalProfileViolation(AssertionError):
    """A packet/value violates the frozen RTL3.3 functional profile."""


@dataclass(frozen=True)
class R4FunctionalProfile:
    """Observable R4 profile; no numeric pipeline or service behavior."""

    source_order: tuple[str, ...] = CANONICAL_SOURCE_ORDER
    head_dim: int = QWEN_ANCHOR_HEAD_DIM
    consumer_count: int = QWEN_ANCHOR_GQA_CONSUMERS
    merge_instance_count: int = QWEN_ANCHOR_MERGE_INSTANCES
    value_fragment_bytes: int = CORE_FRAGMENT_BYTES
    value_fragment_count: int = VALUE_FRAGMENT_COUNT
    rtol: float = MERGE_RTOL
    atol: float = MERGE_ATOL

    def __post_init__(self) -> None:
        if self.source_order != CANONICAL_SOURCE_ORDER:
            raise R4FunctionalProfileViolation("RTL3.3 requires frozen hot -> pending -> packed source order")
        if self.head_dim != 128 or self.consumer_count != 4 or self.merge_instance_count != 1:
            raise R4FunctionalProfileViolation("RTL3.3 differs from the selected one-group Qwen anchor")
        if self.value_fragment_bytes != 64 or self.value_fragment_count != 8:
            raise R4FunctionalProfileViolation("RTL3.3 differs from the frozen 8x64-B value-fragment profile")
        if self.rtol != MERGE_RTOL or self.atol != MERGE_ATOL:
            raise R4FunctionalProfileViolation("RTL3.3 must use the frozen A2 comparison envelope")

    def decode_packets(self, packets: Mapping[str, MergePacket]) -> dict[str, object]:
        """Decode one explicit packet per canonical source, preserving order."""
        if set(packets) != set(self.source_order):
            raise R4FunctionalProfileViolation("RTL3.3 requires exactly hot, pending, and packed packet entries")
        partials: dict[str, object] = {}
        for source, ordinal in zip(self.source_order, SourceOrdinal, strict=True):
            packet = packets[source]
            if packet.header.source_ordinal is not ordinal:
                raise R4FunctionalProfileViolation("packet source ordinal disagrees with the canonical source key")
            if packet.header.consumer_id >= self.consumer_count or packet.header.merge_instance_id != 0:
                raise R4FunctionalProfileViolation("packet is outside the selected consumer/merge-instance profile")
            if packet.header.value_fragment_count not in (0, self.value_fragment_count):
                raise R4FunctionalProfileViolation("packet has an invalid value-fragment count")
            partials[source] = packet.decode_partial()
        return partials

    def merge_packets(self, packets: Mapping[str, MergePacket]) -> NumericMergeResult:
        """Run the existing canonical binary32 oracle; no reordering option exists."""
        partials = self.decode_packets(packets)
        try:
            return merge_numeric_partials(partials)
        except NumericMergeViolation:
            raise

    def assert_packets_match_a2(self, packets: Mapping[str, MergePacket]) -> NumericMergeResult:
        """Bind a canonical packet decode/result to the frozen A2 envelope."""
        partials = self.decode_packets(packets)
        result = merge_numeric_partials(partials)
        assert_matches_a2(partials, observed=result, rtol=self.rtol, atol=self.atol)
        return result

    def encode_normalized_value(self, result: NumericMergeResult) -> bytes:
        """Pack lane i into little-endian bits [32*i+31:32*i] of the 4096-b value."""
        if result.source_order != self.source_order:
            raise R4FunctionalProfileViolation("result source order is not the frozen canonical order")
        lanes = result.normalized()
        if len(lanes) != self.head_dim:
            raise R4FunctionalProfileViolation("normalized result has the wrong lane count")
        payload = b"".join(pack("<f", lane) for lane in lanes)
        if len(payload) != NORMALIZED_VALUE_BYTES:
            raise R4FunctionalProfileViolation("normalized value does not occupy 4096 bits")
        return payload

    def decode_normalized_value(self, payload: bytes) -> tuple[float, ...]:
        """Decode the profile's 128 little-endian binary32 lanes without computing them."""
        if len(payload) != NORMALIZED_VALUE_BYTES:
            raise R4FunctionalProfileViolation("normalized value must be exactly 4096 bits")
        return tuple(
            unpack("<f", payload[offset : offset + BINARY32_BYTES])[0]
            for offset in range(0, NORMALIZED_VALUE_BYTES, BINARY32_BYTES)
        )


DEFAULT_R4_FUNCTIONAL_PROFILE = R4FunctionalProfile()
