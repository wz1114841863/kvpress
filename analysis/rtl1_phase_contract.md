# RTL1 — Interface / Control Skeleton Bring-up

**Status:** `rtl1_owner_local_control_and_replaceable_r4_boundary_complete; rtl1_i0_cross_owner_contract_frozen; behavioral_top_integration_numeric_core_and_composed_proof_pending`.

RTL1 may not change frozen owners, ports, assertions, oracles, pruning,
admission, scheduler semantics, page size, S2 count, outstanding bounds, merge
format, or physical realization parameters.

| Phase | Scope | Evidence before advance |
|---|---|---|
| RTL1.0 | Top/all skeletons, ports, reset, ready/valid, SVA/TB/scoreboard attachment | compile/elaboration clean; no behavior claim |
| RTL1.1 | R1 identity/fragment/terminal/reset-init/stale suppression | R1 assertions/oracle tests |
| RTL1.2 | R2 eligibility/FIFO/credit/grant-on-accept | R2 assertions/interleavings |
| RTL1.3 | coupled R3/R5 P3/descriptor/atomic publication | durable-only/one-commit assertions |
| RTL1.4 | S2/direct-pending/four-consumer release | generation/stale/GQA assertions |
| RTL1.5 | R6 lifecycle/terminal/retirement/global drain | authority/terminal/retire assertions |
| RTL1.6 | R4 boundary only | packet/fault binding; no exp/FP RTL claim |

CDC/HBM adapter, macro/port count, physical queues, frequency, timing, PPA,
and speedup remain outside RTL1 and require later implementation/Gate-B evidence.

## RTL1-I0 progress

**RTL1-I0 cross-owner integration contract: complete; no behavioral wiring.**
`analysis/rtl1_i_cross_owner_integration_contract.md` and its machine-readable
manifest freeze the top-inert inventory and the only permitted later
associations: per-record R3 publication membership, R2/R1 delivery context,
R4 source-instance sideband, named init/drain facts, and R5 reclaim. They
preserve the sole `metadata_publish_commit`, the sole R1 external path, the
frozen R4 header, and top composition-only ownership.

RTL1-I0 adds no Chisel module or top-level behavior. RTL1-I1 must first close
external R1 init acknowledgement and named drain-status composition; later
I2--I4 may then close publication/authority, source/R4/R6, and reclaim under
the frozen I0 contract. Numeric-core realization remains a separate gate.

**RTL1-I1 init/drain composition: complete for safe start and empty-session
retirement.**
`analysis/rtl1_i1_init_drain_carrier_contract.md` adds the dedicated external
R1 reset-epoch acknowledgement carrier and records the reviewed
`route_a_component_status_collector` hierarchy amendment plus its eight named
owner-local facts. The behavioral closure accepts that acknowledgement only at
R1, losslessly serializes status facts to R6, blocks new R2 candidate intake
during retirement, and permits R1 drain only after R2's two local partitions
have drained. It proves safe startup and empty-session retirement only; I2
must next bind admission/per-record publication authority without revisiting
the frozen commit boundary.

**RTL1-I2 admission/publication composition: complete at the R6--R3 boundary.**
`analysis/rtl1_i2_admission_publication_contract.md` freezes and implements
the immutable retained-record context, explicit non-contiguous member ledger,
and post-atomic-publication observation sequence.  R6 supplies a context only
with its matching `hot -> pending` transition; R3 validates it against a live
claimed group and emits `pending -> packed` only after the existing nested
publication acknowledgement.  The top contains that carrier wiring, but does
not yet provide the R2/R1/P3 payload/claim/publish producer.  This is a
control-association closure, not a new page-packing policy, payload movement,
physical memory realization, timing/PPA result, or end-to-end top proof.

