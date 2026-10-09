import pytest

from kvpress.route_a_merge_numeric_reference import MergePacket, MergePartial, NumericMergeViolation
from kvpress.rtl3_3_r4_functional_profile import (
    DEFAULT_R4_FUNCTIONAL_PROFILE,
    NORMALIZED_VALUE_BITS,
    R4FunctionalProfileViolation,
)


def _partial(m: float, l: float, offset: float) -> MergePartial:
    return MergePartial.present(m=m, l=l, o=tuple(offset + index / 64.0 for index in range(128)))


def _packets(partials: dict[str, MergePartial | None]) -> dict[str, MergePacket]:
    return {
        source: MergePacket.from_partial(source=source, consumer_id=2, partial=partials.get(source))
        for source in ("hot", "pending", "packed")
    }


def test_profile_binds_the_exact_rtl3_3_fixture_header_and_canonical_oracle_order():
    packets = _packets({"hot": _partial(1.25, 2.5, 0.0)})
    assert packets["hot"].header.encode().hex() == "0000a03f000020402802000000000000"
    # The explicit integer representation is the Chisel fixture word; bytes
    # remain little-endian because the profile reference owns packet encoding.
    assert int.from_bytes(packets["hot"].header.encode(), "little") == int("0000000000000228402000003fa00000", 16)
    result = DEFAULT_R4_FUNCTIONAL_PROFILE.assert_packets_match_a2(packets)
    assert result.source_order == ("hot", "pending", "packed")
    assert result.present_sources == ("hot",)


def test_profile_round_trips_the_frozen_4096_bit_little_endian_normalized_value():
    result = DEFAULT_R4_FUNCTIONAL_PROFILE.merge_packets(_packets({"pending": _partial(0.0, 2.0, -1.0)}))
    payload = DEFAULT_R4_FUNCTIONAL_PROFILE.encode_normalized_value(result)
    assert len(payload) * 8 == NORMALIZED_VALUE_BITS == 4096
    assert DEFAULT_R4_FUNCTIONAL_PROFILE.decode_normalized_value(payload) == result.normalized()


def test_profile_rejects_source_key_ordinal_disagreement_and_missing_source_entries():
    packets = _packets({"hot": _partial(0.0, 1.0, 0.0)})
    packets["hot"] = MergePacket.from_partial(source="pending", consumer_id=2, partial=_partial(0.0, 1.0, 0.0))
    with pytest.raises(R4FunctionalProfileViolation, match="ordinal"):
        DEFAULT_R4_FUNCTIONAL_PROFILE.merge_packets(packets)
    with pytest.raises(R4FunctionalProfileViolation, match="exactly"):
        DEFAULT_R4_FUNCTIONAL_PROFILE.merge_packets({"hot": packets["hot"]})


def test_profile_retains_fail_closed_empty_source_behavior_without_a_zero_result():
    with pytest.raises(NumericMergeViolation, match="entirely empty"):
        DEFAULT_R4_FUNCTIONAL_PROFILE.merge_packets(_packets({}))
