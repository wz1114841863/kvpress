# Gate-A Reviewer record 01 — overall architecture review

## Status, authority, and disposition

**Status:** `review_in_progress; semantic_pass; finite_anchor_pass;
r1_r3_r5_closed; r4_r6_blocked; realization_sufficiency_blocked; gate_a_not_passed`.

This is the first no-model Gate-A reviewer record after A0--A3.  It performs
architecture/provenance review only.  It neither creates a new A4 DSE nor
authorizes RTL, Chisel, PDK/PPA, a physical macro, a native HBM controller, or
a performance claim.

The reviewed finite anchor is
`rtl_entry_qwen3_8b_32k_s1_v1`.  Its parameter schema uses a
retention/lifecycle-facing vocabulary, while all evidence remains scoped to
the Qwen3-8B Route-A anchor.  This record does not expand that scope to a
generic algorithm, model, workload, or serving claim.

| Verdict group | Result | Meaning |
|---|---|---|
| Semantic consistency | **PASS** | The reviewed contracts retain the frozen mask/lifecycle/authority/order semantics. |
| Finite anchor implementability | **PASS** | The selected 32K × 1 profile supplies finite checked identities, capacities, credits, and reclamation conditions. |
| Realization sufficiency | **BLOCKED** | Several implementation-level architecture choices remain unselected; an RTL author would have to make them. |
| Overall Gate A | **BLOCKED** | Gate A cannot authorize RTL until every blocker below receives a reviewable contract and executable verification plan. |

## Reviewed evidence chain

1. `architecture_gate_a0_remote_report_verification_20260928.md` records a
   byte match for all eleven accepted A4.10--A4.14.1 remote reports.  It is the
   accepted-report provenance input, not a rerun.
2. Gate-A1 selects `direct_pending_endpoint_v1` without claiming that A4 chose
   a physical direct endpoint.
3. Gate-A2 executes source order, atomic publication, authority conservation,
   FIFO/ownership, stale response, terminal outcome, and lossless semantic
   backpressure assertions without a model or clock.
4. Gate-A3 selects and validates finite Qwen3-8B Route-A anchor values,
   including a keep-all cold capacity guard rather than observed compression.
5. A4.14.1 remains the conditional research disposition and omitted-cost
   constraint.  Its metadata/payload service coordinates remain non-additive
   until a common dependency/arbitration/overlap realization exists.

## Group 1 — semantic consistency: PASS

The reviewer confirms the following remain unchanged across the reviewed
chain:

- original per-layer/per-KV-head KVzap mask and `HOT_WINDOW=128` semantics;
- `hot -> maturity -> DROP` or `hot -> pending -> packed` authority path;
- exactly one authoritative residency for every retained live token;
- pending authority survives payload write commit and transfers only at the
  single atomic metadata publication boundary;
- per-head FIFO/ownership/dependency/credit semantics, no partial group
  visibility, and lossless backpressure;
- canonical functional source order `hot -> pending -> packed`, absent-source
  identity, normalization guard, two common S2 slots, and four Qwen-anchor GQA
  consumers;
- Gate-A1 direct pending delivery without S2 reuse or a persistent pending
  copy; and
- fail-closed fault handling with no Full-KV substitution or mask/admission
  change.

`threshold=-4`, score generation, and predictor behavior remain frontend
concerns; they are not Route-A backend RTL interface inputs.  The backend may
express model/layer/head/group/bytes/window dimensions as parameters, but the
reviewed anchor fixes their values and does not authorize changing KVzap
algorithm semantics through parameter reconfiguration.

## Group 2 — finite anchor implementability: PASS

The selected profile establishes the following finite, checked anchor facts:

| Contract | Reviewed value or relation |
|---|---|
| Deployment | 32,768 context tokens; one concurrent sequence; 36 layers; 8 KV heads; 64-token packed page; hot window 128. |
| Cold authority bound | `(32768 - 128) * 1 * 36 * 8 = 9,400,320` pending-resident records under the keep-all guard. |
| Packed pages | `36 * 8 * ceil((32768 - 128) / 64) = 146,880`; 18-bit page ID is sufficient. |
| Shared cold pool | Required `4,888,199,680 B` = cold payload + sidecar + one 33,280-B migration reserve; selected pool = 5 GiB. |
| Pool inclusion | Pending payload, packed payload, position sidecar, one migration-page payload/sidecar duplicate. |
| Pool exclusion | Descriptor/allocator metadata, M2 metadata, P3 stage, endpoint fragments, partial merge state, ECC/alignment, and controller overhead. |
| Request lifetime | `(rid, incarnation)` with 3-bit RID, 2-bit incarnation, `MAX_LIVE=6`, explicit response epoch, and wrap quiescence. |
| Page reuse | 8-bit generation plus explicit no-old-reference/response/S2/endpoint/metadata quiescence before wrap. |
| Data fragment | 512-bit / 64-B core-facing fragment; eight endpoint credits/fragments for one pending record.  It is not an HBM bus width. |
| Resource bounds | Two S2 fill destinations, one direct pending endpoint, one packer, four reads, one write, one active KV-head group. |
| Retirement | External runtime/session manager owns logical retirement; KV subsystem owns drain, quiescence, physical reclaim, and generation advance. |

