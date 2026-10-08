# RTL2.5.5 — Active-state scoreboard/oracle binding

**Status:** `implemented_directed_tested_testbench_only`.

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
