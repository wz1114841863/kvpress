# Realization preparation — wrapper-interface and common-equivalence disposition

**Status:** `human_approved_wrapper_rtl_in_progress` (2026-10-25).  This is
the first decision package after the conditional synthesis-top selection.  It
turns the four MR-2 logical array boundaries and the frozen dual-DUT cut into
an implementable wrapper plan.  The M2 parent-side adapter RTL has passed its
remote directed and 10-suite cross-stage regression on successor `3f3a489`.
The R5 parent-side adapter is functionally verified on the current bounded
contour; P3 and S2 wrapper RTL remain pending. No macro, port count, clock,
library, controller, numeric unit, DC, CACTI, PPA, area, energy, or performance
result is selected or claimed.

## Decision scope and inputs

The two conditional control-top projections remain
`RouteAMeasurementDut` and `FullKVMeasurementDut`, as selected in
[`synthesis_top_candidate_selection_review.md`](synthesis_top_candidate_selection_review.md).
`RouteAKVSubsystemTop` remains rejected.  This package uses the actual
measurement-cut source/port freeze, the four MR-2 logical boundary contracts,
SRP.3 requirements, and SRP.4's unestimated-cost ledger:

- [`measurement_dut_cut_freeze_20261025.md`](measurement_dut_cut_freeze_20261025.md);
- [`mr2_m2_array_boundary_contract.md`](mr2_m2_array_boundary_contract.md),
  [`mr2_p3_array_boundary_contract.md`](mr2_p3_array_boundary_contract.md),
  [`mr2_s2_array_boundary_contract.md`](mr2_s2_array_boundary_contract.md),
  and [`mr2_r5_availability_array_boundary_contract.md`](mr2_r5_availability_array_boundary_contract.md);
- [`srp3_realization_requirements_decision_plan.md`](srp3_realization_requirements_decision_plan.md)
  and [`srp4_differential_cost_evidence_plan.md`](srp4_differential_cost_evidence_plan.md).

An **access contract** below is a typed, clocked semantic request/response
contract to be implemented by a later adapter.  It is not a selected SRAM or
HBM pinout.  “Bounded response” means the wrapper must preserve upstream
ready/valid holding and return an explicit success/fault response; it does
not choose a number of cycles, clock, frequency, pipeline, or CDC scheme.

## Proposed wrapper-interface dispositions

| Interior | Required logical access contract for later adapter | Parent/peripheral that stays in the candidate DUT | Timing, reset, and fault rule | Cost disposition |
| --- | --- | --- | --- | --- |
| M2 head/span entries | `m2_entry_access_v1`: one registered keyed head `lookup` request/response plus independent `publication_commit` and `handoff_release` lanes with exact write acknowledgements. | `RouteAM2ProductionControlOwner`: membership and credit, slot/generation, RMW lowering, private prepare/abort, two member responses, atomic publication resolution, and handoff qualification. | The lookup response holds under backpressure. Both head replicas plus the paired span update are one all-or-nothing logical commit. Publication/handoff have distinct-lane non-alias assertion; their acks cannot revise already accepted R3/R6 decisions. Reset clears the interior and parent private state. | Route-A incremental. Array interior **and** adapter/lookup/commit buffering/provenance-index peripheral are `unestimated_not_zero`; only the interior may later be macro/proxy. |
| P3 payload stage and sidecar | `p3_stage_access_v1`: tagged payload write, sidecar write, and payload read/response. Every tag carries layer plus fragment or record ordinal; a read response is identity-tagged. | `RouteAM2P3Wrapper`: claim/generation, accepted-binding ledger, exact ordering, materializer reservation, durable packed write, publication and release. | A fill/read access may stall but cannot reorder, forge completion, or cause `COMPLETE`/`DURABLE`. Child reset does not relax the parent `mem_init_done`, stale, or fault gates. | Route-A incremental P3 stage interior and adapter are `unestimated_not_zero`. Pending backing is a separate external service, not this wrapper. |
| S2 payload (both contours) and Route-A sidecar | `s2_payload_access_v1`: tagged payload fill/write and payload read/response; Route-A additionally needs `s2_sidecar_access_v1` for sidecar write/read. Each response carries slot/generation and is held under downstream backpressure. | Route-A `RouteAS2GqaSourceWrapper`: fill-open, READY, four commits, release, drain; Full-KV `FullKVS2GqaSourceWrapper`: baseline-local fill/READY/four commits/release/fault. | `READY` remains parent-owned and occurs only after matching terminal/complete conditions. Read data may be released only after matching READY validation; reset/stale/fault are fail-closed. The current Full-KV class tracks completion but has no payload-read array interface, so it is **not yet** an equivalent implementation of `s2_payload_access_v1`. | Route-A sidecar is incremental and unestimated. Payload is not cancellable today; physical common treatment requires a successor Full-KV payload-wrapper implementation and conformance evidence. |
| R5 availability/generation | `r5_availability_access_v1`: parent-owned availability lookup/read response, allocation-update acknowledgement, and typed multi-lane reclaim/generation-update acknowledgement. The descriptor image is excluded. | `RouteAPageManager`: free-page selection, PageRef formation/validation, descriptor visibility, invalidate-before-free, reclaim sequencing, drain/reset, and descriptor-service traffic. | Allocation is not outwardly accepted until its matching availability update succeeds. Reclaim cannot make a page reusable until the matching lane updates and generation advance succeed. Stale/fault/reset leaves the old state unavailable or aborts the request; wrapper never owns page selection. | Route-A incremental availability interior plus scan/lookup/update adapter/peripheral are `unestimated_not_zero`. Descriptor maintenance remains an external-memory service, never a local SRAM proxy. |

