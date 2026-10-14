# Route-A current handoff — RTL3 functional closure

**Status date:** 2026-10-14
**Repository state:** `research/kvzap-latest`, implementation handoff after
`c5ccda6 rtl3: close atomic publication authority`.

This is the compact, living entry point for a new discussion or implementation
turn. It summarizes current status; it does not replace frozen evidence,
historical review records, or the normative architecture contract.

## Read first

1. [`../AGENTS.md`](../AGENTS.md): repository rules and non-negotiable evidence
   boundaries.
2. [`architecture_spec.md`](architecture_spec.md): frozen Route-A semantics,
   owners, atomicity, parameterization, and physical-evidence exclusions.
3. [`rtl2_phase_contract.md`](rtl2_phase_contract.md): detailed RTL2/RTL3 live
   phase ledger.
4. This handoff: current disposition and the next authorized planning target.
5. The most recent slice,
   [`rtl3_9_b3_atomic_publication_authority_activation_contract.md`](rtl3_9_b3_atomic_publication_authority_activation_contract.md),
   before discussing publication, descriptor visibility, or authority changes.

Use these only when the question needs the extra detail:

- [`rtl3_8_5_full_path_closure_coverage_contract.md`](rtl3_8_5_full_path_closure_coverage_contract.md)
  for the all-source-subset functional harness and its explicit limits;
- [`rtl_entry_hierarchy_owner_contract.md`](rtl_entry_hierarchy_owner_contract.md)
  and [`rtl_entry_assertion_verification_contract.md`](rtl_entry_assertion_verification_contract.md)
  for sole-owner/interface/assertion rules;
- [`architecture_gate_a_reviewer_02.md`](architecture_gate_a_reviewer_02.md)
  and [`route_a4141_accounted_net_benefit_ledger_contract.md`](route_a4141_accounted_net_benefit_ledger_contract.md)
  for the architecture/DSE evidence boundary.

## What is frozen

- Route-A preserves the original KVzap per-layer/per-KV-head token mask; Route-B
  is frozen backup work.
- A4.11--A4.14.1 research evidence is closed. A4.14.1 remains conditional,
  proxy/accounting evidence rather than measured HBM, speedup, or PPA.
- The architecture contract fixes the common S2 versus Route-A incremental
  split, M2/P3/page/sidecar semantics, legal GQA reuse, R1--R6 owners,
  `metadata_publish_commit` as the single authority linearization point, and
  no Full-KV substitution/fallback.
- Do not reopen pruning, admission, 64-token page size, M2 organization,
  P3 mapping, S2 count, GQA legality, queue/scheduler semantics, or atomic
  commit semantics while closing RTL3.

## Completed implementation phases

| Phase | Current conclusion |
|---|---|
| Gate-A / Gate-RTL0 | Passed at their declared contract/planning scope. Interface manifest, ownership, assertion, environment-assumption, and Python-oracle binding are frozen. |
| RTL1 | Control-plane hierarchy, identity/lifecycle, backpressure, reset, retirement, and verification closure complete. |
| RTL2 | Constrained functional transaction/dataflow closure complete; it is not physical-memory, numeric, or performance evidence. |
| RTL3.0--RTL3.8.5 | Replacement-owner map, functional reference environments, packed/S2 association work, partial/R4 boundaries, and directed all-source-subset coverage complete within their explicit functional/testbench boundaries. Review-03 correctly recorded no RTL3 PASS. |
| RTL3.9-A0/A1/A | R3 is the unique pending-member binding/materialization owner. It drives one exact eight-fragment `pack_read` plus position sidecar through the existing checked R2/R1 path; ingress mismatches fail closed. |
| RTL3.9-B0/B1/B2/B3 | The same immutable member reaches payload durability, R5 descriptor durability, two required M2 member round trips, R5 visibility acknowledgement, exactly one R3 publication acknowledgement, and R6 acceptance of the exact `pending -> packed` authority transition. |

The B3 witness is functional control/dataflow evidence only. It does **not**
claim physical M2/SRAM/HBM, controller or CDC behavior, numeric datapath,
frequency, bandwidth, throughput, area, energy, PPA, model/GPU evidence, or a
complete LLM inference engine.

## Current functional closure state

The same production-shaped functional graph has now shown its **first packed
read after publication**, through S2 source service, R6 terminal, and
retirement/reclaim:

```text
R3 publication committed
  + R5 visible descriptor
  + R6 accepted packed authority
    -> packed-read association/demand
    -> existing R2/R1 typed packed read + functional memory environment
    -> exact payload and sidecar deposited into S2 READY
    -> S2 source service / four consumer partial commits
    -> allowed outer functional partial provider and R4 reference boundary
    -> R6 terminal -> retirement -> R5/R6 reclaim
```

