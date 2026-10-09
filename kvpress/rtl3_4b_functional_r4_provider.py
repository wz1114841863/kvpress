"""RTL3.4-B oracle-consistent functional R4 provider.

This is a pure-software, transaction-level provider for the replaceable R4
boundary.  It consumes only complete packets that the structural Chisel R4
boundary has accepted, plus an accepted per-consumer merge work item.  It is
not Chisel arithmetic, an exp/FP microarchitecture, a timing model, or a
production-top binding.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from kvpress.route_a_merge_numeric_reference import (
    CORE_FRAGMENT_BYTES,
    MERGE_HEADER_BYTES,
    MergePacket,
    MergePacketHeader,
    NumericMergeViolation,
    SourceOrdinal,
    VALUE_FRAGMENT_COUNT,
)
from kvpress.rtl3_3_r4_functional_profile import (
    DEFAULT_R4_FUNCTIONAL_PROFILE,
    NORMALIZED_VALUE_BYTES,
    R4FunctionalProfile,
)


class R4FunctionalProviderViolation(AssertionError):
    """An accepted-packet/provider association violates RTL3.4-B."""


class R4FunctionalProviderNotReady(R4FunctionalProviderViolation):
    """A merge work item lacks its complete accepted source packet set."""


class FunctionalR4TerminalStatus(str, Enum):
    SUCCESS = "success"
    NUMERIC_FAULT = "numeric_fault"


@dataclass(frozen=True, order=True)
class R4TransactionIdentity:
    """Exact reusable request identity; no request-ID-only matching is legal."""

    request_id: int
    incarnation: int

    def __post_init__(self) -> None:
        if self.request_id < 0 or self.incarnation < 0:
            raise R4FunctionalProviderViolation("R4 identity fields must be nonnegative")


@dataclass(frozen=True)
class R4AcceptedPacket:
    """Raw full packet emitted after the Chisel structural R4 acceptance."""

    transaction_identity: R4TransactionIdentity
    source_kind: int
    source_instance_coordinate: int
    source_generation: int
    consumer_id: int
    header: bytes
    value_payload: bytes

    def __post_init__(self) -> None:
        if not 0 <= self.source_kind <= int(SourceOrdinal.PACKED):
            raise R4FunctionalProviderViolation("accepted packet has an invalid source kind")
        if self.source_instance_coordinate < 0 or self.source_generation < 0:
            raise R4FunctionalProviderViolation("accepted packet source identity must be nonnegative")
        if not 0 <= self.consumer_id < 4:
            raise R4FunctionalProviderViolation("accepted packet consumer is outside the GQA anchor")
        if len(self.header) != MERGE_HEADER_BYTES:
            raise R4FunctionalProviderViolation("accepted R4 header must be 128 bits")
        if len(self.value_payload) != NORMALIZED_VALUE_BYTES:
            raise R4FunctionalProviderViolation("accepted R4 value payload must be 4096 bits")
        # This check is structural association only.  Finite-value checks are
        # deliberately deferred until the numeric oracle runs and may map to a
        # numeric_fault terminal.
        word = int.from_bytes(self.header, byteorder="little", signed=False)
        if ((word >> 64) & 0b11) != self.source_kind:
            raise R4FunctionalProviderViolation("accepted packet header source disagrees with sideband")
        if ((word >> 66) & 0b11) != self.consumer_id:
            raise R4FunctionalProviderViolation("accepted packet header consumer disagrees with sideband")

    @property
    def source_name(self) -> str:
        return ("hot", "pending", "packed")[self.source_kind]

    def decode_packet(self) -> MergePacket:
        """Recreate the frozen packet object from the exact accepted wire bits."""
        header = MergePacketHeader.decode(self.header)
        if header.present:
            fragments = tuple(
                self.value_payload[offset : offset + CORE_FRAGMENT_BYTES]
                for offset in range(0, NORMALIZED_VALUE_BYTES, CORE_FRAGMENT_BYTES)
            )
            if len(fragments) != VALUE_FRAGMENT_COUNT:
                raise R4FunctionalProviderViolation("present accepted packet has the wrong fragment count")
        else:
            if self.value_payload != bytes(NORMALIZED_VALUE_BYTES):
                raise R4FunctionalProviderViolation("absent accepted packet must have an all-zero observation payload")
            fragments = ()
        return MergePacket(header=header, value_fragments=fragments)


@dataclass(frozen=True)
class R4MergeWork:
    """One accepted R6-to-R4 work item after RTL3.4-A association closure."""

    transaction_identity: R4TransactionIdentity
    source_presence: int
    consumer_id: int

    def __post_init__(self) -> None:
        if not 1 <= self.source_presence <= 0b111:
            raise R4FunctionalProviderViolation("R4 merge work must select a nonempty hot/pending/packed set")
        if not 0 <= self.consumer_id < 4:
            raise R4FunctionalProviderViolation("R4 merge work consumer is outside the GQA anchor")


@dataclass(frozen=True)
class FunctionalR4Terminal:
    """One per-consumer terminal for injection through the existing R4 slot."""

    transaction_identity: R4TransactionIdentity
    consumer_id: int
    status: FunctionalR4TerminalStatus
    normalized_value: bytes | None

    def __post_init__(self) -> None:
        if not 0 <= self.consumer_id < 4:
            raise R4FunctionalProviderViolation("terminal consumer is outside the GQA anchor")
        if self.status is FunctionalR4TerminalStatus.SUCCESS:
            if self.normalized_value is None or len(self.normalized_value) != NORMALIZED_VALUE_BYTES:
                raise R4FunctionalProviderViolation("successful functional terminal requires a 4096-bit payload")
        elif self.normalized_value is not None:
            raise R4FunctionalProviderViolation("numeric fault must not carry a normalized payload")


class RouteAFunctionalR4MergeProvider:
    """Stores accepted packets and invokes only the frozen RTL3.3 oracle.

    The provider has no clock, FIFO depth, service rate, or arbitration policy.
    A caller records structural-boundary packet events, then activates one R6
    work item.  Missing packets stall the functional transaction; they never
    synthesize a zero result or Full-KV fallback.
    """

    def __init__(self, *, profile: R4FunctionalProfile = DEFAULT_R4_FUNCTIONAL_PROFILE) -> None:
        self._profile = profile
        self._packets: dict[tuple[R4TransactionIdentity, int], dict[str, R4AcceptedPacket]] = {}
        self._completed: set[tuple[R4TransactionIdentity, int]] = set()

    @staticmethod
    def _key(identity: R4TransactionIdentity, consumer_id: int) -> tuple[R4TransactionIdentity, int]:
        return identity, consumer_id

    def accept_packet(self, packet: R4AcceptedPacket) -> None:
        """Record exactly one structurally accepted packet per source/key."""
        key = self._key(packet.transaction_identity, packet.consumer_id)
        if key in self._completed:
            raise R4FunctionalProviderViolation("old packet cannot mutate a terminally completed consumer")
        source_packets = self._packets.setdefault(key, {})
        if packet.source_name in source_packets:
            raise R4FunctionalProviderViolation("duplicate accepted source packet for one consumer")
        source_packets[packet.source_name] = packet

    def _packets_for_work(self, work: R4MergeWork) -> Mapping[str, MergePacket]:
        key = self._key(work.transaction_identity, work.consumer_id)
        accepted = self._packets.get(key, {})
        expected = {
            source
            for source, bit in zip(self._profile.source_order, (0b001, 0b010, 0b100), strict=True)
            if work.source_presence & bit
        }
        unexpected = set(accepted) - expected
        if unexpected:
            raise R4FunctionalProviderViolation("merge work source mask excludes an already accepted packet")
        missing = expected - set(accepted)
        if missing:
            raise R4FunctionalProviderNotReady(f"merge work lacks accepted packet(s): {sorted(missing)}")
        packets: dict[str, MergePacket] = {}
        for source in self._profile.source_order:
            if source in expected:
                packets[source] = accepted[source].decode_packet()
            else:
                # The merge-request source mask is the accepted declaration
                # that this canonical source is absent; synthesize only the
                # frozen identity packet, never a data-bearing substitute.
                packets[source] = MergePacket.from_partial(
                    source=source,
                    consumer_id=work.consumer_id,
                    partial=None,
                )
        return packets

    def complete(self, work: R4MergeWork) -> FunctionalR4Terminal:
        """Derive one success XOR numeric-fault from accepted packet bytes."""
        key = self._key(work.transaction_identity, work.consumer_id)
        if key in self._completed:
            raise R4FunctionalProviderViolation("duplicate merge work terminal")
        try:
            result = self._profile.merge_packets(self._packets_for_work(work))
            terminal = FunctionalR4Terminal(
                transaction_identity=work.transaction_identity,
                consumer_id=work.consumer_id,
                status=FunctionalR4TerminalStatus.SUCCESS,
                normalized_value=self._profile.encode_normalized_value(result),
            )
        except NumericMergeViolation:
            terminal = FunctionalR4Terminal(
                transaction_identity=work.transaction_identity,
                consumer_id=work.consumer_id,
                status=FunctionalR4TerminalStatus.NUMERIC_FAULT,
                normalized_value=None,
            )
        self._completed.add(key)
        return terminal