This PASS is limited to a finite interface envelope.  It does not establish
that the excluded storage/control costs fit the 5-GiB pool, that the selected
resources meet any service target, or that a production accelerator supports
more than the declared anchor.

## Group 3 — realization sufficiency: BLOCKED

The following are architecture decisions, not merely RTL coding choices.  The
reviewer must close them before a Gate-A PASS.

| ID | Required contract | Why it blocks Gate A | Boundary that must be preserved |
|---|---|---|---|
| R1 | Core/HBM memory-wrapper request-response protocol, response ordering, terminal status, and clock/reset boundary | **CLOSED** by `architecture_gate_a_r1_core_memory_wrapper_contract.md` and its event-level reference. | 64-B core fragment is not HBM width; HBM timing/controller/CDC remain external and unmodeled. |
| R2 | Deterministic arbitration/dependency policy among S2 fills, direct-pending reads, pack reads, and pack writes | **CLOSED** by `architecture_gate_a_r2_arbitration_dependency_contract.md` and its R1-integrated event-level reference. | Preserve frozen FIFO/ownership/dependency/backpressure; no external-HBM scheduler or performance claim. |
| R3 | M2 wrapper and P3-stage wrapper contracts, including logical ports, reset/fault behavior, and ownership handshakes | **CLOSED** by `architecture_gate_a_r3_m2_p3_wrapper_contract.md` and its R1/R2-integrated event-level reference. | HA8-wide and `local32/shared256/staging512` remain logical service contracts, not physical ports/FIFOs or 36 macro copies. |
| R4 | Finite numeric merge interface: operand/result formats, rounding/overflow/exception disposition, and comparison relation to the A2 mathematical reference | The current merge is a real-number functional reference; RTL cannot choose FP16/BF16/FP32 or a spill policy itself. | Preserve canonical source order; do not claim arbitrary reorder equivalence or numeric/PPA evidence. |
| R5 | Page-manager descriptor/allocator metadata placement, address-map ownership, and retirement/reclaim handshake with the external runtime | **CLOSED** by `architecture_gate_a_r5_page_manager_descriptor_contract.md` and its event-level descriptor/reclaim reference. | Pending/packed authority and atomic publication stay unchanged; descriptor region remains outside the 5-GiB pool and its service/energy remains unestimated. |
| R6 | Explicit top-level module graph and generic lifecycle adapter ports | A parameter vocabulary is not yet an RTL module boundary. | Predictor score/threshold stays outside backend; anchor parameters remain values, not portability proof. |

## Required ownership inventory for closing R1--R6

The names below are reviewer roles, not existing RTL modules or a physical
implementation selection.

| Reviewer owner | Must own | Common or Route-A increment |
|---|---|---|
| lifecycle frontend adapter | Retention/maturity/admission events; no predictor score/threshold transport. | Frontend boundary |
| M2 control wrapper | Metadata transaction membership, atomic publication visibility, logical M2 credit/ownership. | Route-A increment |
| P3/pack wrapper | Pending-HBM backing access, transient stage ownership, pack write-to-publication dependency. | Route-A increment |
| packed-page manager | Descriptor/allocator state, page generation, address handles, reclaim handshake. | Route-A increment |
| common S2/GQA source wrapper | Two S2 slots, generation/READY/release, four-consumer fanout. | Common infrastructure |
| direct-pending endpoint | FIFO ordinal pending delivery, transient endpoint credits, source close/fault. | Route-A increment |
| merge wrapper | Ordered source-partial ingress, finite numeric contract, all-consumer completion dependency. | Route-A increment |
| memory-fabric wrapper | Core-side requests/responses, arbitration, ordering/status, HBM adaptation. | Integration boundary |
| runtime retirement adapter | Retire request/ack, admission stop, drain/quiescence completion. | Integration boundary |

## Gate-A reviewer completion criteria

A later reviewer record may change the overall disposition to **PASS** only
when R1--R6 each has: a selected interface/ownership contract; finite fields
and reset/fault behavior; a dependency relation that preserves the frozen
semantics; an executable reference/assertion plan; and an explicit statement
of which PPA/controller properties remain Gate-B evidence.  A choice may use
an abstract macro or controller wrapper, but may not leave an RTL author to
decide arbitration, numeric semantics, or authority transfer.

Until then, the next work is realization-contract closure, not a model/GPU
run, performance DSE, new A4.14.x experiment, or RTL implementation.