### Required implementation consequence

The earlier M2 and R5 functional children exposed whole-array views to their
parents. The implemented M2 and R5 parent adapters replace those views with
typed access carriers; P3/S2 remain to be implemented. A physical-array
replacement cannot retain a whole-array form as a black-box
port without charging a wide snapshot/mux network or changing control
ownership.  The proposed `m2_entry_access_v1` and `r5_availability_access_v1`
therefore require a later, explicit parent-side lookup/update adapter.  That
adapter is inside the corresponding candidate DUT, preserves the parent as the
decision owner, and must be costed.  It is not permission to put a scheduler,
allocator, or authority owner inside a storage macro.

For all four interiors, the future wrapper RTL shall use the candidate top's
ordinary reset as its reset domain and must retain the existing
`core_mem_if_v1.init_ack`/`mem_init_done` functional initialization gates.
Any distinct clock, asynchronous reset, or CDC requires a separate approval;
none is selected here.

## Common-equivalence disposition

The following is the proposed accounting rule for the exact frozen source
contours.  “Eligible common” means a later paired netlist may compare the
logic only after identical configuration, wrapper, reset, and semantic
regression evidence.  It is not a current cancellation.

| Provision | Actual source evidence | Proposed disposition | Required proof before any cancellation |
| --- | --- | --- | --- |
| R2/R1 core transaction path | Both tops instantiate `RouteACoreSideArbiter`, `RouteACoreMemIfV1`, `RouteADeliveryContextRegistry`, and `RouteATypedDeliveryRouter`, and expose `core_mem_if_v1`. | `eligible_common_after_identical_shell`. Route-A-only sidebands in the shared arbiter/router are a Route-A differential adaptation unless proven optimized/identical by the future paired shell. | Same parameters, reset/init behavior, external-memory profile, live producer/consumer paths, and successor structural/semantic regression. |
| Delivery-context connectivity | Registry/router classes are shared, but `FullKVDeliveryContextBridge` and `RouteAUnifiedDeliveryContextAllocationBridge` are not the same class or route set. | Registry/router only are eligible-common; bridge-specific allocation/release muxing is separately charged to its owning contour until a paired mapping exists. | Exact context schema, allocation/release identity, reset/reuse and live route map. |
| S2 payload/GQA | Both own read-to-READY, four consumer commits, and release, but classes/interfaces differ; Full-KV currently lacks the Route-A payload-read storage access boundary. | `noncancellable_pending_full_kv_payload_wrapper`. Do not charge all S2 to Route-A, but do not cancel it from the pair yet. | A common `s2_payload_access_v1` implementation, equal GQA/reset/fault contracts, and access-map comparison in both tops. |
| Lifecycle/status | Both enforce init, stale/fault terminal, retire, and drain responsibilities; Route-A uses R6/lifecycle/status classes while Full-KV is baseline-local. | `noncancellable_paired_semantics`. Keep each contour's lifecycle/status logic in its own BOM until a future shared wrapper or a demonstrated equivalent implementation exists. | One explicit lifecycle/status conformance map, including terminal ownership, drain ordering, reset, and stale/fault behavior. |
| Hot residency | `RouteAHotSourcePath` exists only in Route-A's actual source list. | `route_a_differential_for_current_pair`. Do not invent a Full-KV hot module merely to cancel cost. A later change requires a successor measurement-cut freeze and a separate fairness decision. | None for the current differential classification; any future common claim needs a legal Full-KV counterpart and identical behavior. |
| R3/M2/P3/R5, packed/direct/sidecar, R4 structural merge | Present only in Route-A. | Route-A incremental. | No cancellation; retain each unresolved row as nonzero. |

