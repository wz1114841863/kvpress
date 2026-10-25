# Route-A current handoff — RTL3 closure and measurement RTL status

**Status date:** 2026-10-25
**Repository state:** `research/kvzap-latest`, RTL3 functional-subsystem
closure reviewed at `cf9f055 docs: complete C4-D functional subsystem review`.

This is the compact, living entry point for a new discussion or implementation
turn. It summarizes current status; it does not replace frozen evidence,
historical review records, or the normative architecture contract.

## Read first

1. [`route_a_document_map.md`](route_a_document_map.md): core versus stage
   evidence classification and retrieval discipline.
2. [`../AGENTS.md`](../AGENTS.md): repository rules and non-negotiable evidence
   boundaries.
3. [`architecture_spec.md`](architecture_spec.md): frozen Route-A semantics,
   owners, atomicity, parameterization, and physical-evidence exclusions.
4. This handoff: current disposition and the next authorized planning target.
5. [`rtl2_phase_contract.md`](rtl2_phase_contract.md): detailed RTL2/RTL3 live
   phase ledger.
6. [`rtl3_9_c4_d_functional_completion_review.md`](rtl3_9_c4_d_functional_completion_review.md):
   current bounded functional-closure decision and its exclusions.
7. [`synthesis_realization_partition.md`](synthesis_realization_partition.md):
   approved SRP scope, classification axes, gates, and stop criteria.
8. [`measurement_boundary_selection.md`](measurement_boundary_selection.md):
   MBR.0 human-approved candidate measurement cut; read
   [`measurement_baseline_fairness_plan.md`](measurement_baseline_fairness_plan.md)
   next for MBR.1's approved paired Full-KV fairness plan, then
   [`full_kv_baseline_path_audit_20261016.md`](full_kv_baseline_path_audit_20261016.md)
   for the completed W0/MR-1A bounded measurement-RTL evidence and the
   separately proposed MR-1B direct-pending contract correction. Read
   [`mr1b_direct_pending_cross_owner_contract_proposal.md`](mr1b_direct_pending_cross_owner_contract_proposal.md)
   only when working on that gap. Neither is a selected
   synthesis top.

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
- The ignored A4.14.1 report/input closure is now locally recoverable and
  passing its original read-only preflight; see
  [`a4141_local_provenance_recovery_20261016.md`](a4141_local_provenance_recovery_20261016.md).
  This removes an availability blocker only, not omitted-cost, physical, or
  net-benefit boundaries.
- The architecture contract fixes the common S2 versus Route-A incremental
  split, M2/P3/page/sidecar semantics, legal GQA reuse, R1--R6 owners,
  `metadata_publish_commit` as the single authority linearization point, and
  no Full-KV substitution/fallback.
- Do not reopen pruning, admission, 64-token page size, M2 organization,
  P3 mapping, S2 count, GQA legality, queue/scheduler semantics, or atomic
  commit semantics while planning a separately authorized successor stage.

## Completed implementation phases

