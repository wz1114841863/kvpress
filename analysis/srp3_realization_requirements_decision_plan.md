# SRP.3 — Realization Requirements & Decision Planning

**Status:** Complete at requirements-planning scope on 2026-10-15.  This
record identifies required observable behavior, unresolved realization choices,
future evidence, and stop conditions.  It selects no memory macro, port/bank
organization, HBM controller/protocol, numeric implementation, pipeline,
frequency, timing, PPA result, or realized DUT.

## Purpose and anchors

SRP.3 converts the unresolved items identified by SRP.2 into an explicit
decision register.  It does not implement those items.  Its source-planning
anchor is clean commit `acf6cf9`; functional semantics remain anchored at
`cf9f055` and the architecture/accounting authority remains
[`architecture_spec.md`](architecture_spec.md), including the A4.14.1
omitted-cost constraint.

The nine records below are exactly the SRP.2 records whose semantic mapping is
due in SRP.3.  Other control records retain their SRP.2 source-level status;
this plan neither promotes them to a synthesis DUT nor adds a realization
candidate.

## Non-negotiable requirements for every later choice

Every later memory, wrapper, or numeric candidate shall preserve the frozen
valid/ready nonmutation, identity/incarnation/generation, reset/stale/fault,
single `metadata_publish_commit`, no-early-packed-read, four-consumer release,
terminal, descriptor-invalidate-before-free, and retire-ack contracts.  A
functional environment or test-only fixture cannot become the implementation
merely by satisfying a directed test.

The following are not choices in this phase: original mask and post-decision
admission, 64-token pages, M2 organization, P3/S2 mapping, legal four-member
GQA association, FIFO/scheduler semantics, and one atomic publication.  The
512-bit core fragment and 256-B accounting beat remain distinct logical
interfaces; neither selects an HBM command or burst.

## Requirement and decision register

