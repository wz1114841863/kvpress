# RTL2.3-C1 — shared registry-allocation composition

**Status:** implemented and directed tested.  This closure corrects the
remaining structural gap between active write producers and future Route-A
read producers: the sole delivery-context registry now has exactly one
production allocation producer,
`route_a_unified_delivery_context_allocation_bridge`.
The machine-readable companion is
[`rtl2_3_c1_shared_allocation_manifest.json`](rtl2_3_c1_shared_allocation_manifest.json).

## Exact composition

The bridge accepts these six named lanes and no others:

```text
R3 pack_read        -> pack_read
R3 direct_pending   -> direct_pending
R5 s2_packed        -> s2_packed
R3 packed_write     -> pack_write
R5 append           -> descriptor_maintenance
R5 reclaim          -> descriptor_maintenance
```

It checks the exact lane-to-class mapping before allocation.  Accepted offers
are serialized only for immutable registry binding by the existing
`(arrival_ordinal, candidate_id)` order.  A registry acknowledgement must echo
class, identity, expected fragment count, and descriptor before a lane exposes
the ref-bound candidate.  The existing class-specific read/write pre-R2 merges
then forward candidates to the two logical R2 ingress ports.  R2 remains sole
owner of candidate storage, FIFO/credit, eligibility, read rotation, and R1
grant.

The bridge owns no association table, payload, authority, source state,
response/terminal, retry, scheduler, controller, or physical-memory behavior.
An exposed lane remains unavailable until the exact typed-router release event
is observed.

## Production boundary and non-activation

The production top now uses this bridge for its existing R3/R5 write path and
instantiates the three read lanes into the shared composition graph.  Their
producer inputs are explicitly tied inactive because neither R3 nor R5 has
yet been authorized to emit a live read descriptor/candidate.  Thus C1 does
not launch a new R1 read, change R2 rotation, deposit payload/sidecar data,
make a source deliverable, or emit a scoreboard event.

## Directed evidence

`RouteAReadIngressSpec` validates read-only lane allocation/backpressure,
rejects a write-class record offered on pack-read, and validates a simultaneous
lower-ordinal write/read offer through one shared registry allocation owner.
Focused structural-top elaboration checks the replacement wiring.

Recorded result: `Test / compile` passed; three focused ingress cases passed
1/1 each; focused top elaboration passed 1/1.  Evidence is synthesizable
functional-control/association only: no model/GPU, timing, throughput, PPA,
physical-memory, numeric RTL, deadlock-freedom, or new A4 DSE claim.
