# SRP.4 — Differential Cost Evidence Plan

**Status:** Complete at evidence-planning scope on 2026-10-15.  This record
maps Route-A cost-bearing functions to the accepted A4.14.1 ledger or to an
explicit remaining evidence gap, ranks the least-cost follow-up evidence, and
sets stop conditions.  It does not rerun A4, recover or rewrite a frozen
report, select an implementation, perform synthesis, or derive a new cost,
PPA, latency, throughput, or net-benefit result.

## Accounting authority and provenance limit

The accounting authority is the accepted A4.14.1 report hash
`0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb`, its
contract, and the architecture specification.  The current live tree does not
contain the ignored materialized report at
`analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/`; therefore
SRP.4 does **not** claim to have re-hashed its bytes or rechecked its numerical
rows.  The accepted hash was byte-verified remotely in
[`architecture_gate_a0_remote_report_verification_20260928.md`](architecture_gate_a0_remote_report_verification_20260928.md).

This plan uses that accepted provenance only to classify coverage.  Before any
future numerical comparison, the exact report and all required inputs must be
made available read-only and hash-verified again.  The A4.14.1 differential
omitted-cost budgets (retrieval 27.646, summarization 40.498, reasoning
167.442 mJ/request) remain constraints, not newly checked results or free-cost
allowances.  Payload and metadata service coordinates remain non-additive.

## Coverage vocabulary

- **A4-accounted proxy:** the accepted ledger explicitly includes a declared
  HBM/service or public-CACTI proxy term.  It is not measured physical cost.
- **Partially covered:** bytes, capacity, or action interface is represented,
  while implementation dynamic energy, storage, controller, or control cost
  is still omitted.
- **Explicitly unestimated:** A4.14.1 names the term as omitted; it is neither
  zero nor already inside the Route-A total.
- **Common/not incremental:** provision belongs to fair Full-KV and Route-A
  jointly and must not be charged wholesale to Route-A.  This does not make
  its path-specific activity free.
- **Verification-only/not applicable:** no paper hardware cost can be assigned.

## Differential cost mapping

Every partition record appears exactly once below.  “Full-KV basis” states the
comparison rule, not a claim that an omitted Full-KV term is zero.

