# RTL2 — Production Transaction/Dataflow Integration

**Status:** `rtl2_1a_to_1c_atomic_publication_implemented_directed_tested;
rtl2_2_0_provenance_reconciled; rtl2_2_1_registry_association_implemented_directed_tested;
rtl2_2_2_typed_write_delivery_implemented_directed_tested;
rtl2_2_3_functional_storage_implemented_directed_tested;
rtl2_2_4_read_delivery_context_implemented_directed_tested;
rtl2_3_0_read_issue_contract_implemented_directed_tested;
rtl2_3_c5_source_packet_r4_implemented_directed_tested_limited_protocol_closure;
rtl2_3_r_active_phase_reconciled_no_behavioral_activation;
rtl2_3_c6_source_plan_binder_implemented_directed_tested;
rtl2_3_c7_source_service_top_integration_implemented_directed_tested;
rtl2_3_c8_four_consumer_completion_implemented_directed_tested;
rtl2_6_completion_review_complete_testbench_only_functional_transaction_dataflow`.

RTL2 activates the deliberately inert production ingress left by RTL1, so that
architecture-valid transactions carry real functional payload/sidecar facts
through their already frozen owners.  It is not a new Route-A DSE and it does
not select a physical memory, HBM controller, numerical merge implementation,
clock, service rate, frequency, timing target, area, energy, or PPA result.

The technical authority remains `architecture_spec.md`; the executable
authority remains the existing Route-A references and the RTL1-V scoreboard
adapter.  This document defines activation order and review evidence only.  It
does not reopen pruning, admission policy, page size, M2 organization, P3
mapping, S2 count, GQA legality, scheduler semantics, or the one atomic
metadata-publication boundary.

## RTL2.0 progress

**Status:** `rtl2_0a_to_0g_closed; historical_completion_review_passed;
rtl2_1a_implemented_separately`.

[`rtl2_0_activation_contract.md`](rtl2_0_activation_contract.md) and its
machine-readable manifest complete the fail-closed owner/event inventory.  It
finds seven explicit hierarchy/interface/testbench-boundary amendments needed
to activate production carriers without making the top a producer or a second
authority owner. The separate completion review checked the seven closures and
created the required versioned scoreboard schema before the first behavioral
activation.

**RTL2.0a payload interface/owner closure: complete; behavior pending.**
[`rtl2_0a_payload_materialization_contract.md`](rtl2_0a_payload_materialization_contract.md)
freezes the logical 8x64-B materialization and retained-maturity egress
transactions at the sole hot owner.  It creates no Chisel payload backing or
production behavior; the next required review is the finite admission/group
builder contract.

**RTL2.0b admission-group interface/owner closure: complete; behavior pending.**
[`rtl2_0b_admission_group_builder_contract.md`](rtl2_0b_admission_group_builder_contract.md)
defines the single-packer, 64-member retained-group association and exact
R5-allocation/P3-claim/R3-relay order.  It adds no child, payload behavior, or
publication activity; next review is the R2 multi-producer ingress contract.

**RTL2.0c R2 ingress/context interface-owner closure: complete; behavior pending.**
[`rtl2_0c_r2_ingress_delivery_context_contract.md`](rtl2_0c_r2_ingress_delivery_context_contract.md)
freezes six class-labelled logical producer endpoints and a separate opaque
delivery-context registry.  R2 retains all arbitration/credit/FIFO ownership;
the future typed router may only consume registry-resolved target descriptors.

**RTL2.0d typed delivery-router endpoint closure: complete; behavior pending.**
[`rtl2_0d_typed_delivery_router_contract.md`](rtl2_0d_typed_delivery_router_contract.md)
freezes four exact read-fragment and two final write-terminal descriptors. It
explicitly separates the unchanged 512-bit logical read payload envelope from
existing control-only endpoint observations; it selects neither payload storage
nor router behavior.

**RTL2.0e R3/R5 descriptor-durability prerequisite closure: complete; behavior pending.**
[`rtl2_0e_r3_r5_durability_prerequisite_contract.md`](rtl2_0e_r3_r5_durability_prerequisite_contract.md)
freezes R5's one aggregate `new_page` plus conditional `tail_link` result to
R3. An accepted success is a necessary private prerequisite, never descriptor
visibility or authority transfer; it selects no descriptor storage realization.

**RTL2.0f source-service packet-adapter closure: complete; behavior pending.**
[`rtl2_0f_source_service_packet_adapter_contract.md`](rtl2_0f_source_service_packet_adapter_contract.md)
freezes the R6 accepted-plan copy, the three source-owner packet offers, and
the atomic R4 header/sideband plus fragment egress. It preserves canonical
`hot -> pending -> packed` source order without choosing source computation,
consumer ordering, or numeric implementation.

**RTL2.0g R4 result-stub provider closure: complete; testbench behavior pending.**
[`rtl2_0g_r4_result_stub_provider_contract.md`](rtl2_0g_r4_result_stub_provider_contract.md)
freezes one explicit testbench success-or-fault scenario per accepted nonempty
R6 merge request. It remains outside synthesizable numeric RTL and cannot
bypass R4-to-R6 terminal ownership.

**RTL2.0 completion review: passed pre-behavior.**
[`rtl2_0_completion_review.md`](rtl2_0_completion_review.md) confirms all
seven amendments, the top's continued composition-only scope, and the
pre-behavior [`rtl2_scoreboard_event_schema.json`](rtl2_scoreboard_event_schema.json).
Its narrow PASS authorized only RTL2.1a. The resulting implementation is now
recorded separately below; the review itself remains a historical pre-behavior
gate record.

**RTL2.1a retained-group/admission activation: implemented and directed tested.**
[`rtl2_1a_retained_group_admission_contract.md`](rtl2_1a_retained_group_admission_contract.md)
creates the one-active, 64-record immutable association child and connects only
R6 retained pairs, R5 allocation, R3 claim/ack, and R3 pair relay. It preserves
pending authority and leaves R1, descriptors, publication, payload, and numeric
paths inactive.

**RTL2.1b payload/descriptor prerequisite: implemented and directed tested.**
[`rtl2_1b_payload_descriptor_durability_contract.md`](rtl2_1b_payload_descriptor_durability_contract.md)
records the actual no-tail R3 -> R2 -> R1 -> R5 write path and its private
durability prerequisite. Its tail-link dependency is closed by RTL2.1c below.

**RTL2.1c atomic publication: implemented and directed tested.**
[`rtl2_1c_atomic_publication_contract.md`](rtl2_1c_atomic_publication_contract.md)
binds R3's exact M2 request/response and publication-candidate identities to
the nested R5 visibility acknowledgement and the one `pending -> packed`
handoff. It is functional protocol closure only; no M2 realization is chosen.

## Entry conditions and common rules

RTL2 begins from the RTL1-V completion state.  Every activated carrier must
have one named producer, one named consumer, an identity/generation rule, and
one event-schema mapping before it can leave its inactive top-level binding.
The top is composition-only: it may wire or gate an owner-provided fact, but
may not synthesize a source plan, reconstruct delivery context, manufacture a
terminal, or become a second authority owner.

The first RTL2 change must version the scoreboard-event contract without
editing the frozen RTL1-V event schema.  Its RTL2 event inventory must include
at least:

```text
request_accept
fragment_deliver
write_commit
descriptor_durable
metadata_publish_commit
authority_transition
source_deliverable
consumer_partial_commit
source_release
merge_request
attention_terminal
descriptor_invalidate
page_free
retire_ack
```

The testbench/Python adapter consumes these architectural events; it must not
infer them from arbitrary internal state.  Each RTL2 slice adds directed
positive/negative tests and fixed-seed legal-stall/interleaving tests.  A
stall may delay only: it may not drop, reorder, duplicate, alter a mask or
admission disposition, create Full-KV fallback, or alter authority.

