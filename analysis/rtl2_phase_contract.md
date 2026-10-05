# RTL2 — Production Transaction/Dataflow Integration

**Status:** `rtl2_1a_to_1c_atomic_publication_implemented_directed_tested;
rtl2_2_0_provenance_reconciled; rtl2_2_1_registry_association_implemented_directed_tested;
rtl2_2_2_typed_write_delivery_implemented_directed_tested;
rtl2_2_3_functional_storage_implemented_directed_tested;
rtl2_2_4_read_delivery_context_implemented_directed_tested;
rtl2_3_0_read_issue_contract_implemented_directed_tested;
rtl2_3_c5_source_packet_r4_implemented_directed_tested_limited_protocol_closure;
rtl2_3_r_active_phase_reconciled_no_behavioral_activation;
rtl2_3_c6_source_plan_binder_implemented_directed_tested`.

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
2. **C7:** composition-only top binding of the accepted plan copy, source-owner
   availability, and existing packet adapter;
3. **C8:** all-mask four-consumer commit/release association through R6
   `merge_req`; and
4. **C9:** one authorized top composition path replacing the isolated C2/C3/C4
   endpoint witnesses, without representing opaque verification fragments as
   numeric source partials.

Only C6--C9 permit an RTL2.3 `control_protocol_complete` review disposition.
They do not authorize a source scheduler, numeric attention computation,
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

## RTL2.5 — Active-state reset, fault, retirement, and reclaim

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

RTL2.0--RTL2.5 passing individually does not by itself complete production
dataflow integration.  A separate completion review must consume the explicit
scoreboard events and demonstrate at least one complete retained transaction:

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
separate numeric/memory-realization planning.  It does not authorize profiling,
optimization, synthesis, timing, or PPA claims by itself.

## Stage boundary after RTL2

```text
RTL1 control-plane verification (complete)
        -> RTL2 production transaction/dataflow correctness
        -> RTL2 completion review
        -> numeric and memory realization gates
        -> profiling
        -> optimization
        -> synthesis / timing / PPA / Gate-B
```

Profiling begins only after an appropriate numeric/memory realization has been
separately selected and verified.  It must not retroactively turn the RTL2
functional storage or R4 result stub into physical-performance evidence.
