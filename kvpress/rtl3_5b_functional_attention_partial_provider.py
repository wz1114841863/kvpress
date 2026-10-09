"""RTL3.5-B functional attention-partial provider.

This pure-software reference model realizes only the RTL3.5-A replaceable
partial-producer boundary.  It consumes an already-RoPE-applied Qwen-anchor
query and one source-owner K/V-plus-position lease, then emits the existing
R4 packet representation of a single `(m, l, o)` partial.  It is not Chisel
RTL, a RoPE/MAC/exp implementation choice, a scheduler, or a timing/PPA model.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, sqrt

from kvpress.route_a_merge_numeric_reference import (
    MergePacket,
    MergePartial,
    NumericMergeViolation,
    QWEN_ANCHOR_GQA_CONSUMERS,
    QWEN_ANCHOR_HEAD_DIM,
    SourceOrdinal,
)
from kvpress.rtl3_4b_functional_r4_provider import R4AcceptedPacket, R4TransactionIdentity


QWEN_ROPE_PROFILE = "qwen3_rope_applied_at_q_and_k_creation_v1"
QWEN_ATTENTION_PROFILE = "qwen3_gqa_scaled_causal_attention_v1"
QWEN_ATTENTION_SCALE = 1.0 / sqrt(QWEN_ANCHOR_HEAD_DIM)


class FunctionalPartialProviderViolation(AssertionError):
    """A proposed query/source association cannot enter the RTL3.5-B model."""


@dataclass(frozen=True)
class FunctionalAttentionQuery:
    """Frontend-owned, already-RoPE-applied Q context for one GQA consumer."""

    transaction_identity: R4TransactionIdentity
    layer: int
    kv_head: int
    consumer_id: int
    query_head: int
    query_position: int
    query: tuple[float, ...]
    rope_semantics_profile: str = QWEN_ROPE_PROFILE
    attention_semantics_profile: str = QWEN_ATTENTION_PROFILE

    def __post_init__(self) -> None:
        if not 0 <= self.layer < 36 or not 0 <= self.kv_head < 8:
            raise FunctionalPartialProviderViolation("query is outside the Qwen layer/KV-head anchor")
        if not 0 <= self.consumer_id < QWEN_ANCHOR_GQA_CONSUMERS:
            raise FunctionalPartialProviderViolation("query consumer is outside the four-head GQA anchor")
        if self.query_head != 4 * self.kv_head + self.consumer_id:
            raise FunctionalPartialProviderViolation("query head disagrees with the frozen Qwen GQA mapping")
        if self.query_position < 0:
            raise FunctionalPartialProviderViolation("query position must be nonnegative")
        if len(self.query) != QWEN_ANCHOR_HEAD_DIM or any(not isfinite(value) for value in self.query):
            raise FunctionalPartialProviderViolation("query must contain 128 finite already-RoPE-applied lanes")
        if self.rope_semantics_profile != QWEN_ROPE_PROFILE:
            raise FunctionalPartialProviderViolation("query RoPE profile differs from the frozen frontend profile")
        if self.attention_semantics_profile != QWEN_ATTENTION_PROFILE:
            raise FunctionalPartialProviderViolation("query attention profile differs from the frozen frontend profile")


@dataclass(frozen=True)
class FunctionalSourceRecord:
    """One source-owner K/V record and its exact logical key position."""

    logical_position: int
    key: tuple[float, ...]
    value: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.logical_position < 0:
            raise FunctionalPartialProviderViolation("source logical position must be nonnegative")
        if len(self.key) != QWEN_ANCHOR_HEAD_DIM or len(self.value) != QWEN_ANCHOR_HEAD_DIM:
            raise FunctionalPartialProviderViolation("source record K/V must each contain 128 lanes")
        if any(not isfinite(value) for value in self.key + self.value):
            raise FunctionalPartialProviderViolation("source record K/V must be finite")


@dataclass(frozen=True)
class FunctionalSourceLease:
    """Exact source-owner fact; it owns no partial or terminal behavior."""

    transaction_identity: R4TransactionIdentity
    layer: int
    kv_head: int
    source_kind: SourceOrdinal
    source_instance_coordinate: int
    source_generation: int
    records: tuple[FunctionalSourceRecord, ...]
    rope_semantics_profile: str = QWEN_ROPE_PROFILE

    def __post_init__(self) -> None:
        if not 0 <= self.layer < 36 or not 0 <= self.kv_head < 8:
            raise FunctionalPartialProviderViolation("source lease is outside the Qwen layer/KV-head anchor")
        if not isinstance(self.source_kind, SourceOrdinal):
            raise FunctionalPartialProviderViolation("source lease has an invalid source kind")
        if self.source_instance_coordinate < 0 or self.source_generation < 0:
            raise FunctionalPartialProviderViolation("source instance coordinate/generation must be nonnegative")
        if not self.records:
            raise FunctionalPartialProviderViolation("a selected source lease must contain at least one record")
        positions = tuple(record.logical_position for record in self.records)
        if positions != tuple(sorted(positions)) or len(set(positions)) != len(positions):
            raise FunctionalPartialProviderViolation("source lease positions must be unique and in exact increasing order")
        if self.rope_semantics_profile != QWEN_ROPE_PROFILE:
            raise FunctionalPartialProviderViolation("source key RoPE profile differs from the frozen creation-time profile")

    @property
    def source_name(self) -> str:
        return ("hot", "pending", "packed")[int(self.source_kind)]


@dataclass(frozen=True)
class FunctionalPartialPacket:
    """Existing source-packet adapter payload, represented without a transport claim."""

    transaction_identity: R4TransactionIdentity
    source_kind: SourceOrdinal
    source_instance_coordinate: int
    source_generation: int
    consumer_id: int
    packet: MergePacket

    def __post_init__(self) -> None:
        header = self.packet.header
        if not header.present or header.source_ordinal is not self.source_kind:
            raise FunctionalPartialProviderViolation("functional provider must emit one present matching-source packet")
        if header.consumer_id != self.consumer_id or len(self.packet.value_fragments) != 8:
            raise FunctionalPartialProviderViolation("functional provider packet violates the frozen consumer/fragment shape")

    def as_r4_accepted_packet(self) -> R4AcceptedPacket:
        """Reference-only conversion after the existing structural acceptance boundary.

        This helper does not bypass or replace Chisel acceptance.  It makes the
        exact packet bytes available to the existing RTL3.4-B provider tests.
        """
        return R4AcceptedPacket(
            transaction_identity=self.transaction_identity,
            source_kind=int(self.source_kind),
            source_instance_coordinate=self.source_instance_coordinate,
            source_generation=self.source_generation,
            consumer_id=self.consumer_id,
            header=self.packet.header.encode(),
            value_payload=b"".join(self.packet.value_fragments),
        )


class RouteAFunctionalAttentionPartialProvider:
    """Compute one canonical source partial from only RTL3.5-A accepted facts."""

    @staticmethod
    def _validate_association(query: FunctionalAttentionQuery, source: FunctionalSourceLease) -> None:
        if query.transaction_identity != source.transaction_identity:
            raise FunctionalPartialProviderViolation("query/source transaction identity mismatch")
        if query.layer != source.layer or query.kv_head != source.kv_head:
            raise FunctionalPartialProviderViolation("query/source layer or KV-head mismatch")
        if any(record.logical_position > query.query_position for record in source.records):
            raise FunctionalPartialProviderViolation("source record violates frozen causal visibility")

    def produce(self, *, query: FunctionalAttentionQuery, source: FunctionalSourceLease) -> FunctionalPartialPacket:
        """Return one binary32 `(m,l,o)` packet; no scheduling or state is modeled."""
        self._validate_association(query, source)
        logits = tuple(
            sum(query_lane * key_lane for query_lane, key_lane in zip(query.query, record.key, strict=True))
            * QWEN_ATTENTION_SCALE
            for record in source.records
        )
        if any(not isfinite(logit) for logit in logits):
            raise FunctionalPartialProviderViolation("attention logit is nonfinite")
        maximum = max(logits)
        weights = tuple(exp(logit - maximum) for logit in logits)
        exp_sum = sum(weights)
        if not isfinite(maximum) or not isfinite(exp_sum) or exp_sum <= 0.0:
            raise FunctionalPartialProviderViolation("functional partial is numerically invalid")
        weighted_value = tuple(
            sum(weight * record.value[lane] for weight, record in zip(weights, source.records, strict=True))
            for lane in range(QWEN_ANCHOR_HEAD_DIM)
        )
        try:
            partial = MergePartial.present(m=maximum, l=exp_sum, o=weighted_value)
            packet = MergePacket.from_partial(
                source=source.source_name,
                consumer_id=query.consumer_id,
                partial=partial,
            )
        except NumericMergeViolation as exc:
            raise FunctionalPartialProviderViolation("functional partial cannot encode the frozen R4 packet") from exc
        return FunctionalPartialPacket(
            transaction_identity=query.transaction_identity,
            source_kind=source.source_kind,
            source_instance_coordinate=source.source_instance_coordinate,
            source_generation=source.source_generation,
            consumer_id=query.consumer_id,
            packet=packet,
        )