All RTL2 commands added by implementation must support `--help`.  Evidence
labels remain: synthesizable functional-control evidence where applicable;
no model/GPU; no cycle, latency, throughput, PPA, or RTL numeric-correctness
claim.  Commit each completed slice with the contract/review source in its
message.

**RTL2.6.2a narrow composition is implemented.**
[`rtl2_6_2_composed_packed_source_harness_contract.md`](rtl2_6_2_composed_packed_source_harness_contract.md)
connects a real S2 owner through a test-only availability observation seam,
four R4 commits, source release, R6 merge, and the R4/R6 numeric-fault
terminal in one simulation instance. It neither adds a production R3/R5-to-S2
bridge nor claims the full retained transaction witness.

## RTL2.0 — Producer and event-ownership activation closure

Before behavioral payload wiring, inventory every RTL1 top-inert carrier and
resolve its sole producer/consumer.  The output is a reviewable activation
manifest that binds the full event list above to its Chisel owner and
scoreboard adapter mapping.  It must specifically resolve who creates:

- retained-record/admission-group context;
- read-delivery context and source instance;
- payload-write/descriptor-maintenance terminals;
- S2/direct source-deliverable facts and four-consumer completions; and
- R4 request/result/fault facts and R6 lifecycle/retirement facts.

An owner or hierarchy amendment not already allowed by the frozen interface
contracts is a stop-for-review condition.  A temporary top-level generator,
an adapter-created authority fact, or a reconstructed delivery context is not
an acceptable closure.  RTL2.0 does not claim end-to-end payload movement.

## RTL2.1 — Admission to atomic publication

RTL2.1 is one gate, deliberately implemented and tested in three ordered
sub-slices.  Its only visible packed-authority linearization point remains the
existing `metadata_publish_commit`.

| Sub-slice | Required functional closure | Must remain impossible |
|---|---|---|
| RTL2.1a | Form and preserve an immutable retained group from the frozen admission decision; claim exactly its non-contiguous member records. | Payload release, packed authority, or publication visibility merely from admission/group formation. |
| RTL2.1b | Drive the unique R2-to-R1 payload-write transaction and the R5 descriptor-maintenance prerequisite; emit identity-bearing `write_commit` and `descriptor_durable` only from their owners. **Implemented and directed tested;** its no-tail write path is complete and its visible-tail dependency is exercised by RTL2.1c. | Treating a write commit as metadata visibility or authority transfer. |
| RTL2.1c | After every required payload and descriptor prerequisite is durable, perform the sole nested `metadata_publish_commit`, emit the exact `pending -> packed` authority transition, and make the page readable. **Implemented and directed tested** with stale/mismatch and fault fail-closed cases. | Partial-group visibility, duplicate commit, or a pending/packed authority overlap. |

This slice retains the exact existing admission result; it neither changes
pruning nor invents a new policy.  Fault and stall tests must demonstrate that
no incomplete group becomes visible and that no token has zero or duplicate
authoritative residency.

## RTL2.2 — Read-fragment delivery versus write-terminal delivery

**RTL2.2.0 provenance/interface reconciliation: complete.**
[`rtl2_2_0_delivery_context_reconciliation_contract.md`](rtl2_2_0_delivery_context_reconciliation_contract.md)
preserves the historical RTL2.0c record and records that `pack_read` belongs
to RTL2.2, not the already-completed write-only RTL2.1 behavior. It freezes
the typed read/write fields and keeps S2/direct functional endpoints deferred.

**RTL2.2.1 registry allocation/reuse: implemented and directed tested.**
[`rtl2_2_1_delivery_context_registry_contract.md`](rtl2_2_1_delivery_context_registry_contract.md)
initially implemented the registry as an independent association child. It
enforces class/target compatibility, identity-exclusive live allocation,
ready-low acknowledgement stability, exact release, and stale-incarnation
fail-closed reuse. It deliberately adds no core-side reset-epoch wire. Its
production R3/R5 integration is now completed by the distinct RTL2.2.2
typed-resolution closure below.

**RTL2.2.2 registry-resolved typed write terminals: implemented and directed
tested.**
[`rtl2_2_2_typed_delivery_router_contract.md`](rtl2_2_2_typed_delivery_router_contract.md)
connects R3 packed-write, R5 append, and R5 reclaim candidates through a
producer-neutral pre-R2 allocation bridge, the sole registry, and a typed
router. The bridge preserves the existing R2 ordinal/id merge rule; the router
uses only the registry-held descriptor and releases a ref only after exact
final endpoint acceptance. Its typed read-fragment output remains top-inert:
S2/direct/P3-read deposition and source service are still later work.

**RTL2.2.3 replaceable P3/S2 functional-storage prerequisite: implemented and
directed tested.**
[`rtl2_2_3_functional_storage_contract.md`](rtl2_2_3_functional_storage_contract.md)
records the existing sole R3 P3 reference backing and the new owner-local S2
payload/sidecar reference backing.  A packed S2 slot reaches `READY` only after
matching payload, sidecar, and existing control completion facts.  The top
continues to keep its new S2 ingress/read carriers inactive: no R2 read
producer, typed read deposition, source service, GQA packet, or R4 work is
implicitly activated.

**RTL2.2.4 read-delivery context completion: implemented and directed tested.**
[`rtl2_2_4_read_delivery_context_contract.md`](rtl2_2_4_read_delivery_context_contract.md)
and its machine-readable manifest preserve the producer-originated
`expected_fragment_count` in the immutable registry allocation.  This closes
the count/`last` context needed by a future read endpoint without inventing it
from a response.  It is deliberately not a read producer or deposit path:
the top's typed read output remains inactive, so there is still no P3/S2/direct
payload mutation, source deliverability, or `fragment_deliver` event.

RTL2.2 has two intentionally separate transaction classes.  They must not be
implemented as a generic response demultiplexer.

### Read-fragment delivery

Read data are delivered only to the owner named by frozen read context:

```text
P3 staging  |  S2 fill  |  direct-pending endpoint
```

These are destination classes, not sequential hops.  The existing R2
payload-read candidate rotation is
`s2_fill -> direct_pending -> pack_read`; selection advances only on R1
acceptance.  Delivery preserves request identity, incarnation/generation,
fragment ordinal, last/fault state, sidecar, and endpoint ownership.  Stale or
misdirected response facts must not make S2 `READY`, mutate direct-pending
state, or produce a source-deliverable event.

### Write terminal / commit delivery

Write completion is delivered only to the packed-write owner and the distinct
R5 descriptor-maintenance owner:

```text
packed-write terminal  ->  payload-durable prerequisite
descriptor terminal    ->  descriptor-durable prerequisite
```

Descriptor maintenance remains the frozen FIFO-ordered, one-fragment write
channel through the unique R1 boundary.  It is not a member of the payload-read
rotation and does not imply a second memory port.  Its terminal facts feed
RTL2.1b/RTL2.1c prerequisites rather than S2/direct read delivery.

The complete canonical numbering map, including historical manifest labels, is
[`rtl2_phase_numbering_reconciliation.md`](rtl2_phase_numbering_reconciliation.md).

## RTL2.3 — Source service and multi-source composition

**RTL2.3-R active phase reconciliation: complete; no behavior activated.**
[`rtl2_3_reconciliation_01.md`](rtl2_3_reconciliation_01.md) preserves the
historical RTL2.0 schema and manifest while supplying the active phase labels
for the remaining RTL2.3--RTL2.6 work. Its JSON overlay is a navigation map,
not an event emitter or a replacement schema. In particular, C1--C5 remain
preparation/structural closures; the parent RTL2.3 phase remains incomplete.