The functional memory, attention-partial producer, and R4 merge provider may
remain explicitly replaceable **outer functional environments** during RTL3.
They must not silently become an HBM controller, SRAM macro, attention MAC,
RoPE/exp/FP pipeline, or performance model.

C4-P0 has replayed the frozen event/scoreboard prerequisites from their
immutable source commits. C4-P1 has completed the fail-closed C3b event-field
provenance matrix, and C4-P2 has bound its three selected accepted carriers in
the same C3b testbench instance. C4-P3 and later remain open for event trace
replay, bounded legal stall, stale/mismatch, fault, and reset review. RTL3
itself remains open pending that separate review scope.

## RTL3.9-C0 — association/first-use audit and baseline (complete functional baseline)

C0 keeps R3 as the immutable page/member-ledger owner and treats the existing
`authority_transition_out.fire` as the actual R6 acceptance handshake.  It
does not add an R6 ordinal/page table or a second authority owner.  R3 emits a
read-only page-ready observation only after every ordinal in `[0,
valid_records)` has fired to R6; the activation binder now consumes the real
member-observation stream and requires it to match that summary before it can
query R5 or request an S2 lease.  The exact contract is
[`rtl3_9_c0_post_r6_first_use_association_contract.md`](rtl3_9_c0_post_r6_first_use_association_contract.md).

This is solely a page first-use delay.  It does not change pruning, admission,
page size, M2/P3, GQA, R2 scheduler/FIFO semantics, or R3's single atomic
publication boundary.  C1 remains separately scoped: it must activate only
the post-C0 owner-correct demand/lease path in the composed top.

C0 intentionally permits one completed page association at a time, so a later
member-observation stream is backpressured while the held page awaits/uses its
post-R6 summary.  This is conservative functional flow control because the
member carrier has no `PageRef`; it is not a second authority, admission,
selection, or scheduling mechanism.

## RTL3.9-C1 — post-publication demand activation (complete functional witness)

C1 composes one actual R6-accepted packed-present source-completion plan with
the C0 post-R6 page-ready observation, R5's visible descriptor grant, and
S2's lease through the existing binder and packed-read association owner.  It
observes one exact held registry-allocation request, without modifying the
production top or creating a top/testbench authority, descriptor, plan, or
scheduler producer.  The exact contract is
[`rtl3_9_c1_post_publication_demand_activation_contract.md`](rtl3_9_c1_post_publication_demand_activation_contract.md).

The C1 same-instance Chisel witness passed on 2026-10-14 (one test, zero
failures/errors).  It stops before registry acknowledgement, so it activates
neither C2 typed R2/R1 transport nor functional-memory read data, payload or
sidecar deposit, S2 READY, source service, partial/R4 boundary, terminal,
retirement, or reclaim.

The C0 no-model preflight, binder directed suite, and R3 all-member/ready-low
directed test passed on 2026-10-14.  B3 provenance is replayed from its frozen
commit rather than mutable live source hashes; see
[`rtl3_9_b3_atomic_publication_authority_activation_contract.md`](rtl3_9_b3_atomic_publication_authority_activation_contract.md).

The older C3 prerequisites RTL3.7-B and RTL3.8.3--RTL3.8.5 likewise replay
their hash manifests from their immutable closure commits.  Their historical
validators do not hash mutable descendant source or this living handoff.

## RTL3.9-C2 — functional read-to-S2 closure (complete functional witness)

C2 extends the same B3/C0/C1 instance through the existing allocation bridge,
sole registry, typed R2/R1 path, delivery router, packed payload/sidecar
endpoints, and S2 owner.  One exact payload and sidecar make S2 `READY`; a
stale request identity cannot do so, reset returns the slot to `EMPTY`, and a
matching payload terminal fault makes it `FAULTED` without issuing the sidecar
read.  The test-only composition neither modifies the production top nor
selects a memory/controller/numeric implementation.  The exact boundary is
[`rtl3_9_c2_functional_read_to_s2_contract.md`](rtl3_9_c2_functional_read_to_s2_contract.md).

The endpoint owners retain their established page/generation/slot/ordinal
checks.  C2 does not start source service, partial/R4 work, R6 terminal,
retirement, or reclaim.

## Remaining RTL3.9-C plan

The detailed planned wording is in `rtl2_phase_contract.md`. Work should be
split so that each step has one owner and a reviewable failure boundary:

