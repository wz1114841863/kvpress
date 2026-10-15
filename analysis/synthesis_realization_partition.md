# SRP — Synthesis-Realization Partition & Eligibility Review

**Status:** SRP.0--SRP.1 completed as a proposal and awaiting the required
human partition review.  This document is a living successor-stage plan, not a
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
- `unestimated_pending_evidence`: known cost without present physical evidence;
  it must reconcile with the A4.14.1 omitted-cost budget.
- `not_applicable`: no paper-hardware cost row, used only for verification
  infrastructure or a still-unselected integration shell.

`required_for_paper_claim` is a third, independent field.  It distinguishes
“must obtain implementation or credible cost evidence” from “must implement
all RTL locally.”  A value of `true` requires a named evidence route and a
semantic replacement plan; `false` requires an explicit exclusion rationale.

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
| SRP.1 — Partition Proposal | Propose the two classifications, `required_for_paper_claim`, future synthesis-top candidates, external/verification-only exclusions, and `stop_for_review` items. | Treating a proposal as an approved DUT or physical implementation. |
| **Human review gate** | Approve or revise the proposed minimum paper boundary before SRP.2. | Automatic continuation. |
| SRP.2 — Source/Toolchain Eligibility | Review Chisel constructs, elaboration dependencies, storage shape, reset/IO ownership, wrapper needs, and available toolchain assumptions. Results use the implementation statuses above. | DC/synthesis execution, timing/PPA claims, or `synthesis_ready` declaration. |
| SRP.3 — Realization Requirements & Decision Planning | State required memory access/numeric observable behavior, unresolved parameters, candidate evidence methods, decision owners, and stop conditions. | Choosing macro banks/ports, HBM bursts, exp design, pipeline depth, or target frequency. |
| SRP.4 — Differential Cost Evidence Plan | Align Full-KV baseline, Route-A differential cost, A4-covered accounting, omitted-cost budget, and future evidence source. | Re-running A4 DSE or deriving net-benefit/PPA conclusions. |
| SRP.5 — Completion Review | Decide whether partition, requirements, and evidence plans are sufficiently explicit to authorize a separate realization-choice stage. | Wrapper implementation, synthesis, or performance conclusions. |

## SRP.0--SRP.1 disposition

[`synthesis_eligibility_manifest.json`](synthesis_eligibility_manifest.json)
records the clean source anchor, all structural children instantiated by the
current composition top, the test-scope functional witnesses/adapters, and the
proposed partition at state/interface/function granularity.  It deliberately
finds that the current top is not a future synthesis top and that M2/P3/R5/S2
storage, R4 numeric/partial state, external memory service, and the missing
toolchain/macro choices are `stop_for_review` items.

The proposal does **not** label any source as synthesis-ready.  It provides a
minimum paper-relevant evidence boundary and explicit exclusions only.  SRP.2
may begin solely after the human review accepts or revises that boundary.

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

SRP PASS requires every paper-relevant function to have a partition,
`required_for_paper_claim` decision, semantic replacement plan, cost owner,
and credible evidence route.  It authorizes only a separately reviewed
memory-interface/numeric-realization choice stage.

SRP must stop for review if a test-only provider is proposed as DUT; a
functional environment lacks both a replacement plan and cost evidence; a
common resource is charged wholesale to Route-A; an interface change would
weaken a frozen contract; or the minimum credible differential cost is already
incompatible with the A4.14.1 omitted-cost constraint.  Such a stop may lead
to scope reduction or an independent feasibility review; it never silently
changes Route-A semantics.