**RTL2.3-C6 source-plan binder: implemented and directed tested.**
[`rtl2_3_c6_source_plan_binder_contract.md`](rtl2_3_c6_source_plan_binder_contract.md)
names `route_a_source_plan_binder` as the finite non-top producer of R6's
completion plan. It accepts only an upstream already-selected, nonempty,
canonical declaration; it holds exact fields under R6 backpressure and makes
no source-selection, residency, packet, or numeric claim. C6 creates no
scoreboard event and does not complete RTL2.3.

**RTL2.3-C7 source-service top integration: implemented and directed tested.**
[`rtl2_3_c7_source_service_top_integration_contract.md`](rtl2_3_c7_source_service_top_integration_contract.md)
places the existing packet adapter at the sole composition-top packet boundary.
It receives only R6's accepted plan copy and exact hot/direct/S2 owner-local
availability observations.  All offer/fragment ingress remains explicitly
inactive because no source owner has yet been authorized to produce a numeric
partial.  C7 is therefore a fail-closed observation/association closure, not
a source packet, consumer-completion, source-release, merge-request, or
scoreboard-emission claim.

**RTL2.3-C8 four-consumer completion: implemented and directed tested.**
[`rtl2_3_c8_four_consumer_completion_contract.md`](rtl2_3_c8_four_consumer_completion_contract.md)
names the fail-closed R4 commit demultiplexer and exercises the existing
owner-local release trackers with all seven nonempty source masks.  R6 holds
one merge request only after all planned generation-bearing releases.  The
integration harness uses structural verification packets and does not make a
numeric partial, source arithmetic, host-side scoreboard adapter, live top
endpoint, R4 terminal, or end-to-end claim.

**RTL2.3.0 read-issue descriptor contract: implemented and directed tested.**
[`rtl2_3_0_read_issue_contract.md`](rtl2_3_0_read_issue_contract.md) and its
machine-readable manifest bind the pre-R1 read facts—opaque payload handle,
`valid_count`, source generation/validity, destination, expected fragment
count, and immutable endpoint descriptor—to one producer-originated logical
record.  It names R3 as the pending/pack-read fact owner and R5 as the packed
page-handle fact owner, while preserving S2/direct as endpoint owners.  It is
not a live candidate, R1 request, R2 arbitration, response deposit, source
deliverability, or scoreboard-event activation.

**RTL2.3.1 producer-local candidate refinement: implemented and directed
tested.** [`rtl2_3_1_read_candidate_adapter_contract.md`](rtl2_3_1_read_candidate_adapter_contract.md)
adds the state-free `ReadIssueDescriptor -> SourceCandidate` translation used
by a future named R3/R5 source producer.  It rejects malformed or non-read
issues before candidate creation and copies producer ordering/predicate facts
without selecting an R2 winner.  It is not instantiated in the production top:
read allocation, multi-producer ingress, R2/R1 acceptance, and every response
or source-service effect remain later work.

**RTL2.3.2 incremental read allocation/ingress: implemented and directed
tested in isolation.** [`rtl2_3_2_read_ingress_contract.md`](rtl2_3_2_read_ingress_contract.md)
connects the three Route-A incremental read lanes to the existing
delivery-context registry and a lossless ordinal/id pre-R2 merge.  The new
bridge/merge have no production-top instance: R2, R1, typed read delivery and
all data/source behavior remain inactive.

**RTL2.3.3 R2-owned dual logical ingress: implemented and directed tested.**
[`rtl2_3_3_r2_dual_ingress_contract.md`](rtl2_3_3_r2_dual_ingress_contract.md)
moves the one-step choice between the existing ingress and a future read
ingress inside `route_a_core_side_arbiter`; the top exposes the latter only as
an explicit inactive carrier.  This prevents a top mux from becoming an
arbiter, but does not itself attach the isolated RTL2.3.1/2 producers to the
production graph.

**RTL2.3-C1 shared registry-allocation composition: implemented and directed
tested.** [`rtl2_3_c1_shared_allocation_contract.md`](rtl2_3_c1_shared_allocation_contract.md)
replaces the production write-only bridge with one six-lane composition owner.
It enforces each named lane's unique class before the sole registry allocates a
context, then forwards ref-bound records to the existing read/write pre-R2
merges.  Read producers remain inactive; this does not yet create a read
transaction or endpoint mutation.

**RTL2.3-C2 R3 pending-member pack-read endpoint: implemented and directed
tested in an integration harness.**
[`rtl2_3_c2_r3_pack_read_contract.md`](rtl2_3_c2_r3_pack_read_contract.md)
freezes one retained member to one eight-fragment `pack_read`, with immutable
`payload_ref` association and `member_ordinal * 8 + fragment_index` P3 mapping.
The harness passes that work through the existing C1 registry/R2/R1 route and
the typed router into the R3 endpoint, while stale/mismatched work/identity and
fault/malformed response cases fail closed without payload deposit.  Its one
explicit work carrier is a conservative functional baseline, not a permanent
single-outstanding schedule.  The production top keeps the work/issue boundary
inactive because hot-versus-pack P3 ingress composition and a live work producer
remain separately scoped; no top source-service claim is made.

**RTL2.3-C3 direct-pending record endpoint: implemented and directed tested in
an integration harness.** C3 keeps Gate-A1 `direct_pending_endpoint_v1` as a
direct transient transport: one pending 512-B record maps to one eight-fragment
R1 read, and a typed endpoint forwards each exact fragment before issuing the
existing control-only direct terminal. It binds the direct endpoint's active
identity and generated endpoint generation before any payload handoff; stale
identity, generation mismatch, terminal fault, and malformed matching response
cannot hand off payload or make a source deliverable. C3 creates no S2 slot,
pending buffer, source packet, R4 input, numeric operation, top-level work
producer, or scheduler.

**RTL2.3-C4 packed-S2 page endpoint: implemented and directed tested in an
integration harness.** [`rtl2_3_c4_packed_s2_contract.md`](rtl2_3_c4_packed_s2_contract.md)
binds immutable packed-page work to an S2 fill-open association before it can
enter the existing C1/R2/R1/registry/router path. It preserves tail-page
`valid_records`: payload count is exactly `valid_records * 8` logical 64-B
fragments, so a full 64-record page is 512 fragments. Each accepted response
is serialized into the owner-local S2 payload then terminal handoff; the
separate position-sidecar stream must also complete before S2 `READY`. Stale
identity, page/slot or generation mismatch, terminal fault, and malformed
matching response fail closed without payload deposit or READY. C4 does not
activate a top producer, generate sidecar data, emit source packets, invoke
R4, select an S2 macro/controller, or change scheduling.

**RTL2.3-C5 source packet to R4 boundary: implemented and directed tested.**
[`rtl2_3_c5_source_packet_r4_contract.md`](rtl2_3_c5_source_packet_r4_contract.md)
turns the earlier RTL2.0f interface-only contract into a narrow behavioral
adapter: R6's accepted immutable plan copy plus owner-provided structural
offers/fragments are accepted only in present-subset canonical
`hot -> pending -> packed` order and forwarded to the existing R4 packet
parser. All seven nonempty source masks and four consumer associations per
present source are exercised; stale availability, malformed headers, and
duplicate consumers fail closed. C5 neither derives source partials from
hot/direct/S2 payload state nor consumes commits/creates releases, and it
leaves the composition-only top packet ingress inactive. It is not R4 numeric
merge, source service, a live top producer, or an end-to-end transaction.

Connect owner-produced hot, direct-pending, and packed/S2 source facts to the
frozen source-instance and four-consumer protocol.  A source becomes
deliverable only after its own validity prerequisites; all four distinct GQA
consumer commits are required before its exact generation-bearing release.
The source mask and canonical order remain frozen as `hot -> pending -> packed`;
the RTL must not claim that arbitrary source reordering is bitwise equivalent.

