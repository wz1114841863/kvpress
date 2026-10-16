# SRP — Synthesis-Realization Partition & Eligibility Review

**Status:** SRP.0--SRP.5 completion review has conditional-pass closure at its
declared planning scope.  This document is a living successor-stage record, not a
physical implementation, synthesis, PPA, performance, or new DSE record.

## Purpose

SRP determines the minimum hardware boundary that must receive implementation
or credible realization evidence for a Route-A paper claim.  It separates
functional correctness, implementation realization, and cost/performance
evidence so that no functional model becomes an implicit zero-cost circuit.

It begins from RTL3.9-C4-D functional-subsystem closure.  That closure does
not make the current composition top a synthesis top, select an SRAM/HBM
implementation, or implement an R4 numeric datapath.

## Immutable inputs and scope

- **Functional-closure decision anchor:** `cf9f055` (`RTL3.9-C4-D`).
- **SRP source-inventory anchor:** the exact clean `HEAD` recorded when
  SRP.0 starts.  It is a separate fact from the closure decision and must not
  be inferred from this planning document.
- **Semantic authority:** `architecture_spec.md`, the RTL entry hierarchy and
  assertion contracts, and the applicable RTL3.9-C records.
- **Accounting authority:** the A4.14.1 differential ledger and its
  omitted-cost budget.  SRP records coverage and future evidence sources; it
  does not recompute the ledger or add a new DSE variant.

SRP must not reopen the KVzap mask/pruning, post-decision admission result,
64-token page, M2 organization, P3/S2 mapping, GQA legality,
queue/scheduler, or sole atomic-publication semantics.  It does not select an
HBM protocol/controller, SRAM macro/banking/ports, clock/frequency, numeric
pipeline/exp implementation, timing, throughput, area, power, or complete
LLM inference behavior.

## Two independent classifications

Each reviewed **state element, interface edge, or function**—not necessarily
each whole Chisel module—gets both dimensions below.  A source module may
contain multiple records when it crosses a common/incremental or
implementation/environment boundary.

### Implementation partition

- `candidate_control`: potential logic in a future synthesis DUT; it is not
  yet declared synthesis-ready.
- `requires_wrapper`: control semantics remain in scope, but a storage,
  memory, or numeric wrapper must be separately chosen.
- `external_contract`: environment or black-box boundary whose contract and
  replacement verification are required.
- `verification_only`: testbench, event observer/oracle, fixture, or
  functional witness artifact; never a DUT implementation claim.
- `blocked_by_realization`: cannot be partitioned until a named realization
  question is decided.
- `not_assessed`: deliberately deferred until its prerequisite SRP phase.

### Cost ownership

- `common_full_kv`: shared Full-KV/Route-A provision, reported once.
- `route_a_incremental`: Route-A-specific state/control/provision.
- `differential_activity`: shared infrastructure whose path-specific accesses
  or activity must be compared rather than charging the whole module to
  Route-A.
- `external_system_cost`: outside-DUT cost requiring a declared model or
  calibrated evidence.
- `not_applicable`: no paper-hardware cost row, used only for verification
  infrastructure or a still-unselected integration shell.

Cost ownership answers only **who bears a cost**.  It must never encode whether
the cost is already evidenced.  Each record therefore also carries a separate
`cost_evidence_status` (`not_assessed_srp1`,
`requires_srp4_reconciliation`, `unestimated_pending_evidence`, or
`not_applicable`) and, where relevant, its A4/budget reconciliation route.

Two independent booleans replace the earlier ambiguous single paper-claim
field:

- `required_for_local_implementation`: the paper needs a local DUT/wrapper
  implementation for this item.
- `required_for_paper_cost_evidence`: the paper needs credible differential
  cost evidence for this item, even when local implementation is explicitly
  excluded.

Every non-test record must also declare when its concrete semantic port mapping
and regression mapping are due (`SRP.2`, `SRP.3`, or an existing regression).
SRP.1 records the obligation; it does not pretend that the replacement design
has already been completed.

## Boundary principles

`route_a_synthesis_dut` is a future, explicitly selected control/packing/
metadata/merge-support boundary.  It cannot be assumed to equal the current
`RouteAKVSubsystemTop`: that file remains a composition-only skeleton with
inactive carriers, while the RTL3 functional witness includes test-scope
composition and named functional environments.

`route_a_evaluation_system` is the DUT plus declared external memory/macro,
attention-partial, numeric, and service models.  It is an evaluation boundary,
not a statement that those environments are free or implemented.

