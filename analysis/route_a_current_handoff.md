# Route-A current handoff — RTL3 functional closure

**Status date:** 2026-10-13
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

## Current unclosed RTL3 question

The new page is correctly published and becomes packed-authoritative, but the
same production-shaped functional graph has not yet shown its **first packed
read after publication**:

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

## Next RTL3 plan — RTL3.9-C (planning target, not yet implemented)

The detailed planned wording is in `rtl2_phase_contract.md`. Work should be
split so that each step has one owner and a reviewable failure boundary:

1. **C0 — association/first-use audit.** Freeze the exact join from R3
   post-commit observation, R5 visible descriptor, and R6 accepted packed
   authority to the existing packed-read association owner. Specify the
   descriptor/page/generation/identity checks and forbid pre-publication reads.
2. **C1 — post-publication demand activation.** Activate only the owner-correct
   packed demand/lease path in the composed top. The top may compose facts but
   may not manufacture a source plan, descriptor, authority, or scheduler
   decision.
3. **C2 — functional read-to-S2 closure.** Use the existing typed R2/R1 read
   and functional-memory environment to deliver the published payload and its
   sidecar to S2. Cover ready-low, stale/mismatched identity/generation,
   terminal fault, and reset; no failed read may make S2 READY.
4. **C3 — lifecycle continuation.** Connect S2's exact source service and
   four consumer completions to the already frozen outer partial-provider/R4
   functional boundary, then to R6 terminal, release, retire, and matching
   reclaim. Do not assign `(m,l,o)` computation to an S2/direct/hot storage
   owner.
5. **C4 — event/scoreboard and cross-owner review.** Require a same-instance
   success path plus bounded legal stall, stale/mismatch, fault, and reset
   cases. Replay only accepted architectural events through the existing
   scoreboard contract. Request an RTL3 completion review only after C0--C3
   pass.

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