The RTL2.3 result **after the remaining closure sequence below** is a
functional source packet/fragment path, not a source scheduler, HBM bandwidth
model, or numeric merge implementation.

### Remaining RTL2.3 closure order

The preceding sentence is a parent-phase requirement, not a claim that C5's
testbench-provided structural packets already satisfy it. The only authorized
remaining sequence is:

1. **C6: complete.** `route_a_source_plan_binder` is the named non-top producer
   of R6's immutable nonempty source declaration;
2. **C7: complete.** The composition-only top binds the accepted plan copy,
   source-owner availability, and existing packet adapter;
3. **C8: complete.** All-mask four-consumer commit/release association through
   R6 `merge_req` is directed-tested; and
4. **C9: complete.** One descriptor-selected top composition path now
   replaces the isolated C2/C3/C4 endpoint router attachments. Its explicit
   verification ingress is mutually exclusive with lifecycle-owned ingress;
   it does not represent opaque verification fragments as numeric source
   partials or choose a source schedule. Because it instantiates C4 in the
   top, the logical fragment count/index carriers must be at least 10/9 bits
   to represent the frozen full-page 512 count and 0..511 indices; this is not
   a physical memory/controller selection.

RTL2.3 has passed its separate `control_protocol_complete` review disposition;
C6--C9 passing tests remain distinct from that review evidence. This does not
authorize a source scheduler, numeric attention computation,
physical memory/controller selection, timing, throughput, or PPA claim.

## RTL2.4 — R4 boundary activation with replaceable result stub

After RTL2.3 has produced and held a legal R6 `merge_req`, activate the
existing R4 packet/result/fault boundary using a deterministic
verification result stub.  The stub may issue an identity-matching success or
one numeric fault after a valid source-completion association, so that R6 has
one outward terminal route.  It may not be represented as an exp, floating
point, precision, partial-softmax, online-merge, latency, or numeric-correct
implementation.

The frozen R4 boundary remains the replaceable contract for
`merge_req`, partial header/value fragments, `merge_rsp`, and `numeric_fault`.
The actual numerical implementation is a later realization sub-gate.

**RTL2.4.0 verification-stub terminal contract: complete; behavior pending.**
[`rtl2_4_0_r4_stub_terminal_contract.md`](rtl2_4_0_r4_stub_terminal_contract.md)
freezes the test-only `R4StubScenario`, R4-boundary active-merge observation,
success-XOR-fault association, R6-only terminal rule, and fairness boundary.
It creates no provider, top-level port, terminal behavior, numeric datapath,
scoreboard event, or performance claim.

**RTL2.4.1 verification-stub provider: complete in isolated test scope.**
[`rtl2_4_1_r4_stub_provider_contract.md`](rtl2_4_1_r4_stub_provider_contract.md)
implements the test-scope provider and R4's read-only active-merge observation.
It holds one explicit, identity-matching success XOR numeric-fault offer across
ready-low, rejects empty/stale/mismatched/malformed/duplicate inputs, and
clears on reset. It is not instantiated by the top and does not bind real R6
or create an `attention_terminal` scoreboard event; those remain RTL2.4.2 and
RTL2.4.3 respectively.

**RTL2.4.2 R4--R6 terminal-chain integration: complete in a test-only
harness.**
[`rtl2_4_2_r4_r6_terminal_integration_contract.md`](rtl2_4_2_r4_r6_terminal_integration_contract.md)
binds the existing R6 `merge_ready -> merge_req` event, the real R4 boundary,
the RTL2.4.1 provider, R4's sole `merge_rsp_or_numeric_fault`, and R6's sole
outward `attention_terminal_rsp`. Matching success/fault, stale rejection, R6
terminal backpressure, and destructive reset are directed-tested. The harness
uses an explicit already-completed `merge_ready` stimulus; it is neither a
source scheduler nor a production-top integration. `attention_terminal`
scoreboard binding remains RTL2.4.3.

**RTL2.4.3 attention-terminal scoreboard/oracle binding: complete in a
test-only harness.**
[`rtl2_4_3_attention_terminal_scoreboard_contract.md`](rtl2_4_3_attention_terminal_scoreboard_contract.md)
binds the named R6 outward terminal observation to the frozen R4-origin
`attention_terminal` vocabulary, a same-handshake Chisel event adapter, and
the existing R6 Python lifecycle reference. Success/fault, event ready-low,
duplicate/stale/reset rejection, and exact field/owner validation are tested.
It does not bind numeric values, infer events from internal state, or modify
the production top. The separate RTL2.4 completion review has passed; its
pass does not broaden the RTL2.5.0 behavioral boundary.

## RTL2.5 — Active-state reset, fault, retirement, and reclaim

**RTL2.5.0 lifecycle/reclaim contract: complete; behavior pending.**
[`rtl2_5_0_lifecycle_reclaim_contract.md`](rtl2_5_0_lifecycle_reclaim_contract.md)
freezes the existing R1/R2/R3/R4/R5/R6 ownership, reset stale-state exclusion,
global-drain membership, descriptor-invalidation-before-free ordering, and the
three deferred event targets.  It does not activate their emission, modify the
historical schema/overlay, or create a new top ingress.  RTL2.5.1 is the first
permitted destructive-reset behavioral closure.

**RTL2.5.1 destructive-reset closure: complete for directed reset epochs.**
[`rtl2_5_1_destructive_reset_contract.md`](rtl2_5_1_destructive_reset_contract.md)
injects reset into active R1, R5, S2/direct, and composed top initialization
state, then verifies old facts fail closed until the existing R1 init boundary
is re-established. It neither emits the deferred reclaim events nor closes
fault, retirement, or reclaim behavior.

**RTL2.5.2 fault/terminal closure: complete for the directed R4--R6 fault
boundary.** [`rtl2_5_2_fault_terminal_contract.md`](rtl2_5_2_fault_terminal_contract.md)
reuses the real R4 terminal boundary, real R6 outward terminal owner, and the
existing test-only terminal observation adapter.  It demonstrates one stable
`numeric_fault` terminal/event under legal backpressure, rejects stale,
mismatched, malformed, and post-terminal replay scenarios, and introduces no
retry or Full-KV fallback interface.  This is a narrow interface-absence and
fault-terminal statement only: it does not imply that a fault publishes,
transfers authority, reclaims storage, or closes retirement/reclaim behavior.

**RTL2.5.3 R6 retirement/drain closure: complete for fixed membership and
bounded fairness witnesses.** [`rtl2_5_3_retirement_drain_contract.md`](rtl2_5_3_retirement_drain_contract.md)
composes real R6 with the real status collector to prove that all eight frozen
drain facts, R5 reclaim completion, and a final R1/R2-descriptor pass precede
one matching `retire_ack`.  It also holds the permit and acknowledgement under
fixed-seed finite ready-low stalls before the environment releases them.  This
is neither a formal liveness claim nor R5's durable invalidation-before-free
closure; the three deferred reclaim events remain non-emittable.

**RTL2.5.4 R5 durable invalidation-before-free: complete for directed
descriptor-line witnesses.** [`rtl2_5_4_r5_durable_invalidation_contract.md`](rtl2_5_4_r5_durable_invalidation_contract.md)
exercises R5's sole matching descriptor terminal boundary.  A durable FREE
with next-generation line image, durable-invalidation fact, allocator release,
and generation advance occur together only for the matching terminal; fault,
stale, malformed, or replayed terminals cannot free the live line.  A
two-line witness rejects an old operation identity while the next descriptor
line is live.  This does not emit `descriptor_invalidate` or `page_free`;
their event/oracle binding is exclusively RTL2.5.5.

