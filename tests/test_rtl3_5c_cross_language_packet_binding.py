from __future__ import annotations

from kvpress.rtl3_5c_partial_packet_fixture import (
    FIXTURE_PATH,
    build_fixture_packet,
    encoded_fixture_fields,
    load_fixture_fields,
)


def test_shared_fixture_is_the_exact_rtl3_5b_functional_provider_packet():
    fields = load_fixture_fields(FIXTURE_PATH)
    assert fields == encoded_fixture_fields()
    packet = build_fixture_packet()
    assert packet.packet.header.encode()[::-1].hex() == fields["header_word_hex"]
    assert [fragment[::-1].hex() for fragment in packet.packet.value_fragments] == [
        fields[f"fragment_{index}_word_hex"] for index in range(8)
    ]


def test_shared_fixture_declares_exact_immutable_identity_and_source_association():
    fields = load_fixture_fields(FIXTURE_PATH)
    assert {
        key: fields[key]
        for key in (
            "schema_version",
            "request_id",
            "incarnation",
            "source_kind",
            "source_instance_coordinate",
            "source_generation",
            "consumer_id",
        )
    } == {
        "schema_version": "kvzap-route-a-rtl3-5c-functional-partial-packet-fixture-1.0",
        "request_id": "6",
        "incarnation": "0",
        "source_kind": "0",
        "source_instance_coordinate": "10",
        "source_generation": "1",
        "consumer_id": "2",
    }
