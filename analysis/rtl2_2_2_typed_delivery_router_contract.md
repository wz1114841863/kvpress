# RTL2.2.2 — registry-resolved typed delivery router

**Status:** implemented and directed tested for production write terminals.

RTL2.2.2 closes the deferred typed-resolution integration without turning the
response path into a generic demultiplexer. It migrates the production top
from the fixed RTL2.1b write-context keys to:

```text
R3 / R5 producer descriptor
  -> allocation bridge
  -> delivery-context registry
  -> existing R2 ingress / R1 boundary
  -> registry resolve
  -> typed router
  -> exact R3 or R5 terminal owner
  -> final-accept release
```

The top composes these owner-produced channels only. It neither allocates a
ref, decodes a descriptor, constructs a terminal, nor creates an authority
transition.

## Active production scope

The active terminals are deliberately limited to existing RTL2.1 behavior:

| Candidate class | Stored target kind | Stored endpoint | Existing final owner |
|---|---|---|---|
| `pack_write` | `packed_write_terminal` | R3 packed-write | `route_a_m2_p3_wrapper` |
| `descriptor_maintenance` | `descriptor_maintenance_terminal` | R5 append | `route_a_page_manager` |
| `descriptor_maintenance` | `descriptor_maintenance_terminal` | R5 reclaim | `route_a_page_manager` |

R3 provides its P3 layer/stage-generation/group descriptor. R5 append
provides descriptor operation/page/generation/line/group fields. Reclaim
provides operation `invalidate` and its actual 64-B descriptor-line reference;
it is intentionally not misrepresented as one page target.

The bridge serializes only registry allocation. Before allocation it selects
the lowest offered immutable `(arrival_ordinal, candidate_id)`; after a ref is
bound, the existing `RouteAR2WriteIngressMerge` remains the sole write-ingress
merge and R2 remains the sole eligibility/FIFO/credit/read-rotation owner.
The bridge does not change any candidate ordering fields or choose an R2 grant.

## Exact resolution and release

The registry retains the immutable candidate class, `(request_id,
incarnation)`, target kind, target generation field, and typed descriptor.
`SourceDelivery` resolves only if ref, class, and identity match a live stored
association. The router selects an endpoint only from that stored descriptor:
it never reconstructs an endpoint from R1 response data, destination, address,
or candidate ID.

Write routes additionally require `last`. Unknown, stale, wrong-class,
non-final-write, or descriptor-incompatible delivery is fail-closed and cannot
reach an endpoint. A ref is released only after that exact endpoint accepts a
final delivery. A delayed old-incarnation response/release cannot mutate a
reused association. R1 continues to own external-adapter reset-epoch stale
suppression; no new core-side epoch wire or width is selected here.

The existing R3/R5 local terminal checks and durable/publication semantics are
unchanged: routing a write terminal neither makes metadata visible nor causes
the `pending -> packed` authority handoff. The sole handoff remains the
already-closed `metadata_publish_commit` path.

## Deliberate read deferral

The typed router exposes a resolved read-fragment output for frozen
`p3_pending_read`, `s2_full_fill`, `s2_packed_fill`, and
`direct_pending_read` target kinds. The production top keeps that output
inactive in RTL2.2.2. No read producer, P3/S2 payload deposit, sidecar write,
S2 `READY`, direct-pending deliverability, source release, GQA update, or R4
work is activated. Those are explicit RTL2.3/RTL2.4 work, not a hidden router
side effect.

## Directed evidence

The no-model Chisel tests cover:

1. registry-held R3 packed-write route, ready-low stability, final acceptance,
   release, and ref reuse;
2. stale identity fail-closed behavior and exact append/reclaim endpoint
   selection;
3. bridge ordinal/id allocation selection, no R2 exposure before allocation,
   ready-low candidate stability, and producer-lane hold until release; and
4. production-top elaboration plus the existing R2/R3/R5 RTL2.1 regressions.

Run from `hardware/route_a/chisel`:

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.r2.RouteADeliveryContextRegistrySpec \
  kvpress.routea.r2.RouteADeliveryContextAllocationBridgeSpec \
  kvpress.routea.r2.RouteATypedDeliveryRouterSpec \
  kvpress.routea.r2.RouteACoreSideArbiterSpec \
  kvpress.routea.rtl2.RouteA2_1bWritePathHarnessSpec \
  kvpress.routea.rtl2.RouteA2_1cAtomicPublicationHarnessSpec \
  kvpress.routea.structural.RouteAKVSubsystemTopSpec'
```

Passing evidence is synthesizable functional-control/router evidence only. It
does not claim a complete read dataflow, endpoint payload correctness, SRAM or
HBM realization, clock/timing/throughput, PPA, model/GPU result, numerical RTL
correctness, deadlock freedom, or any new A4 DSE.