**RTL2.5.5 active-state scoreboard/oracle binding: complete in test-only
harnesses (RTL2.5.5-I cross-owner witness included).** [`rtl2_5_5_active_state_scoreboard_contract.md`](rtl2_5_5_active_state_scoreboard_contract.md)
binds the three remaining declared records to named carriers and existing
Python references. R5 now exposes its old-reference `allocator_release` only
after the matching durable descriptor terminal; the test-only adapter atomically
maps it to `descriptor_invalidate` and `page_free`, while the existing outward
R6 acknowledgement maps to `retire_ack`. The binding does not infer page facts
from descriptor images/state, instantiate a scoreboard in the production top,
or alter reclaim/authority/global-drain semantics.

Exercise active retained/publication/source transactions through destructive
reset, terminal fault, retirement drain, descriptor invalidation, and page
free.  The existing R6/R5/R2/R1 ownership and quiescence requirements remain
unchanged: invalidation must be durable before free, and `retire_ack` requires
the existing global drain membership.

Bounded legal-stall tests use explicit environment fairness: accepted external
work and willing consumers eventually complete.  Passing evidence supports only
the statement that no deadlock was observed in the covered bounded,
fairness-constrained interleavings.  It is not a proof that hardware is
deadlock-free, a latency guarantee, or a service-rate claim.  A stronger
liveness statement requires a later formal proof with explicit assumptions.

## RTL2.6 — completion / integration review

**RTL2.6.0 entry audit: complete, with an explicitly incomplete disposition.**
[`rtl2_6_completion_review.md`](rtl2_6_completion_review.md) and its
machine-readable [`rtl2_6_completion_review_manifest.json`](rtl2_6_completion_review_manifest.json)
freeze the review entry inventory without activating a new carrier.  Four of
the fourteen declared RTL2 events have existing testbench bindings;
`attention_terminal`, `descriptor_invalidate`, `page_free`, and `retire_ack`.
The other ten remain schema-only.  Consequently this audit is **not**
`rtl2_production_transaction_dataflow_complete`, and it does not claim a
complete retained-transaction witness.  The named verification ingress remain
owned, justified realization deferrals rather than unowned production
carriers.  RTL2.6.1 must bind the remaining events and replay one real-owner
composed retained transaction before this gate can pass.

**RTL2.6.1 event field-provenance binding: complete; Chisel carrier capture
remains deliberately pending.**
[`rtl2_6_1_event_binding_contract.md`](rtl2_6_1_event_binding_contract.md)
and [`rtl2_6_1_event_binding_manifest.json`](rtl2_6_1_event_binding_manifest.json)
close the no-default field source for the ten formerly schema-only records.
In particular, `request_accept` and `write_commit` retain their preceding
accepted R2/R1 association rather than pretending the bare R1 bundle carries
candidate class, delivery context, or write operation. The manifest is an
executable provenance contract only: it does not mark the records emittable
or change the RTL2.6.0 incomplete disposition. RTL2.6.2 must attach these
associations to real owner-carrier handshakes in one composed testbench
harness.

**RTL2.6.3 publication-to-S2 verification association: complete as a narrow
test-only adapter.**
[`rtl2_6_3_publication_s2_association_contract.md`](rtl2_6_3_publication_s2_association_contract.md)
requires a matching R3 publication observation, R3 `pending -> packed`
authority transition, and an explicit verification-only identity/slot
association before producing an existing S2 service request. It fails closed
on stale authority and page/tag/record mismatch, but is not a production
R3/R5-to-S2 bridge and does not complete the retained-transaction witness.

**RTL2.6.4 publication-to-terminal composition: complete as a narrow
single-instance witness.**
[`rtl2_6_4_publication_to_terminal_composition_contract.md`](rtl2_6_4_publication_to_terminal_composition_contract.md)
uses real R3/R5/R2/R1 publication, the explicit RTL2.6.3 association, and
real S2/R4/R6 control to reach a numeric-fault terminal. It retains every
test-only boundary and does not yet include retirement/reclaim, event replay,
or the full retained-transaction completion disposition.

**RTL2.6.5 full retained-transaction and scoreboard witness: complete with a
testbench-only functional disposition.** The authoritative ordered sub-slices
and non-goals are recorded in
[`rtl2_6_completion_review.md`](rtl2_6_completion_review.md). RTL2.6.5a.1
is complete:
[`rtl2_6_5a_packed_s2_read_composition_contract.md`](rtl2_6_5a_packed_s2_read_composition_contract.md)
uses the actual typed packed-S2 R2/R1 path before S2/R4/R6 completion.
RTL2.6.5a.2 is now also complete:
[`rtl2_6_5a2_r3_pack_read_p3_composition_contract.md`](rtl2_6_5a2_r3_pack_read_p3_composition_contract.md)
uses the actual R3 `pack_read -> R2/R1 -> P3` path before its existing
packed-write, descriptor, and atomic-publication sequence. It does not
relabel a verification ingress as a producer or select a future member issue
schedule. RTL2.6.5b--d are complete, and RTL2.6.5e supplies the final
same-instance R3 publication -> S2 service/terminal -> same-R5 durable reclaim
-> `retire_ack` witness. Its constrained re-review is
`rtl2_production_transaction_dataflow_complete` only under
`testbench_only_functional_transaction_dataflow`.

**RTL2.6.5b terminal-to-reclaim composition: complete.**
[`rtl2_6_5b_terminal_reclaim_composition_contract.md`](rtl2_6_5b_terminal_reclaim_composition_contract.md)
binds an accepted R6 attention terminal to an explicit matching environment
retire request, then uses existing R6 drain/permit and R5/R2/R1 durable
invalidation owners to reach `retire_ack`. It does not make terminal completion
an implicit production retirement request or remove deferred R3/direct drain
facts. RTL2.6.5c now closes testbench accepted-carrier event capture and
pure-software oracle replay for all fourteen immutable-schema event types;
the separate [`rtl2_6_5c_event_capture_replay_contract.md`](rtl2_6_5c_event_capture_replay_contract.md)
records its success, fault, stale, and bounded ready-low coverage. It does not
turn the separate composition slices into a production waveform. RTL2.6.5d
completed the cross-owner review with a historical no-PASS disposition because
the real-owner subpaths were not yet a single same-instance R3 publication ->
S2/terminal -> reclaim witness. RTL2.6.5e now supplies that narrow witness in
one Chisel testbench instance; see
[`rtl2_6_5e_same_instance_witness_contract.md`](rtl2_6_5e_same_instance_witness_contract.md).
Its re-review records `rtl2_production_transaction_dataflow_complete` only
under `testbench_only_functional_transaction_dataflow`. No production bridge,
numeric realization, physical-memory choice, or timing/PPA conclusion is
authorized.

RTL2.0--RTL2.5 passing individually did not by itself complete production
dataflow integration. The separate RTL2.6 completion review has now consumed
the declared event/oracle evidence and demonstrated one complete retained
transaction:

```text
RETAIN
  -> pending authority
  -> pack read
  -> P3
  -> packed write
  -> descriptor durable
  -> metadata_publish_commit
  -> packed authority
  -> packed read
  -> S2 READY
  -> four-consumer completion
  -> R4 boundary
  -> success or fault terminal
  -> retire
  -> reclaim
```

The success branch may use the RTL2.4 result stub; no real floating-point merge
is required for this review.  The review must also show a representative fault,
stale-response, and legal-stall path, with exactly-once terminal behavior,
authority conservation, invalidation-before-free, and final `retire_ack`.
It must identify and justify every remaining deliberately inactive ingress;
an unowned production carrier is a failure, not a deferral.