The initial SRP inventory must at least distinguish:

- R3 retained-record materialization, M2/P3 packing, and publication control
  from the already-selected external admission/predictor decision;
- M2 reference provider versus M2 control/storage realization;
- P3 pending-HBM backing, `p3_payload_stage_page`, and R3/P3 wrapper control;
- R5 allocator/reclaim control, on-chip availability state, and descriptor
  HBM region;
- common S2 payload/GQA infrastructure versus incremental position-sidecar
  storage/management;
- R4 structural multi-source merge control versus R4 numeric realization and
  partial-state storage; and
- outer R1 memory, attention-partial provider, functional R4 reference, and
  all test-only C4 observers/oracles.

R1, R2, R6, and S2 must be classified at function/operation granularity:
their presence on a Route-A path never alone charges their entire provision to
Route-A.

## SRP gates

| Phase | Deliverable and permitted result | Explicitly out of scope |
|---|---|---|
| SRP.0 — Provenance & Source Inventory | Record both anchors, clean-tree state, real main/test source inventory, functional providers, state/interface candidates, and existing evidence references. | RTL edits, synthesis, physical parameters, eligibility verdicts. |
| SRP.1 — Partition Proposal | Propose the two classifications, `required_for_local_implementation` and `required_for_paper_cost_evidence`, future synthesis-top candidates, external/verification-only exclusions, and `stop_for_review` items. | Treating a proposal as an approved DUT or physical implementation. |
| **Human review gate** | Approve or revise the proposed minimum paper boundary before SRP.2. | Automatic continuation. |
| SRP.2 — Source/Toolchain Eligibility | Review Chisel constructs, elaboration dependencies, storage shape, reset/IO ownership, wrapper needs, and available toolchain assumptions. Results use the implementation statuses above. | DC/synthesis execution, timing/PPA claims, or `synthesis_ready` declaration. |
| SRP.3 — Realization Requirements & Decision Planning | State required memory access/numeric observable behavior, unresolved parameters, candidate evidence methods, decision owners, and stop conditions. | Choosing macro banks/ports, HBM bursts, exp design, pipeline depth, or target frequency. |
| SRP.4 — Differential Cost Evidence Plan | Align Full-KV baseline, Route-A differential cost, A4-covered accounting, omitted-cost budget, and future evidence source. | Re-running A4 DSE or deriving net-benefit/PPA conclusions. |
| SRP.5 — Completion Review | Decide whether partition, requirements, and evidence plans are sufficiently explicit to authorize a separate realization-choice stage. | Wrapper implementation, synthesis, or performance conclusions. |

## SRP.0--SRP.1 disposition

[`synthesis_eligibility_manifest.json`](synthesis_eligibility_manifest.json)
records the clean source anchor, all structural children instantiated by the
current composition top, the test-scope functional witnesses/adapters, and the
revised proposed partition at state/interface/function granularity.  SRP.1-R
adds a complete child-to-record coverage map, separates cost ownership from
cost-evidence status, and separates local-implementation need from paper-cost
evidence need.  It deliberately finds that the current top is not a future
synthesis top and that M2/P3/R5/S2 storage, R4 numeric/partial state, external
memory service, and the missing toolchain/macro choices are
`stop_for_review` items.

The proposal does **not** label any source as synthesis-ready.  It provides a
minimum paper-relevant evidence boundary and explicit exclusions only.  The
SRP.0--SRP.1-R human partition review passed with minor documentary corrections
on 2026-10-15: all 40 structural children are covered and all 30 partition
records are internally valid.  SRP.2 source/toolchain eligibility is now
authorized, while synthesis, physical realization, and cost evaluation remain
outside that authorization.

## SRP.2 disposition

SRP.2 reviewed main Chisel source and exercised the existing structural
CHIRRTL/SystemVerilog emission test under Java 21.  All seven main and 64 test
Scala sources compiled; the three structural tests passed.  This is only a
source-level eligibility result: no main-source host/test dependency or
BlackBox/PDK dependency was found, but the current top remains a composition
skeleton and the `Mem` declarations in S2 and P3 remain logical storage that
requires later realization.

The per-record dispositions, toolchain limits, and exact command are in
[`synthesis_eligibility_manifest.json`](synthesis_eligibility_manifest.json).
No item is synthesis-ready, no macro/controller/clock is selected, and SRP.3
has not begun.

## SRP.3 disposition

