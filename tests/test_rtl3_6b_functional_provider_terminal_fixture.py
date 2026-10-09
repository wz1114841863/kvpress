from __future__ import annotations

from kvpress.rtl3_6b_functional_provider_terminal_fixture import (
    FIXTURE_PATH,
    FIXTURE_SOURCE_PRESENCE,
    build_fixture_packets,
    build_fixture_terminals,
    encoded_fixture_fields,
    load_fixture_fields,
)


def test_static_fixture_matches_the_python_functional_provider_and_r4_oracle() -> None:
    assert load_fixture_fields(FIXTURE_PATH) == encoded_fixture_fields()


def test_fixture_covers_one_exact_packed_packet_and_success_terminal_per_gqa_consumer() -> None:
    packets = build_fixture_packets()
    terminals = build_fixture_terminals()
    assert [packet.consumer_id for packet in packets] == [0, 1, 2, 3]
    assert all(packet.source_kind.value == 2 for packet in packets)
    assert all(len(packet.packet.value_fragments) == 8 for packet in packets)
    assert [terminal.consumer_id for terminal in terminals] == [0, 1, 2, 3]
    assert all(terminal.status.value == "success" for terminal in terminals)
    assert all(terminal.normalized_value == bytes(512) for terminal in terminals)
    assert FIXTURE_SOURCE_PRESENCE == 0b100