**Pass disposition:** `rtl2_production_transaction_dataflow_complete` permits
separate numeric/memory-realization planning only under
`testbench_only_functional_transaction_dataflow`. It does not authorize a
production bridge, profiling, optimization, synthesis, timing, or PPA claims.

## Planned successor — RTL3: Functional Realization Closure

**Status:** RTL3.0--RTL3.5-C are complete only within their declared
testbench/reference scopes. RTL3.6 correctly recorded a historical no-PASS,
then RTL3.6-A repaired the active replay provenance, RTL3.6-B/C1/C2 assembled
the bounded same-instance witness, and RTL3.7-A now binds the C2 packed read
to the exact R3-durable functional payload object. RTL3.7-B closes bounded
terminal-to-release-to-retire ordering, and RTL3.7-C joins C2's existing
R1/R2 drain facts with their publication-wrapper counterparts before the
unchanged R6 collector.  The functional-realization no-PASS remains: C2
grants are verification facts, sidecar and R4 remain declared fixtures, and
there is no production-top RTL3 composition,
physical controller, numerical microarchitecture, or performance experiment is
authorized by these records.
See
[`rtl3_0_replacement_owner_contract.md`](rtl3_0_replacement_owner_contract.md)
[`rtl3_1_functional_memory_environment_contract.md`](rtl3_1_functional_memory_environment_contract.md),
[`rtl3_2a_packed_read_association_contract.md`](rtl3_2a_packed_read_association_contract.md),
and [`rtl3_2_packed_read_functional_integration_contract.md`](rtl3_2_packed_read_functional_integration_contract.md).

RTL3 replaces the remaining verification-only data/numeric conveniences with
named, functional providers while preserving every frozen authority,
admission, scheduling, page, GQA, atomic-publication, and R6 terminal rule.
Its word “functional” is deliberate: completion is not physical-memory or
numeric-microarchitecture closure.

### RTL3.0 — replacement-owner manifest and stop-for-review map

**Complete as planning only, with behavioral activation blocked.**
[`rtl3_0_replacement_owner_contract.md`](rtl3_0_replacement_owner_contract.md)
freezes the required machine-readable/Markdown map for each remaining
verification convenience: replacement owner or explicit stop, interface,
identity/incarnation and generation source, accepted-carrier scoreboard
observation, environment assumptions, DUT guarantees, and the testbench
injection that becomes forbidden after replacement. It records two mandatory
stops: packed-read cross-owner association ownership before RTL3.2, and
query/position/RoPE association before RTL3.5.

| Current convenience | Planned functional replacement boundary | Non-negotiable limit |
|---|---|---|
| S2 payload/sidecar fill ingress | `core_mem_if_v1` response through the existing R2 typed-delivery/owner-local S2 deposition path, backed by a functional memory **environment** | The environment is not a second payload/metadata authority and is not an HBM controller. |
| Source packet offer/value-fragment ingress | A uniquely named, replaceable attention-partial-producer boundary fed by source-owner payload/sideband facts | Hot, direct-pending, and S2 owners do not compute `(m, l, o)` merely by owning K/V storage. |
| R4 result stub | An oracle-consistent functional R4 merge provider at the already frozen R4 boundary | It does not choose exp hardware, internal precision, state storage, pipeline, or throughput. |

RTL3.0 must also resolve, or explicitly stop for review on, the source of the
query association and position/RoPE sideband consumed by the partial producer.
It may not invent a query source, repurpose a storage owner as an attention
MAC owner, or make a testbench default appear as an accepted production fact.

### Ordered functional closures

1. **RTL3.1 — functional memory transaction environment (complete,
   testbench-only).** The host-side
   `testbench_route_a_functional_memory_environment` drives real accepted R1
   requests and responses against explicit functional packed payload,
   sidecar, generation, fault, and legal-stall fixture state. Successful
   writes materialize only at their accepted terminal. It is not a production
   Chisel module, HBM controller, burst/channel/CDC mapping, or a
   latency/bandwidth model. It does not form packed-to-S2 association and does
   not clear either RTL3.0 stop; see
   [`rtl3_1_functional_memory_environment_contract.md`](rtl3_1_functional_memory_environment_contract.md).
2. **RTL3.2-A — packed-read association-owner closure (complete,
   executable-contract only).** `route_a_packed_read_association_owner` is
   the unique join owner for an upstream preselected packed-source demand, a
   live R3 publication authorization, an R5 descriptor/location grant, and
   an S2 fill lease. It passes R2 scheduler fields unchanged and requires the
   existing R2 context acknowledgement before typed work. It resolves the
   former packed-read association stop but does not yet implement payload or
   sidecar transport; see
   [`rtl3_2a_packed_read_association_contract.md`](rtl3_2a_packed_read_association_contract.md).
3. **RTL3.2 — packed-page functional read to S2 (complete, bounded
   testbench-composed payload slice).** The real
   `route_a_packed_read_association_owner` joins live R3/R5/S2/demand grants,
   receives the existing registry acknowledgement, and feeds the existing
   R2/R1 typed packed-read and S2 deposition path. A preloaded RTL3.1
   functional-memory object supplies the payload; payload completion remains
   insufficient for S2 READY until explicit matching sidecar completion. This
   closes no sidecar transport, S2 allocation, endpoint-to-owner terminal
   adapter/release integration, source schedule, or production-top binding;
   see [`rtl3_2_packed_read_functional_integration_contract.md`](rtl3_2_packed_read_functional_integration_contract.md).
4. **RTL3.3 — R4 functional-realization profile and oracle binding
   (complete, pre-RTL3.4).** The future provider profile now freezes the
   canonical binary32 packet/oracle, fault disposition, and 4,096-bit
   little-endian normalized-lane representation. The existing Chisel R4
   boundary is bound only through a shared structural fixture; it still does
   not compute or classify numeric values. See
   [`rtl3_3_r4_functional_profile_contract.md`](rtl3_3_r4_functional_profile_contract.md).
   This neither reopens the numeric contract nor selects exp implementation or
   internal precision.
5. **RTL3.4-A — R4 per-consumer result association (complete).** Every
   `MergeRequest`, R4 success/fault carrier, and R4-to-R6 terminal now carries
   an exact query-head `consumer_id`. R6 serially issues the four logical
   consumer work items and aggregates four successes into one group success;
   a matching numeric fault remains fail-closed group termination. See
   [`rtl3_4a_r4_consumer_result_association_contract.md`](rtl3_4a_r4_consumer_result_association_contract.md).
6. **RTL3.4-B — oracle-consistent functional R4 merge model (complete).**
   `route_a_merge_boundary` now emits a lossless complete accepted-packet
   egress; the pure-software `route_a_functional_r4_merge_provider` derives
   each consumer result/fault from only those packet bytes and the accepted
   R6 work fact.  It obeys RTL3.3 and RTL3.4-A and retains R6's exactly-one
   group terminal ownership.  This is not final synthesizable/pipelined
   floating-point RTL; see
   [`rtl3_4b_functional_r4_provider_contract.md`](rtl3_4b_functional_r4_provider_contract.md).
7. **RTL3.5-A — query/position/RoPE and partial-producer boundary (complete
   interface-owner freeze).** [`rtl3_5a_attention_partial_producer_boundary_contract.md`](rtl3_5a_attention_partial_producer_boundary_contract.md)
   resolves the former query/position stop without activating computation.
   Hot, direct-pending, and S2 own only payload, position/sideband, and exact
   source identity/generation.  The external common frontend owns the
   already-RoPE-applied query and the Qwen-anchor `query_head = 4 * kv_head +
   consumer_id` association; the unique replaceable functional partial provider
   alone may later emit `(m, l, o)` through the frozen packet boundary to R4.
   It is not an attention MAC, RoPE, or numerical-RTL implementation.
