# RTL2.3.2 — incremental read allocation and pre-R2 ingress

**Status:** implemented and directed tested in an isolated integration
harness.  This closure binds the already-named Route-A incremental read
producer lanes to the existing delivery-context registry, then presents their
ref-bound candidates through a lossless pre-R2 merge.  It does not instantiate
those children in the production top or connect them to the core arbiter.

The machine-readable companion is
[`rtl2_3_2_read_ingress_manifest.json`](rtl2_3_2_read_ingress_manifest.json).

## Exact lanes and owners

Only the three Route-A incremental read lanes are in scope:

| Lane | Producer fact owner | Candidate class | Registry target kind | Later endpoint owner |
|---|---|---|---|---|
| R3 pack read | `route_a_m2_p3_wrapper` | `pack_read` | `p3_pending_read` | R3 functional P3 endpoint |
| R3 direct pending | `route_a_m2_p3_wrapper` | `direct_pending` | `direct_pending_read` | direct-pending endpoint |
| R5 packed S2 fill | `route_a_page_manager` | `s2_packed` | `s2_packed_fill` | S2 wrapper |

The common Full-KV `s2_full` lane remains outside this Route-A incremental
closure.  It is not silently fabricated, replaced, or merged with these three
lanes.

`route_a_read_delivery_context_allocation_bridge` serializes only registry
allocation.  The sole registry remains owner of opaque-reference allocation,
live association, and exact release.  After a registry acknowledgement binds a
ref, `route_a_r2_read_ingress_merge` compares the already producer-owned
`(arrival_ordinal, candidate_id)` fields to present one candidate.  It has no
FIFO, credit, cursor, R1 request, or response state.  This is the same
lossless pre-R2 composition pattern already used by the closed write ingress;
it is not a second R2 scheduler or an alteration of R2's frozen read rotation.

## Read-lane legality and release

The read bridge accepts only these exact classes with
`request_kind=coreMemoryReadRequestCode` and nonzero expected fragment count.
A write-class carrier cannot allocate a context or enter the merge.  The bridge
asserts that the registry acknowledgement exactly echoes class, identity,
fragment count, and descriptor before it exposes a ref-bound candidate.

After a future exact terminal read endpoint accepts the final response, its
existing router release event must be supplied identically to the registry and
the bridge.  Until then, the producer lane is held awaiting release and cannot
be reused.  RTL2.3.2 creates no response path, so the directed harness supplies
that exact release only to verify the association/lane lifecycle; it does not
model an R1 response or source completion.

## Deliberate non-activation

The production top has no instance of the read bridge or read merge.  No
candidate can therefore reach `route_a_core_side_arbiter`; no R1 request is
accepted, no read rotation advances, no outstanding request is reserved, and
no `request_accept` event is emitted.  The typed router's read output remains
inactive, so there is also no `fragment_deliver`, P3/S2/direct payload or
sidecar deposit, S2 `READY`, direct source deliverability, GQA commit/release,
R4, authority handoff, retirement, or Full-KV substitution.

## Directed evidence

The isolated `RouteAReadIngressSpec` contains the actual registry plus new
bridge/merge.  It verifies that a lower-ordinal direct-pending candidate is
allocated and exposed before later lanes, retains its registry-bound reference
under `ready` low, releases only through the matching association, then exposes
the next lower-ordinal remaining packed-S2 candidate.  A write-class candidate
on the named R3 pack-read lane is rejected before allocation.

Run from `hardware/route_a/chisel`:

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.rtl2.RouteAReadIngressSpec \
  kvpress.routea.rtl2.RouteAReadIssueDescriptorSpec'
```

Passing evidence is synthesizable functional-control/association evidence
only: no model/GPU, cycle, latency, throughput, PPA, physical-memory,
controller, numeric RTL, deadlock-freedom, or new A4 DSE claim.

Recorded result: JSON parse and `git diff --check` preflight passed; `Test /
compile` passed; `RouteAReadIngressSpec` passed 2/2 and the predecessor
`RouteAReadIssueDescriptorSpec` passed 3/3.  This is isolated
association/ingress evidence, not evidence that an R2 request, an R1 launch,
or a data/source-service transaction occurred.
