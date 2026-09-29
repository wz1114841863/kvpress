import random

import pytest

from kvpress.route_a_merge_numeric_reference import (
    CORE_FRAGMENT_BYTES,
    MERGE_HEADER_BYTES,
    QWEN_ANCHOR_HEAD_DIM,
    VALUE_FRAGMENT_COUNT,
    MergePacket,
    MergePacketHeader,
    MergePartial,
    NumericMergeFault,
    NumericMergeResult,
    NumericMergeViolation,
    SourceOrdinal,
    assert_matches_a2,
    compare_with_a2,
    merge_numeric_partials,
)


def _partial(m: float, l: float, offset: float) -> MergePartial:
    return MergePartial.present(m=m, l=l, o=tuple(offset + lane / 64.0 for lane in range(QWEN_ANCHOR_HEAD_DIM)))


def test_anchor_packet_is_128_bit_header_plus_eight_64_byte_binary32_value_fragments():
    partial = _partial(1.25, 2.5, -0.75)
    packet = MergePacket.from_partial(source="pending", consumer_id=3, partial=partial)
    assert len(packet.header.encode()) == MERGE_HEADER_BYTES
    assert len(packet.value_fragments) == VALUE_FRAGMENT_COUNT == 8
    assert all(len(fragment) == CORE_FRAGMENT_BYTES for fragment in packet.value_fragments)
    assert packet.decode_partial() == partial
    assert MergePacketHeader.decode(packet.header.encode()) == packet.header


def test_absent_packet_is_header_only_and_preserves_the_frozen_identity():
    packet = MergePacket.from_partial(source="packed", consumer_id=0, partial=None)
    assert packet.header.present is False
    assert packet.value_fragments == ()
    assert packet.decode_partial().is_absent()
    malformed = MergePacket(MergePacketHeader(0.0, 0.0, SourceOrdinal.PACKED, 0, 0, False, 0), ())
    with pytest.raises(NumericMergeViolation, match="frozen identity"):
        malformed.decode_partial()


def test_reserved_header_bits_and_fragment_count_are_rejected():
    header = MergePacket.from_partial(source="hot", consumer_id=0, partial=_partial(0.0, 1.0, 0.0)).header.encode()
    with pytest.raises(NumericMergeViolation, match="reserved"):
        MergePacketHeader.decode((int.from_bytes(header, "little") | (1 << 74)).to_bytes(16, "little"))
    with pytest.raises(NumericMergeViolation, match="fragment count"):
        MergePacketHeader(0.0, 1.0, SourceOrdinal.HOT, 0, 0, True, 0)
    with pytest.raises(NumericMergeViolation, match="source ordinal"):
        MergePacketHeader(0.0, 1.0, 3, 0, 0, True, 8)


@pytest.mark.parametrize(
    "partials",
    [
        {"hot": _partial(0.0, 1.0, 0.0)},
        {"pending": _partial(1.0, 2.0, 1.0)},
        {"packed": _partial(-1.0, 3.0, -2.0)},
        {"hot": _partial(0.0, 1.0, 0.0), "pending": _partial(1.0, 2.0, 1.0)},
        {"hot": _partial(0.0, 1.0, 0.0), "packed": _partial(-1.0, 3.0, -2.0)},
        {"pending": _partial(1.0, 2.0, 1.0), "packed": _partial(-1.0, 3.0, -2.0)},
        {"hot": _partial(0.0, 1.0, 0.0), "pending": _partial(1.0, 2.0, 1.0), "packed": _partial(-1.0, 3.0, -2.0)},
    ],
)
def test_all_nonempty_source_subsets_are_canonical_binary32_merges_that_match_a2(partials):
    result = merge_numeric_partials(partials)
    assert result.source_order == ("hot", "pending", "packed")
    assert result.partial.l > 0.0
    assert len(result.normalized()) == QWEN_ANCHOR_HEAD_DIM
    assert assert_matches_a2(partials).within_tolerance


def test_empty_source_set_and_zero_exp_sum_normalization_fail_without_a_zero_output_fallback():
    with pytest.raises(NumericMergeViolation, match="entirely empty"):
        merge_numeric_partials({"hot": None, "pending": None, "packed": None})
    with pytest.raises(NumericMergeViolation, match="l > 0"):
        NumericMergeResult(MergePartial.absent_identity(), ("hot", "pending", "packed"), ()).normalized()


def test_present_nan_and_binary32_weighted_value_overflow_are_fail_closed_numeric_faults():
    with pytest.raises(NumericMergeViolation, match="finite m/l/o"):
        MergePartial.present(m=float("nan"), l=1.0, o=(0.0,) * QWEN_ANCHOR_HEAD_DIM)
    maximum = 3.0e38
    with pytest.raises(NumericMergeFault, match="overflows binary32"):
        merge_numeric_partials({"hot": _partial(0.0, 1.0, maximum), "pending": _partial(0.0, 1.0, maximum)})


def test_a2_comparison_rejects_a_numeric_result_beyond_the_frozen_fp32_envelope():
    partials = {"hot": _partial(0.0, 1.0, 0.0), "pending": _partial(1.0, 1.0, 1.0)}
    selected = merge_numeric_partials(partials)
    bad = NumericMergeResult(
        MergePartial.present(m=selected.partial.m, l=selected.partial.l, o=tuple(value + 1.0 for value in selected.partial.o)),
        selected.source_order,
        selected.present_sources,
    )
    assert compare_with_a2(partials, observed=bad).within_tolerance is False
    with pytest.raises(NumericMergeViolation, match="does not match"):
        assert_matches_a2(partials, observed=bad)


def test_a2_comparison_rejects_a_result_labeled_with_noncanonical_source_order():
    partials = {"hot": _partial(0.0, 1.0, 0.0), "pending": _partial(1.0, 1.0, 1.0)}
    selected = merge_numeric_partials(partials)
    reordered = NumericMergeResult(selected.partial, ("pending", "hot", "packed"), selected.present_sources)
    assert compare_with_a2(partials, observed=reordered).within_tolerance is False


def test_fixed_seed_randomized_binary32_vectors_match_a2_without_claiming_reordered_equivalence():
    randomizer = random.Random(414)
    for _ in range(20):
        partials = {
            source: MergePartial.present(
                m=randomizer.uniform(-8.0, 8.0),
                l=randomizer.uniform(0.25, 4.0),
                o=tuple(randomizer.uniform(-4.0, 4.0) for _ in range(QWEN_ANCHOR_HEAD_DIM)),
            )
            for source in ("hot", "pending", "packed")
            if randomizer.choice((True, False))
        }
        if not partials:
            partials["hot"] = _partial(0.0, 1.0, 0.0)
        assert assert_matches_a2(partials).within_tolerance