8. **RTL3.5-B — functional partial-provider realization (complete,
   pure-software).** [`rtl3_5b_functional_attention_partial_provider_contract.md`](rtl3_5b_functional_attention_partial_provider_contract.md)
   implements a stateless functional PE/reference model over only RTL3.5-A
   query/source leases.  It produces the existing present R4 packet shape and
   can feed the RTL3.4-B model in Python tests, but is not Chisel, does not bind
   the top, and selects no FP/exp/RoPE hardware, payload transport, source
   scheduling, or production behavior.
9. **RTL3.5-C — cross-language functional packet binding (complete, static
   fixture only).** [`rtl3_5c_cross_language_packet_binding_contract.md`](rtl3_5c_cross_language_packet_binding_contract.md)
   proves one exact RTL3.5-B provider output is accepted by the existing
   Chisel source-packet adapter and R4 structural boundary without binding a
   production top or creating a live cross-language transport.  It preserves
   exact identity, source instance, header, eight fragments, and consumer
   association only.
10. **RTL3.6 — functional-realization completion review (complete,
    no-PASS).** [`rtl3_6_functional_realization_completion_review.md`](rtl3_6_functional_realization_completion_review.md)
    confirms the valid RTL3.1--3.5 slices and preserves the accepted-carrier
    success/fault/stale/ready-low evidence, but rejects a false end-to-end
    conclusion. RTL3.6-A now repairs the active terminal/reclaim replay
    provenance without changing its event contracts. The next remaining
    closure is a testbench-only same-instance live functional provider/R4/R6
    terminal composition. Sidecar transport and full-path reset-epoch
    composition remain separately explicit.
11. **RTL3.6-A — active replay provenance repair (complete).**
    [`rtl3_6a_active_replay_provenance_repair_contract.md`](rtl3_6a_active_replay_provenance_repair_contract.md)
    refreshes only the two runtime-loaded terminal/reclaim binding source maps
    after their original no-model suites pass, restoring the RTL2.6.5c replay
    preflight. It retains `rtl3_functional_realization_complete = false` and
    authorizes no live composition or realization claim.
12. **RTL3.6-B — same-instance static functional-provider/R4-terminal
    composition (complete, testbench-only).**
    [`rtl3_6b_same_instance_functional_provider_terminal_contract.md`](rtl3_6b_same_instance_functional_provider_terminal_contract.md)
    binds four versioned Python functional-provider packet fixtures through
    the existing Chisel source-packet/R4 structural boundary, then supplies
    only matching static Python R4-oracle terminal bytes to the real R6 and
    same-child R5 reclaim path. It removes manual packet/result injection from
    this witness, but retains the explicit S2 fill verification ingress and
    does not create live co-simulation, production RTL, or a numeric claim.
13. **RTL3.6-C1 — named S2 sidecar fixture transport (complete,
    testbench-only).**
    [`rtl3_6c1_sidecar_fixture_transport_contract.md`](rtl3_6c1_sidecar_fixture_transport_contract.md)
    replaces direct sidecar fragment/complete injection in the RTL3.2
    functional packed-read harness with a handle-keyed fixture transport fed
    only by a copied accepted allocation and exact S2 fill observation. It
    covers unknown-handle/count and stale-generation fail-closed cases while
    retaining reset-epoch composition and a full same-instance dataflow as
    the next RTL3 closure.
14. **RTL3.6-C2 — same-instance dataflow and reset-epoch composition
    (complete, testbench-only).**
    [`rtl3_6c2_same_instance_dataflow_reset_contract.md`](rtl3_6c2_same_instance_dataflow_reset_contract.md)
    joins real R3 publication, the frozen verification association, C1 typed
    delivery and sidecar transport, static R4 terminal fixture, real R6
    retirement, and same-R5 reclaim.  It also demonstrates stale-response
    suppression plus fresh dual-R1 init acknowledgements after destructive
    reset.  It remains a bounded witness with testbench verification facts and
    a separate source-read R1 port, not a production common-memory or
    controller implementation.  The next action is a cross-owner RTL3
    completion review, not a performance or PPA phase.
15. **RTL3.7-A — shared functional-memory object continuity (complete,
    testbench-only).**
    [`rtl3_7a_shared_functional_memory_continuity_contract.md`](rtl3_7a_shared_functional_memory_continuity_contract.md)
    derives the C2 source descriptor's payload handle from the accepted real
    R3 packed write and makes two independently reset functional-memory
    endpoints share that host-side object.  Its testbench store distinguishes
    an eight-fragment payload from a one-fragment descriptor at a coincident
    opaque `address_ref` only through the existing R1 expected-fragment count.
    It is neither a common controller/physical address format nor an
    autonomous C2-grant closure.
16. **RTL3.7-B — C2 terminal/release/retire ordering (complete,
    testbench-only).**
    [`rtl3_7b_terminal_release_global_drain_contract.md`](rtl3_7b_terminal_release_global_drain_contract.md)
    forwards each typed endpoint terminal to S2 but permits only the final
    terminal to form the existing packed-read association terminal. Its release
    observation must be accepted before the matching runtime retire reaches the
    existing R6/R5 drain/reclaim path. It neither changes C2 grant provenance,
    production-top topology, nor R6 global-membership collection. The next
    action is RTL3 completion cross-owner review 03.
17. **RTL3.7-C — C2 drain membership plus fault/stall/reset/event-scoreboard
    closure (complete, testbench-only).**
    [`rtl3_7c_drain_fault_stall_reset_scoreboard_contract.md`](rtl3_7c_drain_fault_stall_reset_scoreboard_contract.md)
    joins matching existing publication and C2 R1/R2 wrapper status facts
    before the unchanged R6 collector: dual R1 init/drain, R2 payload drain,
    and R2 descriptor drain.  It also records bounded observed-event order
    through legal C2 response backpressure and relies on directed stale-reset
    and endpoint-fault fail-closed evidence.  It adds no status code, global
    collector owner, production-top bridge, physical-memory realization, or
    deadlock/performance claim.  C2 grants, C1 sidecar fixture transport, and
    static partial/R4 fixtures remain open; the next action is RTL3 completion
    cross-owner review 03.
18. **RTL3 completion cross-owner review 03 (complete, no-PASS).**
    [`rtl3_completion_cross_owner_review_03.md`](rtl3_completion_cross_owner_review_03.md)
    confirms that RTL3.7-A/B/C close bounded C2 data continuity,
    terminal/release/retire ordering, and joined drain membership, but rejects
    a functional-realization pass.  The C2 grant producer, sidecar source,
    dynamic source-to-partial path, dynamic functional R4 path, production-top
    verification ingress, aggregate provenance replay, and full source-set
    coverage remain explicit.  It defines the narrower RTL3 functional-closure
    rubric without authorizing complete LLM inference, physical realization,
    or performance work.
19. **RTL3.8.0 — functional-closure ingress retirement contract (complete,
    planning only).**
    [`rtl3_8_0_functional_closure_ingress_retirement_contract.md`](rtl3_8_0_functional_closure_ingress_retirement_contract.md)
    freezes I0--I8: each test-only C2 grant, sidecar fixture, verification
    ingress, static partial/R4 fixture, and structural tie-off has one future
    owner or an explicit allowed outer environment.  It authorizes no Chisel
    activation; RTL3.8.1 must first bind the packed C2 activation facts without
    changing scheduling, authority, or publication semantics.