[`srp3_realization_requirements_decision_plan.md`](srp3_realization_requirements_decision_plan.md)
closes requirements planning for precisely the nine SRP.2 records whose
semantic mapping was due in SRP.3: M2 storage; P3 pending backing and stage;
R5 availability state and descriptor region; common S2 payload and
incremental sidecar; R4 numeric/partial state; and external memory service.
For each it records required observable behavior, unresolved realization
parameters, evidence route, responsible semantic module, decision stage,
review authority, and a stop condition.  The corresponding concise
machine-readable record separately marks existing logical-contract mapping
from still-pending physical-wrapper port mapping in
[`synthesis_eligibility_manifest.json`](synthesis_eligibility_manifest.json).

This result makes no memory/numeric choice and does not implement a wrapper,
controller, macro, pipeline, or future synthesis top.  It does not calculate
costs or reopen A4.14.1.  At SRP.3 completion, SRP.4 differential-cost evidence
planning was the next permitted planning phase; its later result is recorded
immediately below.

## SRP.4 disposition

[`srp4_differential_cost_evidence_plan.md`](srp4_differential_cost_evidence_plan.md)
maps every partition record to A4-accounted proxy coverage, partial coverage,
an explicitly unestimated term, common/non-incremental treatment, deferred
future-top cost, or a verification-only exclusion.  It identifies M2 queue/staging, P3 stage, R5
descriptor maintenance, and R4 numeric/partial state as the first omitted-cost
risk screen; later work is limited to owner-carried action taxonomies until a
separately approved realization choice exists.

SRP.4 initially recorded the materialized A4.14.1 report as absent locally.
The later read-only
[`a4141_local_provenance_recovery_20261016.md`](a4141_local_provenance_recovery_20261016.md)
restores the exact ignored report and required input closure, re-hashes them,
and passes the original `--preflight-only` check without creating a new ledger
output.  This resolves only availability for accepted-ledger revalidation; it
does not recompute A4, establish physical cost, or assert a new budget result.
The machine-readable mapping is in
[`synthesis_eligibility_manifest.json`](synthesis_eligibility_manifest.json).
SRP.5 Completion Review is the next permitted planning phase and has not
begun at the time of SRP.4 completion; its later result is recorded below.

## SRP.5 disposition

[`srp5_completion_review.md`](srp5_completion_review.md) finds SRP.0--SRP.4
planning complete enough to conditionally pass into a **separately authorized,
one-record-at-a-time realization-choice planning review**.  It distinguishes
the normal next-stage tasks (physical wrapper mapping and candidate planning)
from hard blockers: the prior A4.14.1 availability blocker is resolved only
for read-only ledger/budget revalidation; the unselected future top blocks
integration/synthesis; and any action without required owner-carried fields
blocks a cost count for its row rather than becoming zero cost.  The recovered
proxy ledger still cannot support a final physical net-benefit conclusion.

The conditional pass authorizes neither RTL/wrapper implementation nor any
macro/controller/numeric selection, synthesis, PPA, controller/PHY, attention
accelerator, or complete-inference work.  The exact authorization and stop
conditions are machine-readable in
[`synthesis_eligibility_manifest.json`](synthesis_eligibility_manifest.json).

## Required semantic and accounting safeguards

Every proposed replacement/externalization must name its port mapping and
regression route for the frozen valid/ready, identity/generation, reset,
stale/fault, `metadata_publish_commit`, no-early-packed-read, four-consumer
commit, terminal, reclaim/free, and retire semantics.  Test-only accepted-event
capture remains evidence for those assertions, never an owner or DUT feature.

Every future cost row must state the Full-KV comparison basis, Route-A
differential, A4 coverage status, omitted-budget status, prospective evidence
method, and double-counting risk.  A missing realization or model is not zero
area, zero energy, zero traffic, or zero latency.

## PASS and stop criteria

SRP PASS requires every paper-relevant function to have a partition, both
implementation/cost-evidence decisions, a deferred-or-complete semantic
mapping, cost owner, and credible evidence route.  It authorizes only a separately reviewed
memory-interface/numeric-realization choice stage.

SRP must stop for review if a test-only provider is proposed as DUT; a
functional environment lacks both a replacement plan and cost evidence; a
common resource is charged wholesale to Route-A; an interface change would
weaken a frozen contract; or the minimum credible differential cost is already
incompatible with the A4.14.1 omitted-cost constraint.  Such a stop may lead
to scope reduction or an independent feasibility review; it never silently
changes Route-A semantics.
