"""Pure-software R4 finite numeric merge contract for the Route-A anchor.

This is a transaction/reference model for the observable binary32 merge
boundary.  It is not a floating-point datapath, exp-unit implementation,
pipeline, timing model, PPA model, or RTL implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from math import exp, isfinite
from struct import pack, unpack
from typing import Mapping

from kvpress.route_a_architecture_reference import (
    CANONICAL_SOURCE_ORDER,
    ContractViolation,
    SourcePartial,
    merge_source_partials,
)


QWEN_ANCHOR_HEAD_DIM = 128
QWEN_ANCHOR_GQA_CONSUMERS = 4
QWEN_ANCHOR_MERGE_INSTANCES = 1
BINARY32_BYTES = 4
MERGE_HEADER_BYTES = 16
CORE_FRAGMENT_BYTES = 64
VALUE_FRAGMENT_COUNT = QWEN_ANCHOR_HEAD_DIM * BINARY32_BYTES // CORE_FRAGMENT_BYTES
MERGE_RTOL = 1e-4
MERGE_ATOL = 1e-5


class NumericMergeViolation(AssertionError):
    """A finite R4 merge transaction does not meet the selected contract."""


class NumericMergeFault(NumericMergeViolation):
    """A nonfinite/invalid numeric result has no selected recovery path."""


class SourceOrdinal(IntEnum):
    HOT = 0
    PENDING = 1
    PACKED = 2


_ORDINAL_BY_SOURCE = {
    "hot": SourceOrdinal.HOT,
    "pending": SourceOrdinal.PENDING,
    "packed": SourceOrdinal.PACKED,
}


def _float_bits(value: float) -> int:
    try:
        return int.from_bytes(pack("<f", value), byteorder="little", signed=False)
    except OverflowError as exc:
        raise NumericMergeFault("value cannot be represented as binary32") from exc


def _from_float_bits(bits: int) -> float:
    return unpack("<f", bits.to_bytes(BINARY32_BYTES, byteorder="little", signed=False))[0]


def _round_binary32(value: float) -> float:
    return _from_float_bits(_float_bits(value))


def _is_binary32(value: float) -> bool:
    if not isinstance(value, float):
        return False
    try:
        rounded = _from_float_bits(_float_bits(value))
        return rounded == value or (not isfinite(rounded) and not isfinite(value))
    except NumericMergeFault:
        return False


@dataclass(frozen=True)
class MergePartial:
    """One 128-lane binary32 online-softmax partial at the R4 boundary."""

    m: float
    l: float
    o: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.o) != QWEN_ANCHOR_HEAD_DIM:
            raise NumericMergeViolation("R4 partial must contain exactly 128 value lanes")
        if not _is_binary32(self.m) or not _is_binary32(self.l) or any(not _is_binary32(value) for value in self.o):
            raise NumericMergeViolation("R4 partial fields must already be binary32 values")
        if self.is_absent():
            return
        if not isfinite(self.m) or not isfinite(self.l) or self.l <= 0.0 or any(not isfinite(value) for value in self.o):
            raise NumericMergeViolation("present R4 partial must have finite m/l/o and l > 0")

    @classmethod
    def present(cls, *, m: float, l: float, o: tuple[float, ...]) -> "MergePartial":
        return cls(_round_binary32(m), _round_binary32(l), tuple(_round_binary32(value) for value in o))

    @classmethod
    def absent_identity(cls) -> "MergePartial":
        return cls(_from_float_bits(0xFF800000), 0.0, (0.0,) * QWEN_ANCHOR_HEAD_DIM)

    def is_absent(self) -> bool:
        return (
            _float_bits(self.m) == 0xFF800000
            and _float_bits(self.l) == 0
            and all(_float_bits(value) == 0 for value in self.o)
        )


@dataclass(frozen=True)
class MergePacketHeader:
    """Selected 128-bit little-endian header for one partial/result packet."""

    m: float
    l: float
    source_ordinal: SourceOrdinal
    consumer_id: int
    merge_instance_id: int
    present: bool
    value_fragment_count: int

    def __post_init__(self) -> None:
        if not _is_binary32(self.m) or not _is_binary32(self.l):
            raise NumericMergeViolation("merge header m/l must be binary32")
        if not isinstance(self.source_ordinal, SourceOrdinal):
            raise NumericMergeViolation("merge header source ordinal is invalid")
        if not 0 <= self.consumer_id < QWEN_ANCHOR_GQA_CONSUMERS:
            raise NumericMergeViolation("merge consumer is outside the four-head anchor")
        if not 0 <= self.merge_instance_id < QWEN_ANCHOR_MERGE_INSTANCES:
            raise NumericMergeViolation("merge instance is outside the selected anchor")
        expected_fragments = VALUE_FRAGMENT_COUNT if self.present else 0
        if self.value_fragment_count != expected_fragments:
            raise NumericMergeViolation("merge header fragment count is inconsistent with present/absent state")

    def encode(self) -> bytes:
        word = _float_bits(self.m)
        word |= _float_bits(self.l) << 32
        word |= int(self.source_ordinal) << 64
        word |= self.consumer_id << 66
        word |= self.merge_instance_id << 68
        word |= int(self.present) << 69
        word |= self.value_fragment_count << 70
        return word.to_bytes(MERGE_HEADER_BYTES, byteorder="little", signed=False)

    @classmethod
    def decode(cls, payload: bytes) -> "MergePacketHeader":
        if len(payload) != MERGE_HEADER_BYTES:
            raise NumericMergeViolation("merge header is not 128 bits")
        word = int.from_bytes(payload, byteorder="little", signed=False)
        if word >> 74:
            raise NumericMergeViolation("merge header reserved bits are nonzero")
        try:
            source_ordinal = SourceOrdinal((word >> 64) & 0b11)
        except ValueError as exc:
            raise NumericMergeViolation("merge header has an invalid source ordinal") from exc
        return cls(
            _from_float_bits(word & 0xFFFFFFFF),
            _from_float_bits((word >> 32) & 0xFFFFFFFF),
            source_ordinal,
            (word >> 66) & 0b11,
            (word >> 68) & 0b1,
            bool((word >> 69) & 0b1),
            (word >> 70) & 0xF,
        )


@dataclass(frozen=True)
class MergePacket:
    """Header plus zero or eight 64-B value fragments; no timing implication."""

    header: MergePacketHeader
    value_fragments: tuple[bytes, ...]

    @classmethod
    def from_partial(
        cls,
        *,
        source: str,
        consumer_id: int,
        partial: MergePartial | None,
        merge_instance_id: int = 0,
    ) -> "MergePacket":
        if source not in _ORDINAL_BY_SOURCE:
            raise NumericMergeViolation("merge packet source is outside the canonical source set")
        effective = MergePartial.absent_identity() if partial is None else partial
        present = not effective.is_absent()
        header = MergePacketHeader(
            effective.m,
            effective.l,
            _ORDINAL_BY_SOURCE[source],
            consumer_id,
            merge_instance_id,
            present,
            VALUE_FRAGMENT_COUNT if present else 0,
        )
        if not present:
            return cls(header, ())
        values = b"".join(pack("<f", value) for value in effective.o)
        fragments = tuple(values[offset : offset + CORE_FRAGMENT_BYTES] for offset in range(0, len(values), CORE_FRAGMENT_BYTES))
        return cls(header, fragments)

    def decode_partial(self) -> MergePartial:
        expected = self.header.value_fragment_count
        if len(self.value_fragments) != expected or any(len(fragment) != CORE_FRAGMENT_BYTES for fragment in self.value_fragments):
            raise NumericMergeViolation("merge packet value fragments do not match its header")
        if not self.header.present:
            if _float_bits(self.header.m) != 0xFF800000 or _float_bits(self.header.l) != 0:
                raise NumericMergeViolation("absent merge packet must encode the frozen identity")
            return MergePartial.absent_identity()
        values = b"".join(self.value_fragments)
        o = tuple(unpack("<f", values[index : index + BINARY32_BYTES])[0] for index in range(0, len(values), BINARY32_BYTES))
        return MergePartial(self.header.m, self.header.l, o)


@dataclass(frozen=True)
class NumericMergeResult:
    partial: MergePartial
    source_order: tuple[str, ...]
    present_sources: tuple[str, ...]

    def normalized(self) -> tuple[float, ...]:
        if self.partial.l <= 0.0:
            raise NumericMergeViolation("R4 normalization requires l > 0")
        return tuple(_finite_binary32(value / self.partial.l, "normalization") for value in self.partial.o)


@dataclass(frozen=True)
class A2Comparison:
    m_exact: bool
    max_abs_difference: float
    max_tolerance_ratio: float
    within_tolerance: bool


def _finite_binary32(value: float, operation: str) -> float:
    if not isfinite(value):
        raise NumericMergeFault(f"{operation} produced a nonfinite intermediate")
    try:
        rounded = _round_binary32(value)
    except NumericMergeFault as exc:
        raise NumericMergeFault(f"{operation} overflows binary32") from exc
    if not isfinite(rounded):
        raise NumericMergeFault(f"{operation} overflows binary32")
    return rounded


def merge_numeric_partials(partials: Mapping[str, MergePartial | None]) -> NumericMergeResult:
    """Merge in the frozen order, rounding each observable result to binary32.

    Exp implementation and internal precision are deliberately not selected.
    This reference evaluates the mathematical exponent with host precision and
    applies IEEE binary32 round-to-nearest/even at every R4-visible result.
    A later implementation proves conformance through ``compare_with_a2``;
    arbitrary source reordering is intentionally unavailable.
    """
    unexpected = set(partials) - set(CANONICAL_SOURCE_ORDER)
    if unexpected:
        raise NumericMergeViolation(f"unknown Route-A source(s): {sorted(unexpected)}")
    present = tuple(name for name in CANONICAL_SOURCE_ORDER if partials.get(name) is not None and not partials[name].is_absent())
    if not present:
        raise NumericMergeViolation("R4 merge has an entirely empty logical source set")
    result: MergePartial | None = None
    for name in CANONICAL_SOURCE_ORDER:
        candidate = partials.get(name)
        if candidate is None or candidate.is_absent():
            continue
        if result is None:
            result = candidate
            continue
        m = max(result.m, candidate.m)
        left_scale = exp(result.m - m)
        right_scale = exp(candidate.m - m)
        l = _finite_binary32(left_scale * result.l + right_scale * candidate.l, "merge exp_sum")
        if l <= 0.0:
            raise NumericMergeFault("merge exp_sum underflowed to zero")
        o = tuple(
            _finite_binary32(left_scale * left + right_scale * right, "merge weighted value")
            for left, right in zip(result.o, candidate.o, strict=True)
        )
        result = MergePartial(_finite_binary32(m, "merge max"), l, o)
    if result is None:
        raise NumericMergeViolation("R4 merge has an entirely empty logical source set")
    return NumericMergeResult(result, CANONICAL_SOURCE_ORDER, present)


def compare_with_a2(
    partials: Mapping[str, MergePartial | None],
    *,
    observed: NumericMergeResult | None = None,
    rtol: float = MERGE_RTOL,
    atol: float = MERGE_ATOL,
) -> A2Comparison:
    """Check the selected binary32 result against the A2 mathematical reference."""
    if rtol < 0.0 or atol < 0.0:
        raise ValueError("R4 comparison tolerances must be nonnegative")
    result = merge_numeric_partials(partials) if observed is None else observed
    expected_present = tuple(
        source
        for source in CANONICAL_SOURCE_ORDER
        if partials.get(source) is not None and not partials[source].is_absent()
    )
    if result.source_order != CANONICAL_SOURCE_ORDER or result.present_sources != expected_present:
        return A2Comparison(False, float("inf"), float("inf"), False)
    a2_inputs = {
        source: None if partials.get(source) is None or partials[source].is_absent() else SourcePartial(partials[source].m, partials[source].l, partials[source].o[0])
        for source in CANONICAL_SOURCE_ORDER
    }
    try:
        a2_first = merge_source_partials(a2_inputs).partial
        a2_values = tuple(
            merge_source_partials(
                {
                    source: None
                    if partials.get(source) is None or partials[source].is_absent()
                    else SourcePartial(partials[source].m, partials[source].l, partials[source].o[lane])
                    for source in CANONICAL_SOURCE_ORDER
                }
            ).partial.o
            for lane in range(QWEN_ANCHOR_HEAD_DIM)
        )
    except ContractViolation as exc:
        raise NumericMergeViolation(str(exc)) from exc
    observed_values = (result.partial.l, *result.partial.o)
    expected_values = (a2_first.l, *a2_values)
    differences = tuple(abs(actual - expected) for actual, expected in zip(observed_values, expected_values, strict=True))
    allowed = tuple(atol + rtol * abs(expected) for expected in expected_values)
    ratios = tuple(0.0 if difference == 0.0 and bound == 0.0 else difference / bound for difference, bound in zip(differences, allowed, strict=True))
    return A2Comparison(
        m_exact=_float_bits(result.partial.m) == _float_bits(a2_first.m),
        max_abs_difference=max(differences),
        max_tolerance_ratio=max(ratios),
        within_tolerance=_float_bits(result.partial.m) == _float_bits(a2_first.m) and all(difference <= bound for difference, bound in zip(differences, allowed, strict=True)),
    )


def assert_matches_a2(
    partials: Mapping[str, MergePartial | None],
    *,
    observed: NumericMergeResult | None = None,
    rtol: float = MERGE_RTOL,
    atol: float = MERGE_ATOL,
) -> A2Comparison:
    comparison = compare_with_a2(partials, observed=observed, rtol=rtol, atol=atol)
    if not comparison.within_tolerance:
        raise NumericMergeViolation(
            "R4 finite merge does not match the A2 mathematical reference "
            f"(m_exact={comparison.m_exact}, max_tolerance_ratio={comparison.max_tolerance_ratio})"
        )
    return comparison
