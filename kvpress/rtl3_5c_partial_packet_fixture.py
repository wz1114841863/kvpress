"""Shared deterministic RTL3.5-C functional-partial packet fixture.

This module defines only a fixed host-reference input and its externally
serialized R4 packet.  It is intentionally not a live Python/Chisel bridge,
production transport, or numeric hardware model.
"""
from __future__ import annotations

from pathlib import Path

from kvpress.route_a_merge_numeric_reference import SourceOrdinal
from kvpress.rtl3_4b_functional_r4_provider import R4TransactionIdentity
from kvpress.rtl3_5b_functional_attention_partial_provider import (
    FunctionalAttentionQuery,
    FunctionalPartialPacket,
    FunctionalSourceLease,
    FunctionalSourceRecord,
    RouteAFunctionalAttentionPartialProvider,
)


FIXTURE_REQUEST_ID = 6
FIXTURE_INCARNATION = 0
FIXTURE_SOURCE_KIND = SourceOrdinal.HOT
FIXTURE_SOURCE_INSTANCE_COORDINATE = 10
FIXTURE_SOURCE_GENERATION = 1
FIXTURE_CONSUMER_ID = 2
FIXTURE_PATH = Path("hardware/route_a/chisel/src/test/resources/rtl3_5c_functional_partial_packet.fixture")


def build_fixture_packet() -> FunctionalPartialPacket:
    """Build the single frozen Python provider output used by both languages."""
    identity = R4TransactionIdentity(request_id=FIXTURE_REQUEST_ID, incarnation=FIXTURE_INCARNATION)
    query = FunctionalAttentionQuery(
        transaction_identity=identity,
        layer=2,
        kv_head=1,
        consumer_id=FIXTURE_CONSUMER_ID,
        query_head=4 + FIXTURE_CONSUMER_ID,
        query_position=9,
        query=tuple(0.25 + lane / 256.0 for lane in range(128)),
    )
    source = FunctionalSourceLease(
        transaction_identity=identity,
        layer=2,
        kv_head=1,
        source_kind=FIXTURE_SOURCE_KIND,
        source_instance_coordinate=FIXTURE_SOURCE_INSTANCE_COORDINATE,
        source_generation=FIXTURE_SOURCE_GENERATION,
        records=tuple(
            FunctionalSourceRecord(
                logical_position=position,
                key=tuple((record_index + 1) * (lane + 1) / 4096.0 for lane in range(128)),
                value=tuple(record_index + lane / 128.0 for lane in range(128)),
            )
            for record_index, position in enumerate((2, 7))
        ),
    )
    return RouteAFunctionalAttentionPartialProvider().produce(query=query, source=source)


def encoded_fixture_fields() -> dict[str, str]:
    """Return the source-independent text fields frozen in the shared fixture."""
    packet = build_fixture_packet()
    result = {
        "schema_version": "kvzap-route-a-rtl3-5c-functional-partial-packet-fixture-1.0",
        "request_id": str(FIXTURE_REQUEST_ID),
        "incarnation": str(FIXTURE_INCARNATION),
        "source_kind": str(int(FIXTURE_SOURCE_KIND)),
        "source_instance_coordinate": str(FIXTURE_SOURCE_INSTANCE_COORDINATE),
        "source_generation": str(FIXTURE_SOURCE_GENERATION),
        "consumer_id": str(FIXTURE_CONSUMER_ID),
        "header_word_hex": packet.packet.header.encode()[::-1].hex(),
    }
    result.update(
        {
            f"fragment_{index}_word_hex": fragment[::-1].hex()
            for index, fragment in enumerate(packet.packet.value_fragments)
        }
    )
    return result


def load_fixture_fields(path: Path) -> dict[str, str]:
    """Parse the deliberately dependency-free, line-oriented shared fixture."""
    fields: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", maxsplit=1)
        if key in fields:
            raise ValueError(f"duplicate RTL3.5-C fixture field: {key}")
        fields[key] = value
    return fields
