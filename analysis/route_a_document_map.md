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
| MBR.0--MBR.1-A / measurement RTL | Approved candidate measurement cut, source/partition BOM, paired Full-KV fairness plan, and bounded Chisel realization | Read `measurement_boundary_selection.md`, then `measurement_baseline_fairness_plan.md`; use `measurement_boundary_bom.json` or `measurement_baseline_matrix.json` for exact source/comparison entries. Read `measurement_realization_candidate_proposal.md` for the approved control/array/R4/top-shell scope, then `full_kv_baseline_path_audit_20261016.md` for W0 and MR-1A implementation evidence. MBR is closed; W0 and MR-1A are complete at their bounded functional scopes. Use `mr1b_direct_pending_cross_owner_contract_proposal.md` only for the approved single-record direct-pending contour. The completed P3/S2/M2/R5 boundary evidence is consolidated by `mr2_completion_review.md`. The historical dual-DUT source/port/cost snapshot is `measurement_dut_cut_freeze_20261025.md`; the current successor source/port/filelist freeze is `successor_synthesis_source_port_filelist_freeze_20261028.md`. Neither is a wrapper, synthesis, or PPA decision. |
| Realization preparation | Logical storage-wrapper interfaces, common-equivalence allocation, integration-shell responsibilities, external/numeric nonzero rows, successor source freeze, and pre-DC dual-top input inventory | Read `realization_preparation_wrapper_common_disposition.md` and its manifest, then `successor_synthesis_source_port_filelist_freeze_20261028.md`, `dual_synthesis_top_input_package_20261028.md`, `control_projection_p1_externalization.md`, `paired_control_projection_profile_20261028.md`, and the completed `paired_control_projection_hdl_freeze_20261028.md`. Paired 9-bit S2 functional conformance is complete but common cost remains non-cancellable. P1 implemented projection constructors and typed functional-boundary externalization; the profile supplies their common bounded A3 parameter object. The current Route-A source input is the descriptor-externalized 48-file split successor recorded in `r5_descriptor_externalized_successor_input_freeze_20261029.md`; do not regress to the legacy monolithic lowering or 182-file list. None of these records defines a macro, physical port count, latency, clock, controller, numeric implementation, DC, or PPA result. |
| DC environment preflight | Remote DC executable/library availability and deterministic no-DC input checking | Read `dc_environment_preflight_20261029.md` and run `hardware/route_a/dc/check_kvzap_control_projection_dc_env.sh` only after sourcing its companion environment file on the EDA server. It confirms an inherited feasibility-library candidate and the frozen independent HDL filelists, but intentionally leaves constraints, array/black-box treatment and external-service stubs unselected. It is not a DC invocation or a library/corner/PPA decision. |
| DC constraint contract | Parameterized one-clock, synchronous-reset and top-level I/O constraint procedure | Read `dc_constraint_contract_20261029.md`, then statically run `hardware/route_a/dc/check_kvzap_control_projection_constraints.sh`. The procedure requires an approved run manifest to supply all numerical timing/I/O values; no H3 period is inherited and no DC run is launched. Array/black-box and external-service decisions remain separate. |
| DC feasibility fair-v1 baseline | Approved identical numerical constraints and static actual-HDL coverage | Read `dc_feasibility_fair_v1_constraint_freeze_20261029.md` and use `hardware/route_a/dc/dc_feasibility_fair_r5_descriptor_successor_v1.json` plus `check_kvzap_control_projection_dc_feasibility_fair_v1.sh`. This freezes the unchanged 2.0 ns fairness baseline and its descriptor-externalized successor input; neither the numeric profile nor a static report is a DC result. |
| DC feasibility input readiness and completed run | Strict paired constraint/input acceptance plus first native DC disposition | Read `dc_successor_input_preflight_r5_descriptor_externalized_20261029.md`, then `dc_feasibility_run_r5_descriptor_externalized_20261029.md`, `dc_feasibility_result_r5_descriptor_externalized_20261030.md`, and `dc_array_proxy_materialization_20261029.md`. Fair-v1 static coverage and five same-header M2/P3/R5/S2 array-interior proxies pass against the 1-file Full-KV/48-file Route-A successor, while all parent controls and external nonzero/unestimated services remain explicit. Both tops link/map and emit netlists, but Route-A fails the frozen setup target and has unresolved hierarchical-lint closure. Do not use raw area/timing for PPA, common-cost cancellation, or zero-cost external-service claims. |
| DC control-realization refinement | Saved-DDC hotspot diagnosis, bounded successor RTL, generated state/proxy closure, and completed same-fair-v1 comparison | Read `dc_control_realization_diagnosis_20261101.md`, then `dc_control_refinement_successor_20261102.md`, and finish with `dc_control_refinement_result_20261103.md`. Retain `dc_control_refinement_active_run_handoff_20261102.md` only as the historical active-run snapshot. The completed paired run closes tool/input provenance and observes a 41.146% Route-A mapped-cell-area reduction, an exact 645,012 sequential-cell/clock-alias-load reduction, and a 21.462% lint-warning reduction. Setup still fails with WNS -0.33 ns and TNS -7,891.18 ns, while the remaining 44,513 warnings keep structural cleanliness blocked. This is logic-only feasibility evidence, not PPA, external-service-zero-cost, speedup, or hardware net benefit. |
| M2/P3 wrapper control-realization P0 | Read-only field-liveness, state-concentration, timing-path and successor-candidate diagnosis after the accepted refinement | Read `dc_m2_p3_wrapper_p0_diagnosis_20261103.md` after the completed DC result. The two wrapper membership tables are 92.907% of its mapped sequential cells. The first bounded candidate stores only a 79-bit member record and 80-bit pending suffix, with a 76,032 mapped-sequential-cell pre-DC ceiling; later independent candidates address the 36-by-64 materializer selector and ordinal-indexable reconciliation lookup. P0 changes no RTL and launches no synthesis. |
| M2/P3 compact-membership P1 | First bounded wrapper representation change, functional non-regression, generated successor closure, and authorized paired-DC routing | Read `dc_m2_p3_wrapper_compact_membership_implementation_20261103.md` after P0, then `dc_m2_p3_wrapper_compact_membership_successor_20261103.md`; use `dc_m2_p3_wrapper_compact_membership_dc_run_20261103.md` only for the separately authorized fair-v1 run state. The 79-bit member record and 80-bit pending suffix pass the final 14-suite/57-test remote regression; the 48-file successor passes 16/16 typed ports, 12/12 owners and 5/5 paired proxies, with wrapper raw state 990,322 -> 400,498 bits. The full reconciliation journal and all frozen authority/publication/arbitration semantics remain intact. The active DC launch is not a result; raw state is not mapped area or PPA. |