| Phase | Current conclusion |
|---|---|
| Gate-A / Gate-RTL0 | Passed at their declared contract/planning scope. Interface manifest, ownership, assertion, environment-assumption, and Python-oracle binding are frozen. |
| RTL1 | Control-plane hierarchy, identity/lifecycle, backpressure, reset, retirement, and verification closure complete. |
| RTL2 | Constrained functional transaction/dataflow closure complete; it is not physical-memory, numeric, or performance evidence. |
| RTL3.0--RTL3.8.5 | Replacement-owner map, functional reference environments, packed/S2 association work, partial/R4 boundaries, and directed all-source-subset coverage complete within their explicit functional/testbench boundaries. Review-03 correctly recorded no RTL3 PASS. |
| RTL3.9-A0/A1/A | R3 is the unique pending-member binding/materialization owner. It drives one exact eight-fragment `pack_read` plus position sidecar through the existing checked R2/R1 path; ingress mismatches fail closed. |
| RTL3.9-B0/B1/B2/B3 | The same immutable member reaches payload durability, R5 descriptor durability, two required M2 member round trips, R5 visibility acknowledgement, exactly one R3 publication acknowledgement, and R6 acceptance of the exact `pending -> packed` authority transition. |
| RTL3.9-C0--C4-D | First owner-correct packed read, S2 READY/source service, terminal/reclaim, accepted-event replay, negative-event coverage, and bounded functional-subsystem review complete. |

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
immutable source commits. C4-P1 completed the fail-closed C3b event-field
provenance matrix, and C4-P2 is its narrow accepted-carrier precursor. C4-A
binds the eligible R5 old-PageRef/page-free release while keeping
descriptor-invalidate fail-closed because two required fields are not on its
accepted R5 carrier. C4-B success/replay under bounded legal backpressure,
C4-C stale/mismatch, numeric-fault, and reset witnesses, and C4-D's bounded
functional-subsystem completion review are complete. RTL3 functional-subsystem
closure is complete; the next work requires separate authorization and remains
outside physical, numeric, and PPA scope.

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
5. **C4-P2 — narrow C4-A accepted-event precursor (complete; testbench
   only).** A
   zero-buffer observer binds only authority transition, terminal, and retire
   acknowledgement to their same-fire event records. See
   [`rtl3_9_c4_p2_accepted_event_binding_contract.md`](rtl3_9_c4_p2_accepted_event_binding_contract.md).
6. **C4-A — event-capture precondition audit (complete; no new capture).**
   Terminal, page-free, and retire-ack have complete accepted carriers;
   descriptor-invalidate remains excluded because its required fields are not
   co-carried. See
   [`rtl3_9_c4_a_precondition_audit_contract.md`](rtl3_9_c4_a_precondition_audit_contract.md).
7. **C4-A — eligible event capture (complete; testbench only).** The R5
   page-free release is now a zero-buffer, same-fire observation; terminal and
   retire remain on their P2 bindings. Descriptor-invalidate remains excluded.
   See
   [`rtl3_9_c4_a_eligible_event_capture_contract.md`](rtl3_9_c4_a_eligible_event_capture_contract.md).
8. **C4-B — event replay and bounded legal backpressure (complete;
   testbench only).** The host replay oracle records each selected event after
   its actual handshake and verifies exactly-once order under two-cycle legal
   stalls. See
   [`rtl3_9_c4_b_event_replay_contract.md`](rtl3_9_c4_b_event_replay_contract.md).
9. **C4-C — negative-event precondition audit (complete; no new witness).**
   The existing C3b harness has exact stale/mismatch, R4 numeric-fault, reset,
   and C4-event ingress/observations. Its case matrix records legal prefixes
   and forbidden suffixes. See
   [`rtl3_9_c4_c_precondition_audit_contract.md`](rtl3_9_c4_c_precondition_audit_contract.md).
10. **C4-C — stale/mismatch, numeric-fault, and reset witness (complete).**
    The narrow host-only same-instance witness passed all three directed
    Chisel tests. Its C4 event records are appended only after actual
    handshakes. See
    [`rtl3_9_c4_c_negative_event_witness_contract.md`](rtl3_9_c4_c_negative_event_witness_contract.md).
11. **C4-D — validation and bounded completion review (complete).** Its
    review reconciled C0--C3b and C4-A/B/C without changing an owner or
    datapath; C3b success/replay and all C4-C negative witnesses passed. See
    [`rtl3_9_c4_d_functional_completion_review.md`](rtl3_9_c4_d_functional_completion_review.md).

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

