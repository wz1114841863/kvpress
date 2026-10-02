# RTL2.2.1 — delivery-context registry allocation and reuse contract

**Status:** implemented and directed tested as an independent, top-inert
functional association child.

RTL2.2.1 realizes only the allocation/reuse half of the frozen RTL2.0c
delivery-context registry. Its synthesizable child is
`route_a_delivery_context_registry`; its direct test is
`RouteADeliveryContextRegistrySpec`. It is not the typed delivery router and
does not activate read fragments, payload storage, S2/direct endpoint behavior,
or any new R2 producer.

## Scope and sole owner

The registry is the sole owner of a live opaque-reference association:

```text
allocate common association -> immutable opaque ref acknowledgement
    -> (future producer binds ref into SourceCandidate)
    -> (future router resolves target and endpoint accepts final event)
    -> exact release -> ref may be reused
```

It holds precisely these common, non-payload fields:

```text
candidate_class
transaction_identity = (request_id, incarnation)
target_kind
target_identity_generation
delivery_context_ref
```

The six target kinds are semantic names only:
`p3_pending_read`, `s2_full_fill`, `s2_packed_fill`,
`direct_pending_read`, `packed_write_terminal`, and
`descriptor_maintenance_terminal`. Each is accepted only with its frozen R2
candidate class. The child owns neither target-specific descriptor fields nor
payload/page/slot storage. RTL2.2.2 must supply the typed target descriptor
and replace the current RTL2.1b write-only compatibility router under a
separate review.

## Safety and reuse rules

- Allocation is blocked before the already-existing R1 initialization barrier
  (`mem_init_done`).
- A live `(candidate_class, request_id, incarnation)` cannot be allocated a
  second time, even if the offered target/generation differs.
- The acknowledged ref and common association are immutable while `valid` is
  held under downstream backpressure.
- Release succeeds only when ref and every stored common association field
  exactly match. A stale class, identity, target kind, or target generation
  is fail-closed and cannot free a live ref.
- A ref may be reused only after an exact release. A delayed old-incarnation
  release then fails against the new association.
- Destructive Chisel reset clears registry associations. No new core-side
  `reset_epoch` wire is introduced here: as frozen by R1, external-adapter
  epoch acknowledgement and stale-response suppression remain R1's
  responsibility. This child relies on that barrier rather than silently
  selecting an epoch encoding or width.

The finite association count derives solely from the existing opaque-reference
width. It is a functional lookup bound, not a selected physical FIFO depth,
SRAM/register realization, port count, service rate, or performance claim.

## Deliberate non-activation

R3/R5 still emit the reviewed fixed RTL2.1b write-context compatibility keys,
and `RouteAR2WriteDeliveryRouter` still consumes them. RTL2.2.1 does not
rewire top-level production behavior, change R2 eligibility/FIFO/credit/read
rotation, modify R1 identity handling, or alter write-terminal ownership.
That compatibility remains only until the later registry-resolved typed-router
closure; it is not reinterpreted as a final deployed encoding.

No pruning, admission, page size, M2 organization, queue/scheduler behavior,
P3 mapping, S2 count, GQA rule, atomic-publication rule, HBM/controller,
timing, throughput, PPA, model/GPU, numeric, or A4 DSE claim is added.

## Directed evidence

`RouteADeliveryContextRegistrySpec` covers:

1. initialization gating and stable allocation acknowledgement during
   ready-low backpressure;
2. class/target mismatch and exact-live duplicate rejection;
3. exact release, ref reuse after a later incarnation, delayed old-incarnation
   release rejection, and live-ref exhaustion.

Run the no-model checks from `hardware/route_a/chisel`:

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.r2.RouteADeliveryContextRegistrySpec'
```

Passing evidence supports only synthesizable functional-control association
semantics. It is not RTL endpoint correctness, a full typed-router proof,
cycle/timing/throughput evidence, a controller model, PPA evidence, or an RTL
numeric-correctness claim.
