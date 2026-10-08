# RTL2.5.5 — Active-state scoreboard/oracle binding

**Status:** `complete_directed_cross_owner_testbench_binding`.

RTL2.5.5 closes the three remaining predeclared event records without changing
the immutable RTL2 event schema or any R5/R6 authority rule.  It binds only:

```text
R5 reclaim candidate + matching durable terminal
  -> R5 old-PageRef allocator_release observation
  -> descriptor_invalidate and page_free scoreboard events

R6 outward session_retire_ack
  -> retire_ack scoreboard event
```

`r5_allocator_release` is a post-durability observation carrier.  It carries
the old page ID/generation captured before R5 advances generation; it is not a
reclaim command, allocator grant, or added physical queue contract.  A
64-B descriptor-line invalidation can cover four pages, so per-page events are
emitted only from this named R5 carrier—not inferred from a line image or R5
state.  The test-only adapter atomically accepts its R5 carrier together with
both event records.  It similarly atomically observes R6's existing outward
acknowledgement and `retire_ack` record.

The Python adapter mirrors explicit testbench setup through the existing R5
page-manager and R6 lifecycle references.  It rejects stale generation,
wrong descriptor operation/context, free-before-invalidate, duplicate free,
and duplicate/mismatched retirement acknowledgement.  This is no-model,
no-GPU architecture-event evidence only; it makes no numeric, RTL-equivalence,
deadlock, physical-memory, cycle, timing, throughput, area, energy, or PPA
claim.

## RTL2.5.5-I integration completion

`RouteAActiveStateScoreboardIntegrationSpec` closes the carrier-to-adapter
gap without placing an observer in the production top. It has two real-owner
test compositions:

1. The real R5 page manager completes a matching reclaim descriptor terminal;
   its `allocator_release_out` feeds the adapter.  A blocked event pair holds
   the owner carrier; one accepted handshake produces matching
   `descriptor_invalidate` and `page_free` records with the old PageRef.
   Destructive reset then clears an unconsumed observation without an event.
2. The real R6 lifecycle adapter plus real fixed-membership status collector
   reaches its outward acknowledgement only after the existing drain/final-pass
   protocol. That `session_retire_ack` feeds the adapter and yields exactly one
   matching `retire_ack` record under atomic event/outward acceptance.

The fixed field trace from these two Chisel witnesses is replayed through the
Python oracle. This adds no cross-language simulator, RTL equivalence claim,
or new production interface: it verifies only the named carrier/event mapping.
