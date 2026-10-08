# RTL2.5.4 — R5 durable invalidation before generation/free closure

**Status:** `complete_directed_r5_durable_invalidation_evidence; reclaim_event_oracle_binding_pending`.

## Scope

RTL2.5.4 closes the existing R5 descriptor-reclaim linearization point.  It
does not create a new allocator, page-reference width, descriptor layout,
reclaim scheduler, controller, top-level ingress, scoreboard emitter, or
physical memory implementation.

For an R6-authorized retirement permit, R5 alone creates the
`r5_to_r2_descriptor_reclaim_candidate` maintenance candidate.  R2/R1 may
transport that candidate and its response, but cannot create page free,
generation advance, or allocator ownership.  The single accepted terminal is
the R5 `reclaim_delivery_in` response whose candidate class/id, R1 transaction
identity, and final-fragment flag exactly match the live reclaim operation and
whose status is `OK`.

At that terminal only, for every allocated lane in the one 64-B descriptor
line, R5:

```text
durable descriptor line = FREE with next generation
    -> durableInvalidation lane fact
    -> allocator bit clear / generation advance
```

The three operations are one owner-local state transition, not separately
scheduled events.  A fault, stale candidate, wrong R1 identity, incomplete
fragment, or absent terminal cannot take this transition.  Reclaim fault holds
the relevant allocation live and prevents final R5 drain completion.

## Directed closure

`RouteAReclaimSpec` now includes a two-descriptor-line witness in addition to
its existing exact-success, fault, multi-lane, and stale-terminal cases:

1. Five published pages create a fully allocated first descriptor line and a
   live second line.
2. The matching sequence-0 terminal durably invalidates/frees only line 0;
   R5 is still not drained because line 1 remains live.
3. R5 exposes a distinct sequence-1 descriptor write for line 1.  A delayed
   sequence-0 terminal is ready-low and cannot change the live line-1 state.
4. Only the matching sequence-1 terminal yields `reclaim_complete` and the
   R5 drained fact; replay after that terminal is also ready-low.

The test observes the 512-bit descriptor write image before each matching
terminal.  Every allocated lane carries `FREE` with its incremented generation
in that durable invalidation image.  It does not claim that a testbench can
observe a physical HBM write or a physical allocator macro.

`RouteAFairReclaimIntegrationSpec` remains the adjacent R1/R2/R5/R6
fixed-seed legal-stall witness.  It exercises the named descriptor write and
response route; it is not a new HBM-controller model.

## Preserved boundaries

This closure preserves A3's complete generation-wrap quiescence requirement.
It verifies the finite reclaim-operation identity/old-terminal exclusion in
the covered test state, not generation-wrap safety for every possible external
page reference.  S2/direct/P3/M2 old-reference quiescence and the fixed R6
global drain membership remain prerequisites supplied by the existing owners.

`descriptor_invalidate` and `page_free` remain declared-only scoreboard
records.  This step does not emit either record, infer it from R5 state, or
change the historical schema/phase overlay.  RTL2.5.5 alone may bind those
events, together with `retire_ack`, to named accepted carriers and the Python
oracle.

The evidence is deterministic no-model ChiselSim.  It makes no formal
deadlock-freedom/liveness, RTL equivalence, HBM, timing, latency, throughput,
area, energy, PPA, model/GPU, numeric, or new A4 DSE claim.
