# Route-A document map

## Purpose and preservation rule

This map separates the small set of documents needed to continue a discussion
from the stage-local records that establish particular results. It is a
navigation aid, not a replacement for a frozen manifest, experiment report, or
interface contract. No record is moved, deleted, or relabelled by this map.

## Default core read set for a new Route-A discussion

Read these in order before proposing a new change or successor-stage plan:

1. [`../AGENTS.md`](../AGENTS.md) — repository rules, frozen boundaries, and
   claim restrictions.
2. [`architecture_spec.md`](architecture_spec.md) — normative Route-A
   semantics, owners, parameterization, and physical-evidence exclusions.
3. [`route_a_current_handoff.md`](route_a_current_handoff.md) — current
   disposition, completed RTL3 functional closure, and authorized successor
   decision path.
4. [`rtl2_phase_contract.md`](rtl2_phase_contract.md) — live RTL1--RTL3
   phase ledger and boundary language.
5. [`rtl3_9_c4_d_functional_completion_review.md`](rtl3_9_c4_d_functional_completion_review.md)
   — latest bounded RTL3 functional-subsystem review and non-claims.
6. [`synthesis_realization_partition.md`](synthesis_realization_partition.md)
   — active SRP planning contract, including the human review gate before
   eligibility or realization work.
7. [`measurement_boundary_selection.md`](measurement_boundary_selection.md)
   and [`measurement_baseline_fairness_plan.md`](measurement_baseline_fairness_plan.md)
   — human-approved MBR.0 candidate cut plus MBR.1's approved paired
   Full-KV fairness boundary.  Read the approved
   [`measurement_realization_candidate_proposal.md`](measurement_realization_candidate_proposal.md)
   only for the subsequent candidate measurement implementation-preparation
   scope; use their JSON records only when an exact classification is at issue.

This is the **core conversational set**. It is intentionally not a substitute
for stage evidence. Use this map to select exactly one additional record when
a question concerns a particular result, interface, or historical claim.

## Conditional living context

Read only when the question needs the corresponding history or object:

| Trigger | Read on demand | Why it is not default core |
|---|---|---|
| Trace schema, trace collection, or predictor evidence | [`../TRACE_SCHEMA.md`](../TRACE_SCHEMA.md) | Continuous trace record; irrelevant to a pure RTL successor-plan discussion. |
| A0--A4 research/DSE disposition or a proxy/accounting claim | [`route_a_research_plan.md`](route_a_research_plan.md) | Longitudinal research record, not the live RTL interface authority. |
| Original Route-A rationale or a historical architecture-stage transition | [`../KVZAP_ARCHITECTURE_PATH.md`](../KVZAP_ARCHITECTURE_PATH.md) | Historical route narrative; later slices may supersede its next-step wording. |
| Broad discovery of a named attachment | [`README.md`](README.md) | Full index; use it to locate a record, not as a default technical contract. |

## Stage evidence index

| Flow stage | Preserve and read only when needed | Primary entry / lookup rule |
|---|---|---|
| Phase 0 / predictor and trace freezes | Baseline, LongBench, Route-B screening, and trace-gate freezes | `baseline_freeze.json`, `predictor_trace_gate_*`, `longbench_*_freeze.json`, `b4_route_b_screening_freeze.json`; see `AGENTS.md` for claim limits. |
| Route-A A0--A4 research/DSE | Static feasibility, lifecycle, accounting, and final A4.14.1 ledger | `route_a_research_plan.md`, `route_a_a0_a3_a4_handoff_20260902.md`, `route_a_stage_archive_20260902.md`, `route_a41*` / `route_a41[1-4]*_contract.md`, the named `analysis/experiments/` report, and `a4141_local_provenance_recovery_20261016.md` when local ledger availability is at issue. |
| Architecture and Gate-A / Gate-RTL0 | Frozen interface, cross-closure, hierarchy, ports, and assertions | `architecture_spec.md`, `architecture_gate_a_*`, `rtl_entry_*_contract.md`, and their manifests/freezes. |
| RTL1 / RTL2 | Control and constrained transaction/dataflow steps | Find the numbered `rtl1_*` or `rtl2_*` contract and its paired manifest through `rtl2_phase_contract.md` or `README.md`; do not load the entire lineage by default. |
| RTL3.0--RTL3.8.5 | Replacement-owner, functional environments, source/R4 paths, and all-source coverage | Start at the relevant `rtl3_*_contract.md` named by the phase ledger; use `rtl3_8_5_full_path_closure_coverage_contract.md` for all-source coverage limits. |
| RTL3.9-A / B | R3 materialization, payload/descriptor durability, atomic publication, R6 authority | `rtl3_9_a*_contract.md`, `rtl3_9_b*_contract.md`, and their manifests; B3 is the publication/authority reference. |
| RTL3.9-C | First packed read through S2, terminal/reclaim, event provenance, and completion review | `rtl3_9_c0_*` through `rtl3_9_c4_d_*`; begin with the C4-D review, then open the smallest named C0--C4 slice needed for a disputed condition. |
| SRP | Minimum paper-relevant realization boundary, eligibility planning, and future cost-evidence routing | Start with `synthesis_realization_partition.md`, then `srp3_realization_requirements_decision_plan.md`, `srp4_differential_cost_evidence_plan.md`, `srp5_completion_review.md`, and `synthesis_eligibility_manifest.json`; consult `a4141_local_provenance_recovery_20261016.md` only for the resolved local-ledger availability item. SRP.0--SRP.5 conditionally passes only to a separately authorized realization-choice planning review. |
| MBR.0--MBR.1-A | Approved candidate measurement cut, source/partition BOM, paired Full-KV fairness plan, and realization-preparation scope | Read `measurement_boundary_selection.md`, then `measurement_baseline_fairness_plan.md`; use `measurement_boundary_bom.json` or `measurement_baseline_matrix.json` for exact source/comparison entries. Read `measurement_realization_candidate_proposal.md` for the approved control/array/R4/top-shell scope, then `full_kv_baseline_path_audit_20261016.md` for the concrete W0 Chisel package. MBR is closed; W0 awaits only explicit implementation authorization and selects no wrapper, synthesis, or PPA. |

## Artifact role rules

- `*_contract.md` explains scope, owner, evidence, validation, and non-claims.
- `*_manifest.json` or audit JSON is machine-readable evidence for its named
  stage, not a living status dashboard; preserve its original stage snapshot.
- `*_freeze*`, `*_provenance*`, dated handoffs, and `analysis/experiments/`
  outputs are immutable/historical evidence. Open them only to audit the
  associated claim or reproduce that stage.
- `route_a_current_handoff.md`, `rtl2_phase_contract.md`, and this map are
  living navigation/status documents. Update those rather than rewriting a
  historical manifest when a later phase changes current disposition.

## Retrieval discipline

For a new question, identify its stage first, read the five core documents,
then add only the table row's primary record. If an exact field, hash, test,
or owner claim is challenged, follow the primary record's links to its paired
manifest/provenance file. This keeps a conversation evidence-bounded while
retaining the complete experiment history.