20. **RTL3.8.1 — packed activation binding (complete for production-shaped
    I0--I3 owner binding; I4 remains open).**
    [`rtl3_8_1_packed_activation_binding_contract.md`](rtl3_8_1_packed_activation_binding_contract.md)
    connects the exact R6 plan fork, R3 publication observation, R5 descriptor
    query/grant, S2 lease request/grant, association allocation through the
    existing packed lane, and final terminal association in the composed top.
    It retires only `verification_s2_service_req_in` and
    `verification_packed_s2_read_work_in`; sidecar verification ingress is
    still explicit for RTL3.8.2.  It adds no source selection, R2 policy,
    metadata authority, physical-memory/numeric realization, or PPA claim.
21. **RTL3.8.2 — functional sidecar delivery (complete for I4; I5--I8
    remain open).**
    [`rtl3_8_2_functional_sidecar_delivery_contract.md`](rtl3_8_2_functional_sidecar_delivery_contract.md)
    retires the top sidecar fragment/complete verification ingress and the
    prior fixture transport.  The accepted association's successful payload
    terminal gates one separately allocated `S2PackedSidecar` typed read using
    the existing registry/R2/R1 path; the typed endpoint serializes final
    sidecar fragment before S2 complete and maps sidecar fault only to S2
    fault.  It introduces no R2 class, priority, scheduler policy, metadata
    authority, memory/controller/numeric realization, or PPA claim.
22. **RTL3.8.3 — source/partial boundary isolation (complete for I5/I6
    isolation; live source realization remains open).**
    [`rtl3_8_3_source_partial_boundary_isolation_contract.md`](rtl3_8_3_source_partial_boundary_isolation_contract.md)
    retires the composed top's remaining P3/direct verification ingress,
    preserves an inactive carrier where a named R3/direct producer does not
    yet exist, and connects the sole named outer functional partial-provider
    packet boundary to the existing source-packet adapter.  It adds no K/V
    lease export, source selection, numeric computation, R4 result, R2
    policy, controller/macro, timing, or PPA claim.
23. **RTL3.8.4 — dynamic R4 functional-reference protocol activation
    (complete for I7/I8 protocol binding; numeric implementation remains
    external).**
    [`rtl3_8_4_dynamic_r4_functional_reference_contract.md`](rtl3_8_4_dynamic_r4_functional_reference_contract.md)
    replaces the exercised functional top's local R4 terminal tie-offs with a
    packet-receipt and exact-work-gated reference-environment boundary.  The
    existing pure-software RTL3.4-B oracle remains its only permitted numeric
    evaluator; this step adds neither Chisel FP/exp/MAC/RoPE arithmetic nor a
    physical/numeric RTL, controller/macro, timing, or PPA claim.
24. **RTL3.8.5 — full-path closure coverage (complete directed coverage;
    final RTL3 review remains separate).**
    [`rtl3_8_5_full_path_closure_coverage_contract.md`](rtl3_8_5_full_path_closure_coverage_contract.md)
    covers all seven legal nonempty source subsets, four R6/R4 consumer
    associations, success/fault, legal stall, stale response, and reset in a
    single elaborated functional-path harness.  It also fixes the discovered
    no-repeat-work handoff condition after an accepted R4 response.  Its
    completion observer and dynamic response fixture are test-only; it adds no
    source owner, numeric hardware, physical implementation, timing, or PPA
    claim.
25. **RTL3.9-A0 — pending-payload read-association closure (complete;
    pre-materialization).**
    [`rtl3_9_a0_pending_payload_read_association_contract.md`](rtl3_9_a0_pending_payload_read_association_contract.md)
    introduces the sole pending-payload owner's immutable identity/handle/
    generation binding and requires its exact atomic join with a retained R6
    admission pair before R3 records it beside the member ledger.  Existing
    `P3PackReadWork` is strengthened to reject a work item whose identity,
    opaque handle, generation, or endpoint does not equal that binding.
    The production top still ties P3 pack-read work inactive: RTL3.9-A must
    separately choose only a materialization mechanism, not a new scheduler
    or memory realization.
26. **RTL3.9-A1 — R3 materialization and P3-ingress exclusion contract
    (complete; pre-activation).**
    [`rtl3_9_a1_r3_materialization_ingress_exclusion_contract.md`](rtl3_9_a1_r3_materialization_ingress_exclusion_contract.md)
    freezes `route_a_m2_p3_wrapper` as the only future materializer of a
    pending member's exact A0 binding into a C2 eight-fragment pack-read work
    item and matching position sidecar. It scopes a one-active-item,
    ordinal-ascending functional baseline without selecting a permanent R2/R3
    schedule, and makes hot/P3 payload plus sidecar exclusion explicit and
    fail-closed. The top work tie-off and packed-write inertness remain until
    RTL3.9-A provides directed functional activation coverage.
27. **RTL3.9-A — R3 pending pack-read functional activation (complete).**
    [`rtl3_9_a_r3_pending_pack_read_activation_contract.md`](rtl3_9_a_r3_pending_pack_read_activation_contract.md)
    removes only the production top's inert P3 pack-read-work tie-off. R3
    materializes A0-bound member work and matching sidecar from its immutable
    ledger, reuses the existing checked R2/R1/typed endpoint path, and guards
    both hot/P3 ingress forms with fail-closed exclusion. Packed write,
    publication, and authority semantics remain unchanged and inert here.
28. **RTL3.9-B0 — durable-write/publication association audit (complete;
    pre-activation).**
    [`rtl3_9_b0_durable_publication_association_contract.md`](rtl3_9_b0_durable_publication_association_contract.md)
    freezes the exact R3 stage/page/tag association across the existing
    packed-write candidate, R2/R1 typed terminal, R5 descriptor prerequisite,
    publication visibility acknowledgement, and R6 authority acceptance. It
    leaves both top packed-write carriers inert and authorizes only B1's
    narrow write-path activation.
29. **RTL3.9-B1 — R3 automatic packed-write activation (complete).
    **
    [`rtl3_9_b1_r3_packed_write_activation_contract.md`](rtl3_9_b1_r3_packed_write_activation_contract.md)
    records that the production-shaped candidate path was already composed:
    RTL3.9-A can now make the R3 stage complete, which reaches R3's sole
    request-plus-eight-fragment packed-write candidate, then the existing
    R2/R1/registry/router typed terminal and R3 payload-durable fact. The
    historical direct `p3_packed_write_issue`/`terminal` test carriers remain
    inactive. B1 explicitly does not make payload durability publication,
    visibility, or authority.
30. **RTL3.9-B2 — R5 descriptor-durability functional activation (complete).
    **
    [`rtl3_9_b2_descriptor_durability_activation_contract.md`](rtl3_9_b2_descriptor_durability_activation_contract.md)
    starts with the A0-bound R3 materializer feedback rather than injected
    work/sidecar, reaches R3 payload durability, then the existing R5 append
    candidate and its typed R2/R1 terminal.  Only that matching descriptor
    terminal enables R5's prerequisite and the first R3 M2-member request;
    stale/mismatched append delivery remains fail-closed at the existing typed
    R2/R5 boundary.  Publication, visibility,
    and authority remain deferred to RTL3.9-B3.

RTL3 completion may establish functional owner/model closure only. It remains
insufficient evidence for physical SRAM/HBM macros, controller realization,
final FP/exp pipeline, frequency, timing, throughput, area, energy, PPA, or
Gate-B.

## Stage boundary after RTL2 and planned RTL3

```text
RTL1 control-plane verification (complete)
        -> RTL2 constrained transaction/dataflow closure (testbench-only)
        -> RTL2 completion review
        -> RTL3 functional realization closure
        -> physical/numeric implementation realization
        -> profiling
        -> optimization
        -> synthesis / timing / PPA / Gate-B
```

Profiling begins only after the relevant functional realization and a separate
physical/numeric realization have been selected and verified. It must not
retroactively turn RTL2 functional storage, the RTL3 functional memory
environment, a replaceable partial producer, or an R4 functional merge model
into physical-performance evidence.