**RTL1-I3 delivery/source/R6 completion composition: complete for the frozen
control association.** `analysis/rtl1_i3_delivery_source_contract.md` freezes
R2's opaque delivery-context preservation, the separate R4 `SourceInstance`
sideband, and the finite R6 expected/released source-completion association.
The top demultiplexes an R4 commit to its sole hot/direct/S2 owner; only that
owner can emit its exact generation-bearing release after four distinct
consumer commits. R6 accepts all and only releases named by a nonempty
per-request completion plan, then emits the existing merge request; the
existing R4 fault/result path remains the only outward terminal route through
R6. Directed tests cover all seven nonempty source masks, stale generation
rejection, and a representative hot--R4--R6 fault path.

This is a control-association closure only. Source-plan, packet, S2 fill,
direct-record, and payload ingress remain top-inert; it selects no source
scheduler/mux, source buffer payload, R4 arithmetic/precision, HBM/controller,
cycle behavior, timing, throughput, PPA, or end-to-end Route-A proof.

**RTL1-I4.0 reclaim transport contract: frozen; behavioral closure pending.**
`analysis/rtl1_i4_reclaim_contract.md` freezes a two-pass retirement drain so
the post-drain R5 invalidation writes cannot be mistaken for pre-reclaim empty
state. It also fixes one 64-B descriptor-line-at-a-time invalidation image,
the existing R2/R1 write route, post-terminal-only allocator reuse, and the
A3 identity-wrap environment obligation. No reclaim RTL is present at I4.0.

## RTL1.6.0 progress

**RTL1.6.0 R4 packet/fault carrier closure: complete.**
`analysis/rtl1_6_r4_packet_boundary_contract.md` freezes identity-bearing R4
header/fragment/result/fault carriers without reinterpreting the legacy opaque
`SourcePartial` bundle. The top ties them inactive. No numeric merge,
binary32 arithmetic, exp, partial-state storage, source-mux, source schedule,
or terminal integration is implemented at this carrier step.

## RTL1.6 progress

**RTL1.6 R4 packet/fault boundary: complete at module scope.**
`RouteAMergeBoundary` checks the frozen absent/present header and fragment
structure, emits the matching per-consumer commit, and maps exactly one
identity-matching replaceable result or numeric fault to the existing R6-facing
terminal channel. It contains no arithmetic and rejects malformed, empty,
stale, duplicate, or simultaneous terminal facts.

This completes RTL1's owner-local control and replaceable R4 boundary. It does
not connect actual sources, R3 publication, S2/direct delivery, R6 lifecycle,
or a numeric core at the top. The next required action is an RTL1 cross-owner
integration review, not synthesis, timing, PPA, or a new DSE.

## RTL1.5.0 progress

**RTL1.5.0 R6 lifecycle semantic-carrier closure: complete.**
`analysis/rtl1_5_r6_lifecycle_semantic_carrier_contract.md` freezes the local
authority-transition and GQA-complete merge-ready carriers, and requires
explicit logical event/status/control encodings plus a parameterized
attention-tracker capacity at elaboration. No top-level port changes, source
mux, R3/R4 integration, lifecycle behavior, physical queue, controller, or
deployment outstanding bound is selected. The top continues to tie the new
local endpoints inactive; RTL1.5 behavior is verified at the lifecycle module
until a later top-integration phase connects their frozen owners.

## RTL1.5 progress

**RTL1.5 R6 lifecycle/terminal/retirement control: complete at module scope.**
The lifecycle adapter now gates session start on three named init
acknowledgements, stages score-free arrival/maturity control and the matching
event-level authority transition, tracks a parameterized finite set of live
attention identities, accepts R4 terminal only after GQA-complete merge-ready,
and returns retirement acknowledgement only after terminal delivery and all
eight named drains. It clears local reachability on destructive reset.

The result is deliberately not top integration: it does not route an actual
source mux, discover source membership, create publication requests, duplicate
M2/P3 authority state, or implement R4 numeric logic. `a_numeric_fault_consumer`,
`a_global_retirement_membership`, and `a_exactly_one_terminal` are
owner-Chisel-bound; global per-token authority conservation and both fairness
progress properties remain composed verification obligations.

## RTL1.4.0 progress

