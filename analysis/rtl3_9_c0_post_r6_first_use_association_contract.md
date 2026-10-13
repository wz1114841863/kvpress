# RTL3.9-C0 — post-R6 packed-page first-use association

**Status:** `implemented_functional_c0_association_baseline_validation_pending`.

## Purpose

C0 closes only the first-use authorization gap identified after RTL3.9-B3.
A packed page may begin its first read only after its one R3 publication is
committed, R5 made the matching descriptor visible, and **every** immutable
member of that page has actually crossed the existing R3-to-R6
`pending -> packed` ready/valid handshake.  It neither changes the mask,
admission, page size, M2/P3 organization, R2 scheduling, GQA mapping, or
single publication linearization boundary.

## Ownership and exact completion rule

R6 remains only the consumer of `authority_transition_in`: it creates no
ordinal table, page table, page-ready fact, or second authority.  R3 retains
the immutable group/member ledger and observes its own
`authority_transition_out.fire`, which is the actual R6 acceptance event in
the composed top.

For one committed page with `valid_records = N`, R3 emits exactly one read-only
`PostR6PackedPageReadyObservation` only after all ordinals `[0, N)` have each
been emitted from its immutable ledger and their exact matching R3-to-R6
transitions have fired.  The observation carries only the existing page
identity `(layer, stage_generation, PageRef, transaction_group_tag,
valid_records)`.  It is not a command, descriptor update, authority transfer,
or scheduler decision.

`route_a_packed_read_activation_binder` consumes the actual
`PublicationMemberObservation` stream instead of allowing the top to discard
it.  It verifies a single contiguous `(layer, tag, ordinal)` stream from zero
through `N - 1`, then accepts the R3 page-ready summary.  Only after that exact
stream and summary agree may it issue the pre-existing address-free R5
descriptor query; only an exact R5 grant may request the existing S2 lease;
only the existing four-carrier association join may form the packed demand.

This C0 baseline intentionally holds one completed page association at a time.
While it is awaiting or using its page-ready summary, it backpressures a later
member-observation stream rather than treating a later `(layer, tag)` as a
malformed continuation: that carrier has no `PageRef` and cannot safely express
two independent page ledgers.  This is conservative functional flow control,
not a change to admission, ownership, selection, scheduling, or authority
semantics.  A later closure may add an explicitly owned, bounded multi-page
association mechanism only with a separate contract.

```text
R3 committed immutable member ledger
  + each exact authority_transition_out.fire into R6
  -> one PostR6PackedPageReadyObservation
  + R6 accepted packed-present plan
  -> binder verifies member stream and page summary
  -> R5 visible descriptor query/grant -> S2 lease -> existing association
```

The top remains composition-only.  It forwards R3's member observation to the
binder and does not construct an ordinal, page, descriptor, authority,
selection, or R2 candidate.  The old post-commit observation remains available
as an observation but is no longer a first-use authorization.

## Fail-closed behavior

- Before R3's post-R6 page-ready observation, the binder issues no descriptor
  query, S2 lease request, demand, or packed-read authorization.
- Duplicate, skipped, wrong-layer, wrong-tag, or over-64 member observation
  poisons the bounded association; it cannot produce work before reset.
- A page-ready summary with an illegal count or a count/layer/tag inconsistent
  with the consumed member stream is rejected before an R5 query.
- Ready-low holds observations without changing R3 membership, R6 authority,
  page visibility, or the candidate fields.  Reset clears incomplete R3 and
  binder association state; it creates no read permission.
- R5 still alone proves descriptor visibility/liveness and S2 still alone
  grants the slot.  Existing stale/mismatch/fault checks remain mandatory for
  C1--C4 and are not converted into controller, SRAM, numeric, timing, or PPA
  claims.

## C0 validation

- `RouteAPackedReadActivationBinderSpec` checks successful full-stream
  materialization and an incomplete-member page-ready rejection with no R5
  query/demand.
- `RouteAR3R5PublicationSpec` checks that the R3 page-ready observation is
  withheld until all members fire into the R6-facing authority channel and is
  stable under ready-low.
- The normal no-model compile and live-document preflight are required before
  this slice can be marked complete.  C0 is not C1 demand activation, C2
  read-to-S2 closure, C3 source/R4 continuation, or RTL3 completion review.

## Evidence boundary

This is functional control/association evidence only.  It does not establish
an HBM controller, SRAM macro, physical descriptor store, attention MAC,
numeric/FP/exp pipeline, timing, throughput, area, energy, PPA, model/GPU
result, complete inference engine, or a new A4 DSE result.