## Artifact role rules

For compact-table read consumers, legal concurrency and the selected RD1
change, read `dc_compact_membership_read_sharing_plan_20261104.md` and
`dc_compact_membership_read_port_audit_20261104.csv`.  The plan selects per-bank
M/S/O member-read sharing and explicitly preserves independently checked
C/F/B inputs, cross-bank capability, cycle behavior and suffix reads.
The authorized candidate implementation, local equivalence evidence and
isolated read-network screening status are tracked in
`dc_rd1_member_read_sharing_implementation_20261104.md`. It does not replace
the pending full-driver-repair result or establish complete DC/PPA closure.
The completed isolated screen records a 62.943% combinational-area reduction
for the M/S/O reader with a 0.056220-ns local path-delay increase; production
wrapper integration, storage/clock cost and complete Route-A timing remain
separate gates.

The complete generated input for the authorized RD1 integration run is frozen
in `dc_rd1_full_input_freeze_20261105.md`.  It records the 48-file successor,
unchanged Full-KV source and raw state, 5/5 proxy closure, archive hash and the
retained entry_id policy.  The freeze authorizes one same-fair-v1 paired run;
it is not a mapped-area or timing result.

The separately authorized complete paired-DC launch is recorded in
`dc_rd1_full_paired_dc_launch_20261105.md`.  Its active-run markers and final
native reports must be checked after user-reported completion; launch
liveness is not a result.