**RTL1.4.0 S2/direct-pending semantic-carrier closure: complete.**
`analysis/rtl1_4_s2_direct_pending_semantic_carrier_contract.md` freezes the
module-local S2 fill/sidecar/generation and direct record-terminal/ordinal
carriers, plus generation-bearing local GQA commit/release. The frozen
top-level lifecycle, R1, R2, R4, and R6 ports/owners are unchanged. The top
ties the new carrier endpoints inactive pending RTL1.4 producer integration;
there is no source mux, numeric merge, physical source buffer, or direct
pending payload buffer in this carrier-only step.

## RTL1.4 progress

**RTL1.4 S2/direct-pending/GQA control: complete at module scope.**
S2 now owns the two-slot generation, fill/sidecar-complete to READY control,
and four-consumer release bitmap. The direct endpoint owns its one pending
source association, strict ordinal/close/fault control, and a matching local
four-consumer release rule. Both remain payload-storage-free and top-inert:
there is no physical S2/direct buffer, source mux, R4 numeric merge, R6
terminal result, controller, timing, or PPA claim. `a_gqa_release` is now
Chisel-bound at the frozen S2 owner; R6 terminal/retirement properties remain
pending.

## RTL1.3.0 progress

**RTL1.3.0 R3/R5 semantic-carrier closure: complete.**
`analysis/rtl1_3_r3_r5_semantic_carrier_contract.md` freezes the local
control-only P3 claim/fragment/sidecar/write-terminal, two-member M2 result,
R5 allocation, and descriptor-terminal carriers. The frozen external
publication triplet and the sole R1 external-memory carrier are unchanged.
The top keeps these local carriers inactive until their producer-owner phases
exist, so this step contains no P3/M2/R5 behavior or authority change. The
structural Chisel elaboration test passed after the carrier addition.

## RTL1.3 progress

**RTL1.3 coupled R3/R5 publication control: complete at module scope.**
`route_a_m2_p3_wrapper` now tracks only P3 control state and the two private
M2 group results: it does not store P3 payload fragments or instantiate an M2
macro. `route_a_page_manager` tracks private append allocation and required
descriptor-durable facts; it exposes a page only through the existing nested
R3 publication handshake. The test-local allocator/stream bounds are required
at elaboration and are not selected physical bitmap/macro instances; the
146,880-entry allocator and 288-stream logical anchors remain intended
integration bindings.

The bound R3 assertion is `a_metadata_publish_commit`: publication visibility
requires a durable P3 write, both M2 members, and the nested R5 acknowledgement.
R5 invalidation-before-free and global authority/retirement assertions remain
pending for R5-later/R6. This module-level result is no-model control-contract
evidence only, not a P3 payload-memory, HBM-controller, timing, or PPA claim.

## RTL1.0 progress

**RTL1.0.a structural skeleton: complete.** The Chisel implementation at
`hardware/route_a/chisel/` elaborates the frozen top and nine direct children,
the RTL0.2 logical ready/valid carrier bundles, `core_clk`,
`destructive_reset`, and the sole R1 external-memory carrier. It contains no
registers or mutable architectural state. The required opaque logical fields
have no deployment defaults: only the structural test supplies local values
needed to elaborate a finite carrier shape.

The no-model evidence is the Chisel structural test
`RouteAKVSubsystemTopSpec`; it checks the ten-module hierarchy in CHIRRTL, the
external top port names in in-memory SystemVerilog, the selected anchor widths,
and absence of sequential RTL. CIRCT may optimize inert child shells out of its
final SystemVerilog; that is why hierarchy is checked at the elaborated CHIRRTL
stage rather than by adding non-architectural logic to defeat optimization.

**RTL1.0.b verification binding infrastructure: complete.**
`hardware/route_a/chisel/src/test/resources/rtl1_0_verification_binding.json`
binds every one of the 15 frozen matrix records to its frozen skeleton owner,
one SVA-registry marker, its safety-guarantee or progress-fairness role, and
the one existing Python oracle association. The accompanying zero-port
SystemVerilog registry binds to `route_a_kv_subsystem_top`; it adds no design
behavior or assertion body. The Python
`RouteAScoreboardOracleBindingRegistry` exposes the exact frozen oracle path,
entry-point labels, observation description, and forbidden adapter rule without
dispatching an event or running a model.

