"""Static RTL3.6-B cross-language functional-provider/R4-terminal fixture.

The fixture is deliberately a *static* test resource.  Python calculates the
four packed-source partial packets and their R4 functional-oracle terminals;
the Chisel testbench replays those bytes through the already-existing packet,
R4 boundary, R6, and R5 paths.  It is not a live co-simulation bridge, a
numeric hardware implementation, or a production endpoint.
"""
from __future__ import annotations

from pathlib import Path

from kvpress.route_a_merge_numeric_reference import SourceOrdinal
from kvpress.rtl3_4b_functional_r4_provider import (
    R4MergeWork,
    R4TransactionIdentity,
    RouteAFunctionalR4MergeProvider,
)
from kvpress.rtl3_5b_functional_attention_partial_provider import (
    FunctionalAttentionQuery,
    FunctionalSourceLease,
    FunctionalSourceRecord,
    RouteAFunctionalAttentionPartialProvider,
)


FIXTURE_REQUEST_ID = 3
FIXTURE_INCARNATION = 0
FIXTURE_LAYER = 0
FIXTURE_KV_HEAD = 0
FIXTURE_SOURCE_KIND = SourceOrdinal.PACKED
FIXTURE_SOURCE_INSTANCE_COORDINATE = 0
FIXTURE_SOURCE_GENERATION = 1
FIXTURE_SOURCE_PRESENCE = 0b100
FIXTURE_PATH = Path(
    "hardware/route_a/chisel/src/test/resources/"
    "rtl3_6b_functional_provider_terminal.fixture"
)


def build_fixture_packets():
    """Return the four exact packed-source packets for the fixed GQA group."""
    identity = R4TransactionIdentity(FIXTURE_REQUEST_ID, FIXTURE_INCARNATION)
    source = FunctionalSourceLease(
        transaction_identity=identity,
        layer=FIXTURE_LAYER,
        kv_head=FIXTURE_KV_HEAD,
        source_kind=FIXTURE_SOURCE_KIND,
        source_instance_coordinate=FIXTURE_SOURCE_INSTANCE_COORDINATE,
        source_generation=FIXTURE_SOURCE_GENERATION,
        records=(
            FunctionalSourceRecord(
                logical_position=7,
                key=tuple((lane + 1) / 4096.0 for lane in range(128)),
                # A zero V vector makes the oracle result exactly representable
                # while preserving a nontrivial Q/K-derived (m, l) packet.
                value=(0.0,) * 128,
            ),
        ),
    )
    provider = RouteAFunctionalAttentionPartialProvider()
    return tuple(
        provider.produce(
            query=FunctionalAttentionQuery(
                transaction_identity=identity,
                layer=FIXTURE_LAYER,
                kv_head=FIXTURE_KV_HEAD,
                consumer_id=consumer_id,
                query_head=consumer_id,
                query_position=9,
                query=tuple(0.125 + lane / 1024.0 for lane in range(128)),
            ),
            source=source,
        )
        for consumer_id in range(4)
    )


def build_fixture_terminals():
    """Evaluate those exact accepted bytes using the frozen functional R4 oracle."""
    packets = build_fixture_packets()
    r4 = RouteAFunctionalR4MergeProvider()
    for packet in packets:
        r4.accept_packet(packet.as_r4_accepted_packet())
    identity = R4TransactionIdentity(FIXTURE_REQUEST_ID, FIXTURE_INCARNATION)
    return tuple(
        r4.complete(
            R4MergeWork(
                transaction_identity=identity,
                source_presence=FIXTURE_SOURCE_PRESENCE,
                consumer_id=consumer_id,
            )
        )
        for consumer_id in range(4)
    )


def encoded_fixture_fields() -> dict[str, str]:
    """Return dependency-free fields consumed by the test-only Chisel bridge."""
    packets = build_fixture_packets()
    terminals = build_fixture_terminals()
    fields = {
        "schema_version": "kvzap-route-a-rtl3-6b-functional-provider-terminal-fixture-1.0",
        "request_id": str(FIXTURE_REQUEST_ID),
        "incarnation": str(FIXTURE_INCARNATION),
        "layer": str(FIXTURE_LAYER),
        "kv_head": str(FIXTURE_KV_HEAD),
        "source_kind": str(int(FIXTURE_SOURCE_KIND)),
        "source_instance_coordinate": str(FIXTURE_SOURCE_INSTANCE_COORDINATE),
        "source_generation": str(FIXTURE_SOURCE_GENERATION),
        "source_presence": str(FIXTURE_SOURCE_PRESENCE),
    }
    for packet in packets:
        consumer = packet.consumer_id
        fields[f"header_consumer_{consumer}_word_hex"] = packet.packet.header.encode()[::-1].hex()
    reference_fragments = packets[0].packet.value_fragments
    assert all(packet.packet.value_fragments == reference_fragments for packet in packets)
    for index, fragment in enumerate(reference_fragments):
        fields[f"fragment_{index}_word_hex"] = fragment[::-1].hex()
    reference_result = terminals[0].normalized_value
    assert all(terminal.normalized_value == reference_result for terminal in terminals)
    assert reference_result is not None
    # The fixture encoding is a Chisel word literal; the frozen 4096-bit
    # width is supplied by the interface, so canonical zero is written as a
    # compact literal rather than 1,024 redundant hex characters.
    fields["result_word_hex"] = "0" if reference_result == bytes(512) else reference_result[::-1].hex()
    for terminal in terminals:
        assert terminal.status.value == "success"
        assert terminal.normalized_value is not None
    return fields


def load_fixture_fields(path: Path) -> dict[str, str]:
    """Parse the line-oriented frozen fixture without a runtime dependency."""
    fields: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", maxsplit=1)
        if key in fields:
            raise ValueError(f"duplicate RTL3.6-B fixture field: {key}")
        fields[key] = value
    return fields