C4-D completed this bounded review on 2026-10-15. The reviewed result is
functional-subsystem closure only.  SRP.0 provenance/source inventory and the
SRP.1-R revised partition proposal passed human review with minor documentary
corrections; SRP.2 source/toolchain eligibility, SRP.3 realization-
requirements decision planning, SRP.4 differential-cost evidence planning,
and SRP.5 completion review are complete at their declared planning scopes.
SRP conditionally passes only to a separately authorized realization-choice
planning review. MBR.0 has begun that bounded `top_future_synthesis_boundary`
planning review, passed its human candidate-cut/BOM review, and authorized
MBR.1.  MBR.1 and MBR.1-A passed external technical review with minor
corrections and received explicit user approval. The targeted Full-KV audit
initially found all three legal baseline path segments absent; W0 has since
completed its bounded dual-DUT functional contour, and MR-1A has completed
its approved Route-A-hot and Full-KV common lifecycle/status integration.
MR-1B direct-pending source-plan association has a contract proposal awaiting
user approval; no MBR review repeats. Independent MR-2 array-only storage
boundary work may proceed without resolving that association. MR-2-P3 has
isolated and directed-tested the P3 functional array interior; see
[`mr2_p3_array_boundary_contract.md`](mr2_p3_array_boundary_contract.md).
MR-2-S2 has isolated and directed-tested the independent S2 payload/sidecar
array-only interior; see
[`mr2_s2_array_boundary_contract.md`](mr2_s2_array_boundary_contract.md).
None of these records selects a
future top or begins physical realization work. See
[`synthesis_realization_partition.md`](synthesis_realization_partition.md)
and its manifest.  No
physical/numeric realization choice, wrapper implementation, synthesis, or
PPA work is authorized by that planning approval.

## Overall path after RTL3

The exact successor gates must be planned and approved after the RTL3 review;
the following is the intended decision sequence, not current authorization:

```text
RTL3 completion review
  -> SRP.0 provenance/source inventory + SRP.1 partition proposal
  -> human review of minimum paper-relevant boundary
  -> SRP.2 source/toolchain eligibility
  -> SRP.3 realization requirements and decision planning
  -> SRP.4 differential-cost evidence plan + SRP.5 completion review
  -> MBR.0 candidate measurement-boundary review + human approval
  -> MBR.1 / MBR.1-A external review + user approval (complete)
  -> Full-KV legal-path source audit (complete)
  -> separately authorized W0 dual-DUT Chisel implementation (complete)
  -> MR-1A Route-A-hot and Full-KV common measurement integration (complete)
  -> MR-1B direct-pending contract approval and scoped implementation
  -> MR-2 independent array-only storage-wrapper realization
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

## Measurement RTL live status — 2026-10-21

MR-1A remains complete at its authorized Route-A-hot and Full-KV-common
functional scope. MR-1B B2c has three bounded implementation sub-batches:

1. the reset-only, fixed-64 reconciliation journal/query (`5348de9`);
2. accepted pending-to-packed eligibility withdrawal (`8fe1bba`); and
3. pre-issue R2 candidate cancel/ack, endpoint abort/ack, and the resulting
   R6-owned fault terminal (current directed P2a witness: 4/4 local tests
   passed on 2026-10-21).

The P2a witness was subsequently incorporated into the final bounded MR-1B
acceptance.  The single-record `valid_count = 1` restriction remains in force.

The P2a directed suite has now been reproduced from the clean remote Git
checkout `46ff89a`: `RouteAMeasurementDutR3Spec` passed 4/4 with exit code 0
on 2026-10-21. Its remote log is
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr1b_b2c_remote_p2a_46ff89a.log`.
This confirms the user-local offline Chisel/Verilator platform for this
directed Route-A test; it is not a dual-DUT structural or final B2c closure.

