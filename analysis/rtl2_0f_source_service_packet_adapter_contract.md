# RTL2.0f — source-service packet-adapter closure

**Status:** source_service_packet_interface_owner_closed; behavioral_packetization_pending.

This closure resolves the production source-to-R4 boundary without granting a
source owner, scheduler, numeric unit, or top-level mux to the adapter. It
defines how the independently owned hot, direct-pending, and S2 sources expose
already-serviceable partial packets to the frozen R4 packet boundary. It does
not activate Chisel packet behavior, source payload storage, attention
arithmetic, R4 numeric merge, controller behavior, timing, throughput, PPA, or
new A4 DSE.

The machine-readable record is
[rtl2_0f_source_service_packet_adapter_manifest.json](rtl2_0f_source_service_packet_adapter_manifest.json).

## Owners and immutable plan association

route_a_source_service_packet_adapter is an integration-protocol child of the
composition-only top. It receives a copy of an already accepted R6
SourceCompletionPlan; R6 remains its sole owner. The adapter does not discover
or synthesize a plan, choose source presence, replace a source, or create an
absent-source packet. Its plan use is limited to validating a matching offered
SourceInstance and enforcing the frozen source-kind order:

    hot -> pending -> packed

The canonical order is a finite merge-semantic order, not an execution schedule
or a claim that arbitrary reordering is bitwise equivalent. No new order among
consumer IDs is selected: each source owner remains responsible for its exact
four consumer associations.

The only logical producers are:

| Source kind | Sole partial-offer producer |
|---|---|
| hot | route_a_hot_source_path |
| pending | route_a_direct_pending_endpoint_v1 |
| packed | route_a_s2_gqa_source_wrapper |

Each offer must exactly match the live R6 identity, a present source-plan bit,
and the planned SourceInstance {kind, instance_coordinate, generation}. Such
an offer is present and carries eight fragments; a source that is absent in the
plan offers no packet. The adapter never creates a source, substitutes S2 for
direct, or treats a transient P3 copy as a source.

## Exact packet inputs and outputs

An owner provides one SourceServicePartialOffer and, when present, eight
SourceServiceValueFragment records:

    SourceServicePartialOffer {
      transaction_identity, source_instance, consumer_id,
      r4_header[127:0], partial_present
    }

    SourceServiceValueFragment {
      transaction_identity, source_instance, consumer_id,
      fragment_index[2:0], last, data[511:0]
    }

The header is owner-provided structural packet content. The adapter validates
only frozen structural association: header source ordinal equals
source_instance.kind; header consumer ID equals consumer_id; merge instance is
zero; reserved bits are zero; an owner offer with partial_present=true carries
exactly fragments 0..7 with last only at 7. It neither evaluates m/l/o,
finite-ness, exponent, normalization, or arithmetic.

For each accepted offer the adapter produces an atomic R4 header plus
R4SourceInstanceSideband pair, then the exact ordered value fragments:

    adapter_to_r4_header_and_sideband:
      R4PartialHeader(identity, header) +
      R4SourceInstanceSideband(identity, SourceInstance, consumer_id)

    adapter_to_r4_value_fragment:
      R4ValueFragment(identity, fragment_index, last, data[511:0])

The header and sideband are accepted together by the existing R4 boundary.
Payload data and header bits are forwarded unchanged. The legacy SourcePartial
carrier remains inert and cannot be reinterpreted as this packet interface.

## Commit, release, fault, and stall boundary

The existing R4 ConsumerPartialCommit returns through the frozen top
demultiplexer directly to the matching source owner, not to the adapter. A
source owner emits its one SourceRelease only after four distinct matching
consumer commits; R6 alone compares releases with its nonempty plan and issues
merge_req. The adapter neither counts commits nor creates release, merge
request, numeric fault, outward terminal, authority transition, or credit
return.

A source offer with stale identity/generation, absent-plan bit, wrong source
kind/coordinate, header mismatch, duplicate consumer association, malformed
fragment sequence, or a post-reset association is rejected without R4 or
source-owner mutation. While any ingress or R4 output is valid and its peer is
not ready, all held identity, SourceInstance, header, fragment, and consumer
fields remain unchanged. Backpressure may delay only; it cannot reorder source
kinds, alter a mask/admission result, drop/duplicate a packet, or invoke
Full-KV fallback.

## Explicit exclusions

This closure does not define functional hot/direct/S2 payload storage, source
attention partial computation, P3/S2 macro behavior, R4 binary32 arithmetic,
absent-source numeric identity generation, a physical source mux, source
service rate, or a common overlap schedule. R4 uses its already frozen
source-presence contract for absent-source semantics; no adapter-generated
absent packet is authorized here.

## Validation

    .venv/bin/python tools/validate_rtl2_source_service_packet_adapter_manifest.py --help
    .venv/bin/python -m pytest tests/test_rtl2_source_service_packet_adapter_manifest.py -q

This is a pure-software executable interface contract: no model/GPU,
cycle/timing/throughput, PPA, RTL-correctness, numeric-datapath, or new A4 DSE
claim is made.