| Cost-bearing scope and partition IDs | A4.14.1 coverage status | Full-KV basis and double-counting rule | Remaining evidence gap | Least-cost future verification method | Priority |
|---|---|---|---|---|---|
| Future integration shell: `top_future_synthesis_boundary` | Verification-only/not applicable. | No area/control is assigned until a future DUT boundary is approved. | Future-top membership and integration overhead. | Keep excluded from ledger; require an explicit future-top bill of materials before any synthesis comparison. | Gate |
| Common lifecycle/hot/R1/R2 control: `r6_common_lifecycle_control`, `common_hot_residency_control`, `r2_shared_arbitration_control`, `r1_core_transaction_control` | Common/not incremental; no standalone A4 physical-control term. | Baseline control is shared; do not charge it as Route-A increment. Future absolute-system evidence must use one identical baseline. | Differential transactions/control toggles caused by Route-A. | Accepted-carrier action inventory, compared against the same Full-KV interface events; do not infer gates/energy from a Chisel module. | P4 |
| Common S2 payload/GQA: `s2_common_payload_gqa_control` | A4-accounted proxy for the two-page S2 source-buffer provision and path activity. | Fixed S2 proxy area appears once as common infrastructure; Route-A receives only its path activity. | Chosen macro/ports/clock and any physical activity calibration. | Retain A4.13.5/A4.14.1 common-versus-path split; after a separate choice, compare identical Full-KV/Route-A wrapper access counts. | P3 |
| Route-A control and differential activity: `r6_route_a_packed_activity`, `direct_pending_transport_control`, `shared_delivery_context_state`, `typed_read_delivery_control`, `r3_materialization_publication_control`, `packed_read_activation_and_demand_control`, `p3_wrapper_control`, `r5_allocator_reclaim_control`, `packed_s2_read_ingress_control`, `r4_structural_merge_control`, `r6_component_status_collection` | Explicitly unestimated control activity.  Some payload movement is covered elsewhere; no control implementation energy/area is implied. | Compare accepted Route-A-only events with an explicitly named Full-KV counterpart or record that no counterpart exists; never charge shared R1/R2/R6 provision twice. | FSM/state, association, arbitration-adapter, and status-collection dynamic/area. | One owner-carried event taxonomy and counter map, then a future wrapper-level toggle/access map after the DUT boundary is approved. | P4 |
| M2 fixed provision and head/span control entry: `m2_control_protocol`, `m2_storage_realization` | A4-accounted proxy: M2 fixed public-CACTI provision once and A4.14.0 head/span control-entry accesses. | Route-A incremental M2 fixed provision is not multiplied by workload.  Do not label control-entry proxy as total M2 dynamic energy. | Queue/staging dynamic accesses, exact storage realization, and control-wrapper cost. | Reconstruct only accepted M2 operation/publish and queue/staging event classes from frozen traces; retain existing proxy as prior evidence, then require a selected-wrapper access map. | P1 |
| M2 functional reference: `m2_reference_provider` | Verification-only/not applicable. | Never treated as M2 hardware or an incremental baseline. | Replacement provenance only. | Preserve existing regression boundary; no cost row. | Excluded |
| P3 pending backing: `p3_pending_hbm_backing` | Partially covered: A4 payload service models P3 admission movement/traffic under declared profiles. | Compare fair Full-KV/Route-A payload service under the same declared profile; pending backing/controller are not free. | Controller/PHY/CDC, mapping, physical HBM cost, and transport-control cost. | Re-hash accepted A4 inputs; make a request/byte/terminal-class map at `core_mem_if_v1`; later bind one declared external-service model without changing request semantics. | P2 |
| P3 staging: `p3_payload_stage_page` | Explicitly unestimated: fixed 1,179,648-B envelope is deterministic capacity only. | Route-A incremental; do not add it to S2, pending backing, or payload page capacity. | Stage macro area, fill/read/write/release dynamic accesses, and physical placement. | Derive exact stage fill/read/write/release counts from existing accepted R3 owner events, then evaluate one separately approved storage proxy/wrapper against those counts. | P1 |
| R5 availability/active state: `r5_availability_state` | Explicitly unestimated. | Route-A incremental; PageRef generation/availability is not part of payload HBM or M2 entry proxy. | On-chip allocator/stream-state capacity and dynamic accesses. | Count allocate, tail update, invalidation, generation advance, and free only from accepted R5 owner events; bind later to an approved storage/control candidate. | P2 |
| R5 descriptor region and maintenance: `r5_descriptor_hbm_region` | Explicitly unestimated.  The descriptor capacity/interface is known, but A4 does not charge maintenance traffic/dynamic energy. | External-system service; descriptor region remains separate from the cold-payload pool and must not become a payload-read class. | Descriptor read/write/invalidate service, controller energy, cache/mapping, and external storage cost. | Replay the existing exactly-one `desc_maint_write`, descriptor-visibility, invalidate, free, and retire events into a descriptor transaction taxonomy; only later choose a service proxy. | P1 |
| Packed sidecar/page management: `s2_incremental_sidecar_storage` | Partially covered: A4 carries 512-B sidecar transfer capacity/bytes; sidecar latch/storage and page management are explicitly unestimated. | Route-A incremental; do not fold sidecar storage into common 32-KiB S2 payload. | Sidecar storage/access and page-manager physical control. | Use immutable page association to count sidecar fill/read/release events; pair with the P3/R5 event taxonomy, then assess one approved storage/control candidate. | P2 |
| R4 numeric and partial state: `r4_numeric_partial_state`, `outer_attention_partial_provider` | Explicitly unestimated.  A4 records partial-state interface/actions but not arithmetic, partial RF/SRAM/spill, interconnect, or outer provider/PE cost. | Route-A pays only incremental cross-source merge work; do not charge the whole common attention MAC array. | Numeric implementation, partial-state placement, merge arithmetic/interconnect, and differential outer-provider activity. | First preserve finite binary32/fault conformance while producing a source/subset/partial-state action inventory; a cost proxy requires a separately approved numeric realization candidate. | P1 |
| External memory service: `external_memory_service` | Partially covered only for declared payload service energy/traffic; controller/PHY/interconnect/clock/wire/leakage and HBM physical area are explicitly unestimated. | Use the same declared profile for Full-KV and Route-A traffic; never report external memory as zero cost or a native HBM controller. | External-service calibration, controller/CDC/physical energy and area. | Contract-level request/response class and byte inventory first; then decide whether a calibrated external model is credible enough for the paper before local controller work. | P2 |
| Test-only infrastructure: `functional_sidecar_delivery_reference`, `testbench_observers_fixtures_and_oracles` | Verification-only/not applicable. | Excluded on both sides. | None; cannot substitute for a cost row. | Enforce exclusion in every later bill of materials. | Excluded |

The machine record enforces exactly-one mapping for all partition IDs.

## Priority and lowest-cost validation sequence

P1 is the first risk screen because these terms are both Route-A-specific and
wholly absent from accounted dynamic energy: M2 queue/staging accesses, P3 stage
accesses, R5 descriptor maintenance, and R4 numeric/partial state.
Their first step is **not** synthesis: reuse only existing immutable owner
events or frozen trace inputs to build an action taxonomy with identity,
accepted-event, and Full-KV-basis labels.  If an event lacks an owner-carried
field, it remains uncounted rather than inferred from private state.

P2 then establishes the same action/byte taxonomy for pending/external memory,
R5 availability, and sidecar/page management.  It identifies what a future
external-service or storage candidate must explain, but selects neither.

P3 verifies the common S2 accounting split once a common-storage candidate is
separately authorized.  P4 covers residual Route-A control and shared
differential activity only after the higher-risk omissions have a credible
route.  Any P1--P4 result that cannot retain the A4.14.1 omitted-cost
constraint, preserve the frozen semantics, or avoid double counting stops for
an independent feasibility/scope review; it never changes pruning, admission,
pages, scheduler, or publication semantics.

## SRP.4 completion boundary

SRP.4 completes only the evidence plan: all 30 partition records are mapped;
the A4-accounted, partial, unestimated, common, and verification-only cases
are explicit; and each unresolved Route-A cost has a minimum future method and
priority.  No cost quantity is added to the ledger, and no budget pass/fail is
recomputed.

The next planning gate is SRP.5 Completion Review.  A later realization-choice
stage still requires explicit human approval and must first satisfy the
ownership, logical-contract, physical-wrapper, and cost-evidence conditions
recorded by SRP.3 and SRP.4.
