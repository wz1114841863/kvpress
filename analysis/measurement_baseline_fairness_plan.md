# MBR.1 — Paired Full-KV Measurement-Baseline Fairness Plan

**Status:** Baseline-planning record complete; **pending human MBR.1 review**
on 2026-10-16.  MBR.0's human PASS authorizes this plan only.  This document
does not create Full-KV RTL, select a synthesis top, select a macro, library,
clock, wrapper, controller, or numeric kernel, run synthesis, or make a PPA,
latency, throughput, energy, or net-benefit claim.

## Purpose and preconditions

MBR.1 names a fair *planning contour* for a later Full-KV comparison:
**`full_kv_measurement_control_cut`**.  It is paired with MBR.0's
`route_a_measurement_control_cut`; neither identifier is a current source top
or a declaration that a realizable top already exists.

The MBR.0 BOM has exactly one mapping for each of the 30 SRP partition
records, its human review passed after the three cost-evidence corrections,
and its next gate is now this plan.  The functional anchor remains `cf9f055`.
The MBR.1 machine-readable comparison matrix is
[`measurement_baseline_matrix.json`](measurement_baseline_matrix.json).

The following preconditions are deliberately retained rather than solved:

- `RouteAKVSubsystemTop` is still a composition-only skeleton and is not
  either measurement candidate.
- Functional memory, source-partial provider, R4 reference, fixtures,
  observers, and replay oracles remain outer/test-only evidence, never hidden
  DUT logic.
- SRP.5's future-top integration blocker remains open.  MBR.1 allocates the
  *responsibility* for the five integration categories, not their gates,
  muxes, state, wires, or area.
- The recovered A4.14.1 report is a conditional proxy/accounting constraint;
  it is not a physical cost result and its payload/metadata service
  coordinates remain non-additive.

## Paired semantic baseline

Full-KV is not defined by deleting Route-A signals from a witness.  Its
planning contour uses the same legal common lifecycle and source-service
semantics: common hot control, R2/R1 transaction control at `core_mem_if_v1`,
S2 `FILL -> READY -> four-consumer -> partial update -> release`, legal GQA,
reset/stale/fault exclusion, and terminal/retire discipline.  Per
[`architecture_spec.md`](architecture_spec.md), Full-KV has no Route-A
position sidecar or cross-source merge.

The common provision can cancel in a later differential result only after a
future implementation proves structural equivalence under the same selected
configuration.  In particular, a common label is not permission to omit its
activity or external memory service.

| Comparison rule | Required later proof | Forbidden shortcut |
|---|---|---|
| Common R6/hot/R2/R1/S2 provision | Same selected interface/reset semantics, GQA cardinality, storage-wrapper boundary, and live owner paths on both sides. | Charging the whole common provision to Route-A or cancelling it merely because class names look similar. |
| Route-A control/storage increment | A named implementation/proxy and SRP.3/SRP.4 evidence route for each record. | Treating an unimplemented wrapper, array, or external service as zero. |
| Differential activity | Owner-carried accepted event/counter with the fields needed by its cost row, or an approved supplementary route. | Inferring an action from private state, a fixture field, or absence of an event. |
| External service | A declared matching service/profile basis for both sides, with Route-A-specific descriptor/pending activity separately recorded. | Calling controller/PHY/CDC/calibration free, or adding metadata and payload coordinates as one latency/energy result. |
| Numeric/source partial | A separate R4 finite-conformance/cost route; common source PE scope remains external. | Counting a functional provider as an attention accelerator or setting merge activity to zero. |

## Differential accounting form

The following are placeholders for later evidence, not equations that produce
a number in MBR.1.  Area, static-power, and dynamic-energy/activity ledgers
must remain separate: no expression below permits adding unlike units.

```text
Area / implementation envelope (one selected library/constraint only):
  A_RouteA = A_common_paired
           + A_RA_control + A_RA_storage_proxy_or_wrapper
           + A_RA_R4_numeric_or_partial_state
           + A_RA_integration_shell[mixed common/differential]
           + A_RA_external_service_or_proxy                 (each unresolved term is nonzero)
  A_FullKV = A_common_paired + A_FullKV_only_control
           + A_FullKV_integration_shell[mixed common/differential]
           + A_FullKV_external_service_or_proxy             (each unresolved term is nonzero)
  Delta_A  = evidence-complete, like-for-like terms only.

Dynamic-energy / activity envelope (one declared workload/service profile only):
  E_RA = E_common_path + E_RA_control_events + E_RA_storage_accesses
       + E_RA_R4_numeric_events + E_RA_source_partial_delta_events
       + E_RA_integration_activity + E_RA_external_service   (each unresolved term is nonzero)
  E_FK = E_common_path + E_FullKV_only_events
       + E_FullKV_integration_activity + E_FullKV_external_service
  Delta_E = evidence-complete, same-profile event/service terms only.
```

