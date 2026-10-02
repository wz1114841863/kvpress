# RTL2.1a — Immutable retained-group and pending-admission activation

**Status:** `implemented_and_directed_tested; limited_to_control_association`.

RTL2.1a is the first behavioral activation authorized by the RTL2.0 completion
review. It instantiates the reviewed
`route_a_admission_publication_ingress_adapter` and makes it the only owner of
the finite, one-active retained-group association. The authoritative
machine-readable record is
[rtl2_1a_retained_group_admission_manifest.json](rtl2_1a_retained_group_admission_manifest.json).

The implemented transaction is exactly:

```text
R6 RETAIN hot->pending context + authority pair
  -> collect every immutable ordinal in one <=64-record group
  -> one R5 allocation request / matching response
  -> one R3 P3 claim / matching layer acknowledgement
  -> one exact context + original hot->pending authority pair per ordinal to R3
```

`entry_id` is stored and relayed verbatim; a first-entry-plus-count span is
never reconstructed. Arrival and DROP authority edges remain local R6/hot
facts. The adapter has no authority state of its own: it only relays the
already-created `hot -> pending` transition to R3 after the claim dependency.
Thus pending remains the only authoritative residency until a later, separately
authorized `metadata_publish_commit` emits `pending -> packed`.

## Implemented boundaries

The new Chisel child is in
[`RouteAIncrementalSkeletons.scala`](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala)
and is composed by
[`RouteAKVSubsystemTop.scala`](../hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala).
The top only connects owner-provided channels; it does not create a group,
context, page reference, claim, terminal, or authority transition.

The adapter accepts R6 context and authority only atomically, fixes
layer/head/tag/valid-record count on its first member, rejects duplicate or
out-of-range ordinals, and accepts a group only after all ordinals are present.
It then holds its R5 allocation and R3 claim stable under ready-low. A response
or acknowledgement mismatch cannot advance the group. The existing one-packer
P3-ack carrier contains only `{layer, stage_generation}`; under the frozen
single-active-group anchor, layer match gates that acknowledgement locally
without inventing a tag field, reconstructing one, or copying R3's stage
generation into adapter state.

The existing R3 dual-input join is the only consumer of the relayed pair. The
adapter asserts that both context and authority fires are simultaneous; this
preserves the already frozen R3 atomic join rather than adding a second
authority-linearization point.

## Explicitly still inactive

RTL2.1a does **not** enable hot payload materialization/egress, P3 fragment or
sidecar movement, R2 candidate/FIFO/credit behavior, R1 traffic, descriptor
maintenance terminal, R5 descriptor durability, M2 member results,
`metadata_publish_commit`, packed authority, packed reads, S2/direct service,
R4, or retirement/reclaim behavior beyond existing RTL1 control.

R5 allocation and R3 reservation are logical prerequisites only. They are not
descriptor visibility, payload durability, publication, packed authority, a
physical page allocator/macro choice, or an HBM operation.

## Verification

[`RouteAAdmissionPublicationIngressAdapterSpec.scala`](../hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteAAdmissionPublicationIngressAdapterSpec.scala)
checks a non-contiguous two-member group, ready-low stability, response/ack
mismatch rejection, exact ordinal relay, paired `hot -> pending` preservation,
split input rejection, and destructive-reset stale-response exclusion.

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.rtl2.RouteAAdmissionPublicationIngressAdapterSpec'
```

This is directed synthesizable-control evidence only. It makes no model/GPU,
payload/numeric correctness, cycle/timing/throughput, PPA, physical-memory, or
new A4 DSE claim.