The independent direct-path non-regression has also been reproduced from the
clean remote Git checkout `3d44658`: `RouteADirectPendingReadPathSpec` passed
7/7 with exit code 0 on 2026-10-21. Its log is
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr1b_b2c_remote_direct_nonreg_3d44658.log`.
It confirms the pre-existing direct success/stale/mismatch/withdrawal/fault
contour after P2a; it does not substitute for the remaining latest
reconciliation regression, dual-DUT structural guard, or final B2c coverage
audit.

The earlier Full-KV B2c sideband tie-off issue is resolved by `81b7443` with
an explicit inactive direct-cancel ingress and consumed impossible ack.  The
remote final run passed 14/14 (`EXIT_CODE=0`) across Full-KV baseline,
four-consumer, packed activation, and dual-DUT structural suites; combined
with `c32fffe`'s 22/22 B2c-focused rerun, MR-1B is **PASS at its approved
single-record functional/provenance scope**.  This does not make MR-2, M2
production replacement, synthesis eligibility, DC, or PPA ready.

### MR-2 M2 carrier/provenance closure (2026-10-22)

The minimal M2 production-carrier contract is now implemented and functionally
verified.  The existing pending-payload/location owner supplies immutable,
group-scoped `m2_group_opaque_address_ref` and `m2_group_owner` facts in its
binding.  The admission adapter requires all accepted group members to agree,
relays the facts through the accepted P3 claim, and R3 records them with the
stage.  The two existing M2 group member requests and responses now carry
`kv_head`, opaque reference, and owner; R3 accepts a completion only on an
exact full identity match.  Wrong bank/reference/owner and group disagreement
are fail-closed.

Remote directed evidence is 11/11 passed (`EXIT_CODE=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_carrier_directed.log`;
W0/MR-1A/B2c non-regression and the dual-DUT structural guard are 27/27
passed (`EXIT_CODE=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_carrier_nonreg.log`.
The carrier's adapter/stage/outstanding-register control is recorded as
Route-A incremental, unestimated-not-zero BOM cost.

M2 carrier provenance and the bounded measurement-DUT production-control
replacement were closed before entry-data lowering. `RouteAMeasurementDut`
instantiated `RouteAM2ProductionControlOwner` with eight-bank mirrored
head/span control provenance plus a 36-stage exact two-member gate. Its
then-final directed remote regression was
4 suites/14 tests passed, `EXIT_CODE=0`, at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_owner_final_directed.log`.
The required W0/MR-1A/B2c non-regression is also 6 suites/27 tests passed,
`EXIT_CODE=0`, at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_owner_nonreg.log`.
The earlier precheck is retained only as a precheck because its intended
measurement-DUT selector used the wrong package.  The required M2
storage-array provenance audit is recorded in
`analysis/mr2_m2_entry_update_provenance_gap.md`: current carriers have no
legal entry/update-data producer, entry layout, RMW operand, write-enable, or
storage-fault source. That historical block was resolved only by the later
approved minimal-runtime implementation below; it was not resolved by
repurposing an address, owner, or fixture as entry data. No macro, physical
address, timing, energy, area, synthesis, DC, or PPA conclusion follows.

The implementation-level declaration review is now recorded in
`analysis/mr2_m2_entry_update_declaration_contract_proposal.md`. It separates
the frozen 59/50-bit (64/64 padded) semantic-accounting envelopes from real
entry words and finds no current production data-decision owner. Before M2
storage RTL, four explicit choices remain: entry encoding/validity, head/span
key and reuse rule, lifecycle-to-RMW lowering with one declaration producer,
and typed storage-fault encoding. The proposed declaration is a single data
carrier only; it cannot change R3 atomic publication, admission, R6 authority,
or R2 arbitration. Its future producer/peripheral/array costs are Route-A
incremental and `unestimated_not_zero`.

The final MR-2 four-decision approval proposal is
`analysis/mr2_m2_four_design_decision_proposal.md`. Its preferred package uses
128-bit real head/span entries, a 614-slot generation-tagged span pool, and
generic fail-closed storage faults; the entry arrays alone are 152,320 bits
(2.84× the frozen 64-bit accounting proxy) before tags, queues, or peripheral
logic. Crucially, frozen A4 M2 records require explicit private/shared
source-FIFO and create/dequeue/release facts that are absent from the current
non-contiguous R3 packed group. Approval must therefore include one explicit
upstream metadata-lifecycle declaration producer. Without that producer, only
the current provenance journal is implementable and it must not be labelled M2
storage realization.

### MR-2 minimal admission-to-metadata bridge (2026-10-22)

The first approved minimal-runtime implementation sub-batch is now live in
`RouteAMeasurementDut`. `RouteAAdmissionPublicationIngressAdapter` emits a
`MetadataAppendMemberDeclaration` only on the same accepted fire as the
existing retained admission context, R6 authority, and exact pending-payload
binding. `RouteAMetadataAdmissionBridge` therefore records an actual immutable
binding rather than reconstructing membership from group tag, ordinal, mapping
reference, or a fixture. It holds one bounded group entry per P3 layer,
up-to-64 exact member bindings, a local/shared/staging logical-credit
classification, and a 16-bit per-stream append sequence. It gates pre-accept
admission with ready-low before the triple fires; it neither revises the
admission disposition nor creates R3 publication, R6 authority, source
selection, or R2 arbitration.

The bridge forwards the pre-existing M2 group prepare only after the exact
member mask is complete. Publication faults keep pending membership and credit
while discarding only private preparation. Credit is released only from the
non-backpressuring R3 observation that the corresponding all-member post-R6
handoff has fired. At this bridge-only checkpoint, it was not yet the grouped
entry-data prepare/commit/abort or actual M2 entry storage. Those bounded
production pieces are implemented in the following record; the M2 array-only
boundary remains separately open. Its state is Route-A incremental and
`unestimated_not_zero` in `analysis/measurement_boundary_bom.json`.

Remote directed evidence is 4/4 passed (`EXIT=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_admission_p1_indexfix_20261022.log`:
non-contiguous real members, duplicate rejection, private prepare, publication
then all-member handoff release, and local-to-shared bounded credit fallback.
The previous dynamic stream-index width warnings were removed before this run.
The current-source dual-DUT elaboration/structural guard is 3/3 passed
(`EXIT=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_admission_p1_structural_20261022.log`.
Neither bridge-only result alone was an M2 entry-data/storage realization,
synthesis eligibility, or physical-cost conclusion.

### MR-2 M2 grouped entry-data production integration (2026-10-23)

The approved bounded-runtime lowering is now integrated in
`RouteAMeasurementDut`. The existing accepted retained-member declaration
enters `RouteAMetadataAdmissionBridge`; the bridge preserves immutable full
member bindings, credit class, and append sequence, and fires
`MetadataAppendOperand` only jointly with the pre-existing R3 M2 group
prepare. `RouteAM2ProductionControlOwner` validates the exact member mask and
binding provenance, reserves private head/span state, and returns the two
existing typed M2 member responses. It returns OK only after joint validation
of both objects; a failed validation produces the existing typed fault and
private abort rather than a partial update.

The real bounded entry state is two mirrored 128-bit head entries for each of
288 head keys and one 128-bit span entry for each of 614 slots (152,320 entry
bits before occupancy/generation and peripheral state). Both head replicas and
the matching span become visible together only on the existing accepted
`metadata_publish_commit`/Published resolution. A publication fault or reset
clears only private state and retains legal pending membership and credit.
Only the exact non-backpressuring post-R6 all-member handoff clears a visible
entry, advances its generation for stale-safe reuse, and releases bridge
credit. Generation wrap remains fail-closed.

Evidence is remote 11/11 directed (`EXIT=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_grouped_p1_entryverify_20261022.log`,
followed by remote 40/40 selected W0/MR-1A/MR-1B/M2/dual-DUT non-regression
(`EXIT=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_grouped_p1_full_nonreg_20261022.log`.
The evidence includes pre-publication invisibility, joint member completion,
typed semantic fault/abort, publication fault, reset, exact post-R6 handoff
release, credit fallback/release, stale/duplicate rejection, Full-KV
lifecycle/fault/reset, packed/hot/direct-pending paths, and the dual-DUT
structural guard.

This closes **bounded functional M2 production entry-data integration** only.
It did not at that point close the M2 array-only boundary, select an
SRAM/macro or ports, or turn functional storage into physical/PPA evidence.
The boundary result is recorded next; M2 queue/staging activity and wrapper
cost remain `unestimated_not_zero`, and the old fixture-only
`RouteAM2EntryStorage` remains separate from the production result.

### MR-2 M2 logical entry-array boundary (2026-10-24)

`RouteAM2EntryArrayBoundary` now owns only the bounded functional entry-word
interior: 288 logical head keys with two mirrored 128-bit head-control entries
each, plus 614 logical 128-bit span-owner entries. It accepts only parent-owned
already-decided publication-commit and all-member-handoff-release updates. The
production owner still exclusively owns accepted operand association, immutable
validation, RMW decision, private prepare/abort, slot and generation control,
credit, typed faults, `metadata_publish_commit`, and post-R6 handoff
qualification. Both updates may occur in one cycle only for distinct logical
locations; the boundary asserts that condition and mirrored-head equality.

The boundary structural/preflight suite passed locally (8 tests, including all
four M2/P3/S2/R5 boundary guards and MBR/SRP validators). Remote targeted
evidence passed 3 suites / 11 tests, `EXIT=0`, at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_array_boundary_p0_20261023.log`.
Remote selected W0/MR-1A/MR-1B/M2/dual-DUT non-regression then passed 10
suites / 40 tests, `EXIT=0`, at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_array_boundary_p1_full_nonreg_20261023.log`.

This closes **only the logical functional M2 entry-array boundary**. It does
not select a memory macro, physical banking/ports/latency, controller,
queue/staging activity model, DC, CACTI, timing, area, power, throughput, or
PPA conclusion. Those retained and unestimated items must be addressed by the
separate realization-preparation stage.

### MR-2 R5 logical availability/generation boundary (2026-10-25)

`RouteAR5AvailabilityArrayBoundary` is now the sole logical owner of the R5
availability/generation vectors. `RouteAPageManager` retains allocation choice,
PageRef/generation validation, descriptor visibility, durable
invalidate-before-free, reclaim, drain/reset/init, and all descriptor-service
and wrapper-peripheral behavior. Remote directed R5 evidence passed `21/21`;
the latest-source selected cross-stage evidence passed in two non-overlapping
invocations totalling `40/40`. The record is
[`mr2_r5_availability_array_boundary_contract.md`](mr2_r5_availability_array_boundary_contract.md).

This closes only the logical functional R5 array boundary. It does not select
an R5 macro, ports, latency, descriptor service, controller, DC, CACTI, or
PPA, and all remaining storage/access costs remain `unestimated_not_zero`.

### MR-2 completion review (2026-10-25)

MR-2 now passes at its approved **functional measurement-boundary** scope:
P3 stage, S2 payload/sidecar, M2 entry, and R5 availability/generation
interiors are separated while every parent-owned protocol, atomicity,
identity/generation, lifecycle, reset, and external-service control remains
in the candidate DUT. The review is
[`mr2_completion_review.md`](mr2_completion_review.md). It neither selects
physical storage nor authorizes synthesis/PPA. The next bounded task is the
dual-DUT measurement-cut freeze, before any realization-choice work.

### Dual-DUT measurement-cut freeze (2026-10-25)

The actual `FullKVMeasurementDut` and `RouteAMeasurementDut` instance/source
lists, outer interfaces, cost classifications and single-record direct-pending
limit are frozen at `fc06fdbc`. The record is
[`measurement_dut_cut_freeze_20261025.md`](measurement_dut_cut_freeze_20261025.md)
with its machine-checked JSON inventory. It confirms actual shared R2/R1/
delivery classes, but deliberately records non-identical Full-KV S2/lifecycle
classes and the absent same-class Full-KV hot owner as **not automatically
cancellable**. The next gate is a separately approved realization-preparation
review; this freeze does not select a synthesis top or physical wrapper.

### Synthesis-top candidate selection (2026-10-25)

The two future control-top candidates are selected conditionally from the
frozen measurement DUT projections, while `RouteAKVSubsystemTop` remains
rejected as a composition skeleton. The review
[`synthesis_top_candidate_selection_review.md`](synthesis_top_candidate_selection_review.md)
records retained/excluded controls, outer boundaries, no-wholesale-black-box
rules and the pre-DC stop conditions. In particular, actual shared R2/R1/
registry/router classes do not resolve the Full-KV hot and S2/lifecycle
equivalence differences. The next permitted work is wrapper-interface planning
and common-equivalence disposition, not RTL, macro selection, DC or PPA.

The EDA-server Chisel platform is user-local and offline. See
[`chisel_platform_handoff_20261021.md`](chisel_platform_handoff_20261021.md).
Future remote implementation work must use a provenance-preserving Git checkout
rather than the earlier rsync-only platform smoke snapshot.

## New-conversation prompt seed

> Work in `/home/wz/AI/kvpress` on branch `research/kvzap-latest`. Read
> `AGENTS.md`, `analysis/architecture_spec.md`,
> `analysis/route_a_current_handoff.md`,
> `analysis/rtl2_phase_contract.md`, and
> `analysis/rtl3_9_c4_d_functional_completion_review.md` before editing; use
> `analysis/route_a_document_map.md` to select any stage-local evidence.
> Current state is RTL3 functional-subsystem closure complete. SRP.0--SRP.1-R
> passed human partition review; SRP.2 source/toolchain eligibility, SRP.3
> realization-requirements decision planning, SRP.4 differential-cost evidence
> planning, and SRP.5 completion review are complete. MBR.0's candidate
> measurement-boundary BOM passed human review; MBR.1 and MBR.1-A passed
> external technical review with minor corrections and received user approval.
> The Full-KV legal-path audit originally found all three baseline path
> segments missing. W0 has completed its bounded dual-DUT functional scope,
> and MR-1A has completed the Route-A-hot plus Full-KV common lifecycle/status
> scope. MR-1B B2c is complete only for its approved single-record functional
> contour: reconciliation, qualified withdrawal, cancel/abort, and R6-owned
> fault have passed remote directed and W0/MR-1A structural regressions. The
> MR-2's bounded M2 production control and admission-to-metadata membership
> bridge, real `MetadataAppend` operands, grouped entry-data
> prepare/commit/abort, actual bounded production entry state, and the M2
> logical entry-array boundary are live in `RouteAMeasurementDut`. The
> fixture-only `RouteAM2EntryStorage` is still not production evidence. The
> R5 availability/generation array-only boundary is also functionally closed;
> both M2 and R5 remain logical boundaries only, and no
> result selects a macro, wrapper ports/latency, or physical realization. None
> selects
> a top or begins physical realization work.
> Read
> `analysis/synthesis_realization_partition.md` and
> `analysis/srp3_realization_requirements_decision_plan.md`, and
> `analysis/srp4_differential_cost_evidence_plan.md`, and
> `analysis/srp5_completion_review.md`, and
> `analysis/measurement_boundary_selection.md`, and
> `analysis/measurement_boundary_bom.json`, and
> `analysis/measurement_baseline_fairness_plan.md`, and
> `analysis/measurement_baseline_matrix.json`, and
> `analysis/measurement_realization_candidate_proposal.md`, and
> `analysis/measurement_realization_candidate_manifest.json`, and
> `analysis/full_kv_baseline_path_audit_20261016.md`, and
> `analysis/full_kv_baseline_path_audit_20261016.json`, and
> `analysis/synthesis_eligibility_manifest.json`. Do not advance to realization
> choice, synthesis,
> physical realization, PPA, or cost evaluation without a later approval;
> do not reopen pruning/admission/page/scheduler/atomicity or introduce
> physical HBM/SRAM, numeric pipeline, timing, PPA, model/GPU, or new A4 DSE
> claims. Preserve frozen artifacts, run no-model preflight/tests first, update
> live navigation, and commit each completed modification batch with its
> source/scope.
