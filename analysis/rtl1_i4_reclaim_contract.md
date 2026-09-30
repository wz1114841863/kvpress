# RTL1-I4 — R5 descriptor invalidation, reclaim, and reuse contract

**Status:** `complete_rtl1_i4_r5_reclaim_r2_r1_r6_control_composition`.

RTL1-I4 completes only the existing R5 retirement/reclaim path. It preserves
the original KVzap mask, DROP/RETAIN disposition, 64-token page format, M2/P3
publication boundary, fixed R2 class ordering, direct-pending realization,
two S2 slots, R4 numeric boundary, and the unique R1 external-memory path.
It creates neither a descriptor-read class, a second HBM port, a descriptor
cache, retry/fallback, numeric datapath, timing/throughput/PPA claim, model or
GPU experiment, nor a new A4 DSE.

## R6 two-pass retirement drain and reclaim permit

The previous one-pass drain collection is insufficient for R5 reclaim: an R5
descriptor invalidation intentionally creates one new R2-descriptor/R1 write
*after* ordinary request work has drained. R6 therefore retains sole
retirement ownership and performs these event-level phases:

```text
retire request
  -> pre-reclaim drain: R1, R2 payload, R2 descriptor, R3, S2, direct, R4
  -> R6 ReclaimPermit
  -> R5 one-line-at-a-time descriptor invalidations
  -> final drain replay: R2 descriptor then R1, plus R5 local-empty
  -> matching R6 retire_ack
```

`ReclaimPermit` carries only the retirement `TransactionIdentity`. R6 may
offer it only when all live attention, staged lifecycle control, merge, and
terminal associations are empty and all seven non-R5 pre-reclaim drains have
been accepted. R6 must clear the collected R1/R2-descriptor facts when the
permit is accepted, suppress their premature final replay while R5 reclaim is
active, and require their fresh final facts together with R5's local-empty
fact before `retire_ack`.

This session-wide conservative order establishes the already-frozen A3
per-page quiescence set for every page considered by R5:
`no_live_page_reference`, `no_outstanding_old_page_response`,
`no_s2_old_page_association`, `no_direct_pending_old_page_association`, and
`no_metadata_old_page_reference`. It is not a per-page scoreboard, a physical
drain algorithm, or a latency guarantee.

## Line-preserving descriptor invalidation

R5 remains the sole allocator/generation owner. During retirement it selects
at most one descriptor **line** at a time. A line is the already-frozen 64-B
R1 fragment containing four 128-bit descriptor lanes. Its issue carries a
nonempty allocated-lane mask, an anchor `PageRef` for terminal association,
the selected `descriptor_line_index`, and the complete 512-bit invalidated
line image.

For every allocated lane in that line, the image writes `FREE`, zeroes all
non-generation descriptor fields, and writes the next page generation. A
non-allocated lane remains a `FREE` descriptor with its current generation.
Thus no line read, byte-mask write, local shadow descriptor table, or
unmodelled preservation mechanism is introduced. One successful durable line
terminal applies the invalidation/generation advance to precisely the
issued allocated-lane mask. This line batching is an event-level realization
of the existing per-page invalidation rule: no participant allocator bit may
become free before that terminal.

The selected logical descriptor-line index is carried through the existing
opaque R1 `address_ref`; a non-test integration must provide enough opaque
width to name every selected descriptor line. This is not an HBM base address,
controller address, burst, or physical mapping selection.

## Existing R2/R1 transport binding

Each reclaim line creates exactly two ordered existing `desc_maint_write`
`SourceCandidate`s: one R1 write request and one final 64-B write-data
fragment. Both carry the same R5-generated logical transaction identity and
opaque one-live-operation delivery context. The R2 write-data candidate may
remain ready-low until its matching R1 write request is live; this delays but
does not duplicate or reorder the line.

R2 accepts R5 descriptor candidates during retirement **only after** an
accepted R6 permit, only for the descriptor-maintenance class, and only while
one R5 reclaim line is active. All other retirement ingress remains blocked.
The R2 source delivery is routed back only to R5's matching active reclaim
line, where its final `ok` response becomes the existing durable descriptor
terminal. A fault, mismatched identity/context, wrong final marker, or stale
generation cannot free a page, advance a generation, or make R5 drained.

The A3 selected profile permits request-ID/incarnation wrap only after its
explicit complete transport quiescence predicate. I4 therefore refines the
R1 RTL implementation to permit a repeated numeric identity only after the
preceding terminal and the environment's no-old-response obligation; it does
not create a wider ID, a new outstanding bound, or a new epoch wire. The
strict-no-reuse executable profile remains a regression baseline. This
environment obligation is necessary because a wrapped identical external
response cannot be distinguished in the fixed core-side identity format.

## Required invariants and evidence

The I4 behavioral step must bind these existing requirements rather than leave
them to the implementer:

```text
allocator_free(page) -> durable_invalidate(page) && complete_quiescence(page)
generation_change(page) -> matching durable invalidation
old PageRef -> cannot match reclaimed/reused R5, S2, direct, R3, or R1 state
R6 retire_ack -> fresh post-reclaim R1/R2-descriptor/R5 drain facts
reclaim line issue -> exactly one R2 -> R1 write request/data/terminal path
ready_low -> issue/data/terminal/permit/ack state remains stable
```

Directed evidence must cover withheld pre-reclaim drain facts, withheld final
R1/R2-descriptor replay, fault/no-free, stale PageRef/generation, ordinary and
wrap generation advance, same-line multi-lane preservation, and a fixed-seed
legal-stall sequence. The tests are no-model protocol evidence only; they are
not formal proof, full-system correctness, controller behavior, or a
performance/PPA result.

## I4 disposition

The behavioral closure implements the stated R6 two-pass permit/replay, R5
one-line-at-a-time FREE/next-generation image, R2 retirement-only descriptor
ingress, and unique R1 write/request/data/terminal route. Directed ChiselSim
evidence covers success, ready-low issue stability, terminal-only free, fault
no-free, permit association, and fresh final drain replay.

It does not authorize a production payload/admission ingress, descriptor
cache, descriptor read/RMW path, physical memory realization, or a claim that
all top-inert producer paths are complete. The existing S2/direct/R3 drain
facts establish the R5 permit precondition; I4 adds no page-reference state to
those owners and therefore does not claim per-owner reused-PageRef simulation.