At RTL1.0.b completion every safety body was explicitly
`owner_state_pending` and every progress body `owner_event_pending`. That was
required because RTL1.0.a had no owner state or event transitions to observe.
The registry proves binding inventory/ownership consistency only; it is not an
SVA/formal proof, Python-scoreboard execution, directed protocol test,
randomized scenario, or RTL functional pass. Consequently RTL1.0.b alone did
not authorize R1--R6 behavior.

## RTL1.1 progress

**RTL1.1 R1 core-memory wrapper: complete at module scope.**
`RouteACoreMemIfV1` replaces only the R1 inert shell with the selected
`core_mem_if_v1` transaction state: four live reads, one live write,
`(RID[2:0], incarnation[1:0])` live/retired identity discipline, ordered
512-bit fragments, fail-closed malformed or early-write-commit handling, and
one terminal removal. Its write commit reports payload durability only; it
does not create publication, page authority, a packed read, or any R3/R5
behavior.

`mem_init_done` is a module-local adapter acknowledgement. After destructive
reset, R1 will not accept or emit traffic until it is observed. The adapter
must suppress/drain pre-reset replies before acknowledging it; because the
adapter epoch is explicitly not a core-side wire, R1 cannot distinguish an
adapter-violating old response from a new response with the same numeric
identity after that acknowledgement. The still-inert top ties this local input
low until the lifecycle/reset owner phase integrates the handshake. Therefore
this is an R1 module pass, not a functional top-level Route-A pass.

The binding manifest now marks the three R1-owned safety records
`a_descriptor_unique_memory_path`, `a_reset_stale_exclusion`, and
`a_stale_response` as `owner_chisel_assert_bound`; all other safety and
progress records remain pending. The zero-port SVA registry remains only the
frozen top-level attachment; these three bodies are Chisel assertions, not an
SVA/formal proof. The frozen Python scoreboard association is still read-only
inventory binding, not an event-dispatch adapter or an RTL/Python equivalence
claim.

No-model ChiselSim directed tests cover reset-init gating, stalled read
fragment forwarding, terminal stale suppression, same-epoch identity reuse
rejection, the four-read bound, ordered write fragments, successful terminal
write commit, early-commit terminal fault, and pre-init stale response
suppression. They make no HBM controller, CDC, timing, bandwidth, PPA, model,
GPU, performance, or complete RTL-correctness claim.

## RTL1.2.0 progress

**RTL1.2.0 R2 semantic-carrier realization: complete.**
`analysis/rtl1_2_r2_semantic_carrier_contract.md` resolves the RTL1.0 opaque
candidate and source-delivery records into the existing-port R2 request,
predicate, response-association, and parameter boundary. It neither adds a
top-level channel nor chooses a physical queue/FIFO depth. RTL1.2 may now
implement the R2 owner behavior only against that carrier contract.

## RTL1.2 progress

**RTL1.2 R2 arbiter: complete at module scope.** `RouteACoreSideArbiter`
implements parameterized candidate storage, class-specific eligibility checks,
the frozen read rotation and ordinal/id selection, accepted-grant-only cursor
advance, a separate descriptor/write path, R1 response association, and one
transport reservation per live R1 identity. It does not implement source
owners, metadata publication, semantic-credit return, an HBM controller, or
top-level traffic integration. The existing top remains inert until its later
owner phases connect candidate producers and `mem_init_done`.

The binding registry marks `a_ready_low_nonmutation` and
`a_fifo_credit_losslessness` as `owner_chisel_assert_bound`; `p_credit_return`
remains an environment-fairness progress obligation because publication/source
credits belong to later R3/R5/R6 owners. ChiselSim directed tests cover
ineligible backpressure, stalled grant stability, accepted cursor advancement,
matched terminal routing, and separate descriptor terminal release. This is
no-model functional-module evidence only, not SVA/formal proof, controller,
timing, throughput, PPA, or end-to-end RTL correctness evidence.