This deliberately does not call a class “common” merely because both logical
systems eventually deliver a source to four consumers.  It also prevents a
fake Full-KV hot path from being introduced just for a favorable subtraction.

## Synthesis-shell cost and interface plan

The future top projection must retain all live outer contracts in the
measurement-cut freeze.  The shell is a costed design object; it cannot be
treated as an empty test harness.

| Shell category | Concrete boundary to plan | Proposed allocation and evidence state |
| --- | --- | --- |
| Interface adaptation | `core_mem_if_v1`; Route-A lifecycle/source/partial/R4 boundaries; Full-KV read-work/consumer/terminal boundaries. | Mixed common/differential, `unestimated_not_zero`. Only the identical core-memory mapping can later be common. |
| Reset/init gating | Candidate top reset plus `core_mem_if_v1.init_ack`, `mem_init_done`, stale-response epoch and drain/retire sequencing. | Common only where the final R1/R2 path is identical; lifecycle/S2-specific gates remain per-contour pending equivalence. |
| Protocol fanout and muxing | Route-A R2 read/write classes, packed/direct/sidecar demux, R3/R5 ownership joins; Full-KV read-only route. | Count every retained mux/fanout in the corresponding top. Do not suppress Route-A-only inputs merely because an inactive skeleton once tied them off. |
| Delivery-context connectivity | Shared registry/router plus each contour's bridge and endpoint targets. | Registry/router potentially common; bridge, endpoint routing and Route-A packed/direct target fanout are individually classified until proven identical. |
| Storage-wrapper adapters | Four access contracts above, including M2/R5 view-to-lookup lowering and P3/S2 tags/response holding. | M2/P3/R5 and Route-A sidecar are Route-A incremental. S2 payload is pending paired proof. All are unestimated, not zero. |

The future source/filelist package must explicitly list parent RTL, the chosen
array wrapper, external-service stubs, and excluded functional reference
boundaries.  It must not import `RouteAFunctionalSidecarDeliveryAdapter`,
`RouteAFunctionalPartialProviderBoundary`, or `RouteAFunctionalR4ReferenceBoundary`
as synthesized hardware merely to make elaboration succeed.

## R4 and external-service cost responsibility

| Boundary | What stays outside the candidate control RTL | Mandatory nonzero accounting treatment before a net-benefit claim |
| --- | --- | --- |
| R4 numeric / partial state | Attention MAC array, numeric partial-state storage/placement, ordered merge arithmetic, exp/normalization implementation, and outer-provider interconnect. The candidate retains only structural packet/commit/terminal control. | `r4_numeric_partial_state` and `outer_attention_partial_provider` remain Route-A differential `unestimated_not_zero`. Any later implementation must preserve finite binary32/fault conformance and use the four-consumer, at-most-three-source canonical action inventory; it may not charge a complete attention PE to Route-A. |
| Core memory service | Native HBM controller, PHY, CDC, address mapping, timing/service guarantee, physical HBM area, and controller/wire/clock energy. | `external_memory_service` remains an explicit external-system cost with the same declared service profile for both tops. It is partially represented by A4 traffic evidence, never zero and never a synthesized controller claim. |
| P3 pending backing | Pending payload backing and its identity/fault/stale service. | Separate Route-A external service; do not merge it into the P3 stage array or treat it as free. |
| R5 descriptor region | Descriptor maintenance/read/invalidate service. | Separate Route-A external descriptor service; not an R5 local array proxy and not a payload-read class. |

## Approval gate and successor work

The approved dispositions authorize **only** a wrapper-RTL work package with
these order constraints:

1. implement typed parent-side adapters and preserve each named parent owner;
2. close the Full-KV S2 payload-wrapper choice or retain it as a non-cancelled
   paired provision;
3. create a successor source/port/filelist freeze and run owner, reset/stale,
   atomicity, and paired-cut regressions; then
4. prepare (not run) the dual-top synthesis input package for a separately
   authorized DC feasibility step.

It does **not** authorize macro selection, a physical timing/clock choice,
numeric realization, external controller, DC, CACTI, PPA, or a quantitative
cost conclusion.  Before approval, this record is a precise implementation
proposal rather than a realization decision.