1. **C3a — packed source service to terminal (complete).** The C2 same-instance
   witness now reaches S2 service, the named partial/R4 environments, four
   packed consumer commits, S2 release, and the sole R6 terminal. See
   [`rtl3_9_c3a_packed_source_service_terminal_contract.md`](rtl3_9_c3a_packed_source_service_terminal_contract.md).
2. **C3b — retirement and reclaim (complete).** The same C3a terminal now
   reaches runtime retirement, the production-shaped drain collector, R6's
   reclaim permit, R5's matching descriptor invalidation/page free, and one
   matching R6 retire acknowledgement. See
   [`rtl3_9_c3b_retirement_reclaim_contract.md`](rtl3_9_c3b_retirement_reclaim_contract.md).
3. **C4-P0 — frozen event/scoreboard provenance (complete; no functional C4
   claim).** The RTL2.4.3, RTL2.5.5, RTL2.6.5c, and RTL3.7-C source-hash
   records replay only at their immutable commits; they are no longer compared
   with mutable descendants. See
   [`rtl3_9_c4_p0_event_scoreboard_historical_provenance_contract.md`](rtl3_9_c4_p0_event_scoreboard_historical_provenance_contract.md).
4. **C4-P1 — C3b event provenance matrix (complete; audit only).** All
   immutable schema records have a fail-closed classification; no event is
   authorized for capture yet. See
   [`rtl3_9_c4_p1_c3b_event_provenance_matrix_contract.md`](rtl3_9_c4_p1_c3b_event_provenance_matrix_contract.md).
5. **C4-P2 — selected accepted-event binding (complete; testbench only).** A
   zero-buffer observer binds only authority transition, terminal, and retire
   acknowledgement to their same-fire event records. See
   [`rtl3_9_c4_p2_accepted_event_binding_contract.md`](rtl3_9_c4_p2_accepted_event_binding_contract.md).
6. **C4-P3+ — event/scoreboard and cross-owner review (remaining).** Replay
   the selected same-instance events, then require bounded legal stall,
   stale/mismatch, fault, and reset cases. Request an RTL3 completion review
   only after C0--C3b and all C4 sub-phases pass.

## RTL3 completion criteria

RTL3 is complete only if a reviewer can verify all of the following for the
declared functional subsystem scope:

- no exercised functional path retains a testbench ingress where a named
  internal owner is required;
- the published packed path above reaches S2, source completion, R4 terminal,
  retirement, and reclaim in one owner-correct functional instance;
- all source subsets have stated ownership and directed success/fault/stall/
  stale/reset coverage, without source-storage owners taking over attention
  computation;
- event capture/scoreboard replay observes owner-produced facts rather than
  inferred testbench defaults;
- publication is still unique, no packed read precedes visibility, each source
  releases only after four GQA consumer updates, and authoritative residency
  remains exactly one;
- any retained outer environments are named and documented as functional-only.

An RTL3 PASS means **functional subsystem closure**, not whole-model inference,
physical implementation, performance, or a Gate-B PASS.

## Overall path after RTL3

The exact successor gates must be planned and approved after the RTL3 review;
the following is the intended decision sequence, not current authorization:

```text
RTL3 completion review
  -> synthesis-realization partition/eligibility plan
  -> separate memory-interface and numeric-realization choices
  -> synthesizable control/numeric wrapper implementation and verification
  -> targeted synthesis/formal/lint and physical proxy calibration
  -> profiling of the selected realized design
  -> optimization only against measured bottlenecks
  -> timing/area/power evidence and Gate-B review
```

CACTI remains appropriate for explicitly declared SRAM proxy envelopes and
early storage-area/energy sensitivity. It cannot replace a selected macro,
controller, wire/clock, synthesis, timing, or power result. Likewise, DC is
meaningful only after the synthesis-eligible partition, clocks, black-box or
macro assumptions, and numeric/memory wrapper choices have been separately
frozen.

## New-conversation prompt seed

> Work in `/home/wz/AI/kvpress` on branch `research/kvzap-latest`. Read
> `AGENTS.md`, `analysis/architecture_spec.md`,
> `analysis/route_a_current_handoff.md`, and
> `analysis/rtl2_phase_contract.md` before editing. Current state is RTL3.9-B3
> complete: R3 atomic publication, R5 visibility, and R6 pending-to-packed
> authority are closed in a functional Chisel witness. Plan RTL3.9-C only as
> the post-publication packed first-use functional closure; do not reopen
> pruning/admission/page/scheduler/atomicity or introduce physical HBM/SRAM,
> numeric pipeline, timing, PPA, model/GPU, or new A4 DSE claims. Preserve
> frozen artifacts, run no-model preflight/tests first, update live navigation,
> and commit each completed modification batch with its source/scope.
