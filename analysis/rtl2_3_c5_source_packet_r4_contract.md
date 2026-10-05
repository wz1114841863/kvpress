# RTL2.3-C5 — source packet to R4 boundary closure

**Status:** `implemented_directed_tested; limited_protocol_closure`.

C5 makes the pre-existing RTL2.0f source-service packet contract behavioral in
one narrow Chisel composition: an R6-accepted `SourceCompletionPlan` copy is
validated by `route_a_source_service_packet_adapter`, then owner-provided
structural packets are forwarded to the existing `route_a_merge_boundary`.
It exercises every nonempty source mask and all four consumer associations per
present source. It is a source-packet/R4-ingress closure, not a production
attention calculation or end-to-end Route-A transaction.

The machine-readable provenance record is
[`rtl2_3_c5_source_packet_r4_manifest.json`](rtl2_3_c5_source_packet_r4_manifest.json).

## Exact ownership and transaction boundary

`route_a_lifecycle_adapter` remains the sole owner that accepts an immutable,
nonempty `SourceCompletionPlan`. C5 adds only its lossless copy output; the
adapter cannot create, alter, or select source presence. For one copied plan,
the adapter accepts only owner-provided `SourceServicePartialOffer` and eight
`SourceServiceValueFragment` records matching:

```text
transaction identity + planned SourceInstance + consumer ID
```

The structural source order is frozen as `hot -> pending -> packed`. This is
the merge-semantic packet order, not a new scheduler policy and not a claim
that arbitrary source reorder is bitwise equivalent. Each present kind must
provide four distinct consumer packets before the adapter advances to the next
present kind. It neither consumes `ConsumerPartialCommit` nor emits
`SourceRelease`; those remain respectively the frozen R4 and source-owner/R6
responsibilities.

The three source availability observations are owner-state observations only:

| Kind | Owner | C5 observation |
|---|---|---|
| hot | `route_a_hot_source_path` | active identity and `SourceInstance` |
| pending | `route_a_direct_pending_endpoint_v1` | deliverable identity and endpoint instance |
| packed | `route_a_s2_gqa_source_wrapper` | READY state and slot/generation instance |

They do not turn any owner into an attention-partial producer. The directed
harness supplies structural offers/fragments as an explicit verification
environment, rather than pretending that hot/direct/S2 payload state computes
an `m,l,o` partial.

## R4 packet binding and fail-closed rules

For a legal offer, the adapter atomically forwards an unchanged
`R4PartialHeader` and `R4SourceInstanceSideband`, followed by exact ordered
`R4ValueFragment[0..7]`. It checks planned identity, source kind/coordinate/
generation, availability, consumer uniqueness, header source and consumer
fields, merge-instance zero, reserved header bits, present/eight-fragment
form, fragment ordinal, and final-fragment position. A bad association is
not accepted and cannot produce an R4 partial commit or mutate an owner.

The C5 directed suite covers all seven nonempty masks, all present
source/consumer packet combinations, stale availability, malformed header,
duplicate consumer rejection, and a stalled prior R4 consumer commit that
holds the next coupled header/sideband until release. It also relies on the
existing R4 boundary to consume the packet only through its coupled
header/sideband and ordered fragment protocol. This proves only the covered
structural protocol behavior; it does not introduce a numeric-fault source or
claim a source-service fault model.

## Deliberate remaining boundary

The composition-only top remains inactive for the new plan-copy and packet
ingress carriers. C5 therefore does **not** establish an authorized live top
producer, physical payload movement, hot/direct/S2 partial arithmetic,
owner-side all-four-commit release, R6 `merge_req`, R4 result/numeric-fault
terminal, retirement, or reclaim. It does not select storage macros, ports,
HBM/controller behavior, cycles, latency, throughput, area, energy, or PPA.

This is synthesizable functional protocol evidence with directed ChiselSim
coverage; it is not model/GPU evidence, a numeric-datapath correctness claim,
an RTL end-to-end correctness claim, or a new A4 DSE.

## Reproduction

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl2.RouteASourceServicePacketAdapterSpec'
```