For the next independent Page Manager hotspot diagnosis, read
`dc_page_manager_p0_diagnosis_20261104.md` and
`dc_page_manager_p0_state_audit_20261104.csv`. The read-only saved-DDC query
finds the 36,720-bit allocated-line selector as the largest measured state/cone
and a global-WNS path, then selects an exact-priority realization screen as
PM1. It changes no RTL, proxy boundary, constraint or synthesis input.

For the authorized PM1 implementation and isolated selector screen, continue
with `dc_pm1_exact_priority_selector_implementation_20261104.md`. The candidate
retains all 36,720 bits and exact same-cycle lowest-index semantics, and passes
bounded exhaustive plus full-geometry directed/random checks. It is not wired
into production Page Manager. The two generated combinational selector tops
are only small-synthesis inputs; source size is not mapped area and a launch
is not a result. The first screen `pm1_selector_screen_20261104_r1` later
failed with a native DC `SIGSEGV` during Pass-1 mapping of the original side;
the candidate side was never attempted and no area/timing result exists.
The bounded successor is
`dc_pm1_registered_selector_successor_20261104.md`: it preserves both child
selector bodies, gives both the same Q/D register boundaries, isolates the two
DC processes and requires identical sequential counts. It is still an
isolated selector experiment, not production Page Manager integration.
Its completed r2 run is partial only: the unchanged original child again
segfaults in DC Pass-1 mapping, while the independently launched banked side
maps and emits native reports. The combined run fails and provides no matched
PM1 area/timing comparison.

The bounded production-module successor is
`dc_pm1_page_manager_integration_20261105.md`.  It adds a default-off Page
Manager realization parameter, enables PM1 only in the candidate test instance
and passes 5/5 real reclaim tests.  It deliberately defers mapped claims until
a saved-DDC replacement-readiness probe or later complete paired successor can
preserve a fair comparison context.

The saved-DDC prerequisite is closed by
`dc_pm1_saved_ddc_replacement_readiness_20261105.md`.  Its read-only probe
finds one independently addressable, unique, hierarchical mapped Page Manager
and recovers the exact allocated-line and reclaim-line boundary.  It permits a
future characterized bottom-up replacement screen but is not mapped candidate
evidence or a substitute for a complete top compile.

The concrete successor procedure is
`dc_pm1_characterized_replacement_plan_20261105.md`: emit a distinct but
port-identical PM1 Page Manager child, use fail-closed `change_link`, project
the real saved-top environment with `characterize`, and map only that child.
Any positive screen remains provisional until complete same-fair-v1 top DC.

For the specific cause of the residual M2/P3 area, read
`dc_compact_wrapper_hotspot_attribution_20261104.md`.  It cross-checks mapped
reference counts, separates membership sequential cells from overlapping
primitive cones, and routes the next candidate toward record-read/decode
implementation rather than assuming the priority selector explains all area.

For the approved entry_id driver repair, read
`dc_entry_id_driver_repair_20261104.md`.  It describes a synthesis-only,
explicit result-net preservation policy and a fail-closed 48-bit driver gate.
The focused DC regression and mapped simulation pass. Finish with
`dc_m2p3_entry_id_repair_result_20261105.md`: production paired DC closes both
side/outer markers and all 48 drivers while retaining the second optimization's
8.362% area reduction versus the first refinement. Timing and broad structural
cleanliness remain blocked.

The completed compact-membership native-DC result supersedes its active-run
snapshot: read `dc_m2_p3_wrapper_compact_membership_result_20261104.md` after
the P1 successor record.  It observes a further 8.313% mapped-area reduction
and the expected 76,032 sequential-cell reduction, but setup still fails and
new LINT-3/LINT-5 entry_id outputs block structural acceptance.  Diagnose that
driver/observability regression before another optimization or rerun.

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
