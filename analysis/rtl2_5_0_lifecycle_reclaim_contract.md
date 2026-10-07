# RTL2.5.0 — lifecycle, reset, and reclaim closure contract

**Status:** `contract_frozen; behavioral activation pending`.

## Purpose and boundary

RTL2.5.0 freezes the owner, event, ordering, reset, and bounded-progress
requirements for the final active-state closure.  It introduces no new
synthesizable behavior, top-level ingress, scoreboard emitter, or physical
implementation.  In particular, it does **not** make `descriptor_invalidate`,
`page_free`, or `retire_ack` emittable; later RTL2.5 substeps must bind each
event to its named owner-local accepted carrier before changing the active
phase overlay.

The fixed lifecycle is:

```text
active retained/publication/source/R4 work
  -> destructive reset OR one terminal outcome OR runtime retirement
  -> global drain and R5 page quiescence
  -> durable descriptor invalidation
  -> generation advance / allocator free
  -> matching retire_ack
```

This is an ordering contract, not a controller schedule, latency bound,
deadlock-freedom proof, HBM operation, or PPA claim.

## Frozen owner and event inventory

The historical RTL2 event schema remains byte-unchanged.  RTL2.5.0 copies its
three deferred reclamation records exactly as the later binding target:

| Event | Sole emitter owner | Sole carrier | Required fields | RTL2.5.0 state |
|---|---|---|---|---|
| `descriptor_invalidate` | `route_a_page_manager` (R5) | `r5_to_r2_descriptor_reclaim_candidate` | `page_ref`, `generation`, `descriptor_operation`, `delivery_context_ref` | declared only; not emittable |
| `page_free` | `route_a_page_manager` (R5) | `r5_allocator_release` | `page_ref`, `generation` | declared only; not emittable |
| `retire_ack` | `route_a_lifecycle_adapter` (R6) | `r6_to_runtime_retire_ack` | `session_id`, `request_id`, `incarnation` | declared only; not emittable |

R5 remains the sole page/descriptor/allocator owner.  R6 remains the sole
runtime lifecycle/retire-ack owner.  R2 may carry an already-created
descriptor-maintenance candidate, but cannot create invalidation, page-free,
or allocator ownership.  R1 retains response suppression; no response, top
wrapper, testbench adapter, or scoreboard may infer these events from arbitrary
internal state.

The existing R4-origin `attention_terminal` binding from RTL2.4.3 is not
rewritten.  A numeric fault remains one R6 outward terminal outcome only: it
does not permit retry, Full-KV fallback, a second terminal, publication, or
page reuse.

## Reset and stale-state rules

Destructive reset invalidates local reachability and stops new local work; it
does not erase raw HBM bytes, relax authority, or relax generation checks.
Before a new R5 initialization acknowledgement, the existing R1
`mem_init_done`/pre-reset-response suppression boundary remains mandatory.
After reset, a pre-reset request identity, old response, old source/S2/direct
association, old metadata reference, or old page generation must fail closed:
it cannot mutate state, create a source deliverable, publish metadata, produce
a terminal, invalidate a descriptor, free a page, or acknowledge retirement.

No RTL2.5.0 field chooses a new reset epoch width, request-ID width, page-ID
width, generation width, allocator mapping, credit depth, or scheduler policy.

## Retirement, drain, and reclaim ordering

On an accepted runtime retirement identity, R6 stops new arrival, maturity,
and attention acceptance.  Existing attention may reach exactly one terminal.
The one frozen global-drain predicate contains all of:

1. R1 live transactions;
2. R2 payload-arbiter and descriptor-maintenance grants;
3. R3 M2/P3 groups and stages;
4. R5 page and descriptor operations;
5. S2/GQA ownership;
6. direct-pending ownership; and
7. R4 merge state.

After that global drain, R5 applies its existing per-page quiescence predicate:
no live page reference, outstanding old-page response, S2 old-page association,
direct-pending old-page association, or metadata old-page reference.  For each
page, a descriptor invalidation must be durable before generation advance and
allocator free.  No `retire_ack` may leave R6 before all required R5 reclaim
work has completed for the matching retirement identity.

Generation wrap remains subject to the complete A3 quiescence predicate; this
contract neither weakens nor reinterprets it.

## Later RTL2.5 evidence sequence

1. **RTL2.5.1:** destructive reset injected into active owner-local states;
   stale facts fail closed and the init boundary is re-established.
2. **RTL2.5.2:** fault/terminal closure proves one terminal outcome and no
   retry or fallback across the active-state boundary.
3. **RTL2.5.3:** R6 retirement/drain collection closes the fixed membership and
   bounded fairness assumptions.
4. **RTL2.5.4:** R5 descriptor durable-invalidate before generation/free closes
   reclaim ordering and old-generation exclusion.
5. **RTL2.5.5:** only then bind the three named scoreboard events and the
   Python oracle; run directed plus fixed-seed legal-stall coverage.

Any bounded progress test may assume accepted external work and willing
consumers eventually complete.  It may conclude only that no deadlock was
observed in covered fairness-constrained interleavings; it cannot claim
deadlock freedom, latency, throughput, or service rate.

## Non-goals

RTL2.5.0 does not authorize a numeric R4 implementation, source scheduling,
mask/admission/atomic-publication change, physical HBM/SRAM/controller choice,
profiling, synthesis, timing, area, energy, PPA, model/GPU run, or new A4 DSE.