| ID | Required observable behavior and fixed capacity/interface | Still unresolved; no selection made | Candidate evidence before a later decision | Stop-for-review condition |
|---|---|---|---|---|
| `m2_storage_realization` | Preserve eight head-affine logical banks; two 1RW `head_control` replicas and one 1RW `span_owner` store per bank; atomic mirrored head update; both frozen member results before staging/publication; ready-low and reset nonmutation. | Macro/wrapper form, physical ports, coherence implementation, queue/staging access mapping, latency, and placement. | Contract-driven replacement test at `m2_op_req/op_rsp` and publish boundaries; capacity/access reconciliation to A4.12/A4.14.0; future cost row in SRP.4. | A candidate exposes a private member, weakens atomic RMW, treats abstract 2/2/2 as physical ports, or leaves queue/staging cost unaccounted. |
| `p3_pending_hbm_backing` | Remain the unique authoritative pending K/V source until the associated atomic publication; preserve `core_mem_if_v1` identity, ordered fragments, payload-durable outcome, stale/fault exclusion, and reset `mem_init_done` gate. | Controller/PHY/CDC, address mapping, transaction/burst form, ECC/retry/timeout, service rate, and physical HBM evidence. | Adapter conformance under accepted request/response/fault/reset traces; separately declared external-service model; SRP.4 cost provenance. | An adapter changes authority before publication, turns a fault into a retry/fallback semantic change, or lacks both a replacement contract and a cost route. |
| `p3_payload_stage_page` | Exactly one transient 64-record/32,768-B payload stage per anchor layer; separate 8-B sidecar per valid record; `RESERVED -> COMPLETE -> DURABLE` only after exact eight 64-B fragments per member, sidecar binding, and write durability; never authoritative. | Storage primitive, ports, access/reorder policy, physical location, dynamic energy, and non-anchor scaling. | Wrapper-level fill/write/release and stale/fault regression against R3 contracts; capacity and action provenance from A4.13.1/P3; future storage/dynamic evidence in SRP.4. | A proposal creates a second residency, permits stage completeness without sidecar or all fragments, or cannot preserve release only at publication. |
| `r5_availability_state` | Preserve 288 96-bit active stream descriptors, 18,360-B availability state, 18-bit page ID plus 8-bit generation, unique owner, quiescence-before-reuse, reset/init isolation, and invalidate-before-free. | On-chip state primitive, banking/ports, allocator microarchitecture, timing, and dynamic accesses. | Allocation/reclaim/reuse regression using accepted owner carriers; capacity mapping and explicit future access accounting. | Generation/reuse can admit a stale reference, free precedes durable invalidation/drain, or the shared pool is silently charged as Route-A-only. |
| `r5_descriptor_hbm_region` | Preserve 146,880 128-bit descriptors in the separate 2,350,080-B region, four entries per 64-B line, and at most two private exactly-one `desc_maint_write` operations per append before the one publication event. | HBM mapping/controller service, descriptor caching, write issue timing, ECC/retry policy, and physical cost. | Descriptor-line protocol/replay plus publication and retirement regressions; external-service and differential-cost plan in SRP.4. | Descriptor visibility precedes publication, descriptor maintenance becomes a payload-read scheduler class, or invalidate/free ordering is weakened. |
| `s2_common_payload_gqa_control` | Preserve two common 32,768-B payload slots, matching fill association, `READY` only after complete matching payload terminal(s), four exact GQA consumer partial updates before release, and common Full-KV/Route-A ownership. | Common storage macro/ports, arbitration, fill/consume overlap realization, clocking, and access energy. | Shared-path wrapper conformance for Full-KV and Route-A; future common-baseline evidence, with path activity separated in SRP.4. | The whole S2 provision is charged to Route-A, `READY` is asserted early, or release precedes any consumer commit. |
| `s2_incremental_sidecar_storage` | Preserve a distinct 512-B full-page (8-B/valid-record) sidecar bound to the immutable packed-page association; no S2 `READY` until payload and sidecar complete; no sidecar creation by endpoint. | Sidecar storage/latch/macro form, porting, placement, dynamic accesses, and non-anchor size. | Packed fill/sidecar association and stale/fault regression; explicit incremental storage/access evidence in SRP.4. | A candidate folds sidecar into the 32-KiB payload capacity without accounting, fabricates positions, or makes `READY` without complete sidecar. |
| `r4_numeric_partial_state` | Preserve canonical `hot -> pending -> packed` order; four consumer partial interfaces of binary32 `(m,l,o[127:0])`; observable binary32/RNE results and stated tolerance; `l > 0` normalization; exactly-one R6 `numeric_fault` with no output/fallback on nonfinite, overflow, or invalid `l`; account for the 2,080-B logical group partial state if materialized or spilled. | Exp/arithmetics design, internal precision, pipeline/register placement, partial-state RF/SRAM/spill, latency, throughput, and numeric dynamic cost. | Finite conformance suite from `architecture_gate_a_r4_numeric_merge_contract.md`, including subset/malformed/overflow tests, plus a state-placement cost/evidence plan. | Any candidate changes source order, broadens numeric tolerance without a specification revision, treats partial state as free, or cannot retain fault/terminal semantics. |
| `external_memory_service` | Preserve synchronous `core_mem_if_v1` core-side contract, four-live-read/one-live-write anchor limits, ordered fragments per identity, exactly-one terminal result, stale-response suppression, and reset `adapter_epoch_ready -> mem_init_done`. | External controller/protocol/CDC, physical clock relation, sustained service, address translation, and physical HBM cost. | Contract adapter verification with explicit environment assumptions; later calibrated/declarative service evidence and cost reconciliation. | A future environment assumes away stale/fault/reset behavior, relies on test-only reference as a controller, or reports an external service as zero cost. |

## Evidence discipline and decision gates

The next, separately authorized realization-choice review must consider one
record at a time and record: (1) the candidate's exact wrapper/port mapping,
(2) its frozen-contract regression route, (3) capacity and access assumptions,
(4) cost ownership and non-duplication rule, and (5) which evidence is still
modelled rather than measured.  It may decide no more than one of the listed
unresolved categories at a time; a choice for one record does not implicitly
choose a controller, macro, numeric pipeline, or future synthesis top for any
other record.

Existing A4 proxies are admissible only as named prior evidence: A4.14.0's M2
proxy is not a selected M2 implementation, and A4.13.5's source-buffer proxy
is not a selected S2 macro.  The A4.14.1 payload and metadata service
coordinates remain non-additive.  SRP.4 must map every unestimated
differential term against its omitted-cost budget; SRP.3 does not calculate or
pass that budget.

## Completion and next authorization

All nine SRP.3-due records now have a semantic requirement, unresolved-choice
list, evidence route, and stop condition.  This completes requirements and
decision planning only.  It authorizes no RTL/wrapper implementation,
synthesis, timing/PPA, physical-cost conclusion, or numeric/memory choice.

The next allowed planning activity is SRP.4 — Differential Cost Evidence Plan.
It must retain this register and cannot reinterpret an absent physical choice
as zero cost.