`A_RA_R4_numeric_or_partial_state` is a separate numeric-realization/proxy
envelope, not the full attention PE.  Likewise,
`E_RA_source_partial_delta_events` is only the named Route-A differential at
the outer partial interface; it cannot charge or cancel the complete source
PE without a separately declared common profile.  No MBR.1 row permits a
numeric difference.  A row whose action lacks a complete carrier remains
`unresolved evidence`; it does not disappear from a future ledger.  Payload
and metadata coordinates are retained separately, so this plan cannot derive
system latency, throughput, energy, or net benefit.

## Future-top integration allocation

MBR.0's five deferred categories are now assigned an evidence responsibility.
The assignment is conditional until a future top/BOM proves the indicated
equivalence; it makes no new hardware selection.

| Deferred integration category | Fairness allocation rule | Required later evidence |
|---|---|---|
| Interface adaptation | Pair only the identical `core_mem_if_v1`/common interfaces; Route-A-only packed, descriptor, sidecar, and direct-pending adaptation is differential. | Future top port/BOM mapping and semantic regression. |
| Reset/init gating | Pair common R1/R2/S2 lifecycle reset; R3/M2/P3/R5 and packed-path reset state is Route-A differential. | Reset-domain/initialization mapping and stale-response regression. |
| Protocol fanout/muxing | Pair only demonstrated common transaction/source paths; packed/direct/sidecar routing fanout is Route-A differential. | Live owner connectivity and a future top netlist/BOM review. |
| Delivery-context connectivity | A common Full-KV context may be paired only after its owner/type mapping is explicit; packed/direct source-class context is Route-A differential. | Context schema/owner mapping and accepted-carrier activity route. |
| Logical-storage-wrapper adapters | Pair an identical common S2 payload wrapper only; M2/P3/R5/sidecar wrappers and their peripherals are Route-A differential. | Physical-wrapper mapping plus frozen semantic regression. |

`deferred_unestimated` therefore remains the cost-evidence status for the
future integration shell.  Its whole-record classification is **mixed
common/differential, deferred**: the five allocations identify conditional
subterms but do not permit treating either future top's shell as wholly
Route-A incremental.  The matrix records this conditional allocation; it does
not convert it into an estimate.

## Record-level comparison treatment

The matrix maps all 30 SRP records exactly once.  It distinguishes four
things that must not be collapsed: paired common provision, Route-A
incremental control/storage, differential activity needing an owner event,
and external service needing a same-profile or separate evidence route.
Test/reference records are excluded from both candidate DUTs and may only
validate a replacement.

Important boundary cases are explicit:

- M2 fixed provision and its head/span control proxy may inherit the recovered
  A4.14.1 accounting context, but queue/staging dynamic access, other control
  activity, and a real wrapper are still omitted pending evidence.
- P3 pending backing and R5 descriptors use external declared service routes;
  they do not make HBM/controller/PHY/CDC/calibration zero.  P3 staging,
  R5 availability, and S2 payload/sidecar arrays may later use an
  array-only proxy, while their control/peripherals remain inside the control
  candidate.
- R4 structural control is a Route-A increment.  R4 numeric/partial state
  and source partial remain separate external evidence.  A full attention PE
  is not required for this paper boundary, but a credible Route-A differential
  numerical/activity route is required before cost evidence.

## MBR.1 review gate and non-claims

A human MBR.1 review must confirm that the Full-KV planning contour retains
the same common semantics, no common provision is prematurely cancelled, all
five future-top categories have a conditional common/differential allocation,
and every external or missing event has a route or a stop-for-review state.
It must also confirm that this plan has not selected a future top or widened
the work into a controller, attention accelerator, synthesis, or PPA flow.

Passing MBR.1 may authorize only the next separately reviewed measurement or
realization-choice proposal named by that review.  It cannot by itself create
RTL, choose physical realization, or support a performance conclusion.

The separately approval-gated candidate preparation supplement is
[`measurement_realization_candidate_proposal.md`](measurement_realization_candidate_proposal.md).
It records no implementation choice and does not alter this pending MBR.1
review disposition.
