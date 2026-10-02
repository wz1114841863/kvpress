# RTL2 — Production Transaction/Dataflow Integration

**Status:** `rtl2_0_pre_behavior_completion_passed; rtl2_1a_behavioral_entry_authorized`.

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

**Status:** `rtl2_0a_to_0g_closed; completion_review_passed;
behavior_not_started; rtl2_1a_only_authorized`.

[`rtl2_0_activation_contract.md`](rtl2_0_activation_contract.md) and its
machine-readable manifest complete the fail-closed owner/event inventory.  It
finds seven explicit hierarchy/interface/testbench-boundary amendments needed
to activate production carriers without making the top a producer or a second
authority owner. The separate completion review has now checked the seven
closures and created the required versioned scoreboard schema, but no
top-inert carrier has been behaviorally enabled.

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
Its narrow PASS authorizes only RTL2.1a; it does not claim that any carrier,
payload path, or numeric path is behaviorally active.

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
| RTL2.1b | Drive the unique R2-to-R1 payload-write transaction and the R5 descriptor-maintenance prerequisite; emit identity-bearing `write_commit` and `descriptor_durable` only from their owners. | Treating a write commit as metadata visibility or authority transfer. |
| RTL2.1c | After every required payload and descriptor prerequisite is durable, perform the sole nested `metadata_publish_commit`, emit the exact `pending -> packed` authority transition, and make the page readable. | Partial-group visibility, duplicate commit, or a pending/packed authority overlap. |

This slice retains the exact existing admission result; it neither changes
pruning nor invents a new policy.  Fault and stall tests must demonstrate that
no incomplete group becomes visible and that no token has zero or duplicate
authoritative residency.

## RTL2.2 — Read-fragment delivery versus write-terminal delivery

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

## RTL2.3 — Replaceable functional P3/S2 storage boundary

P3 and S2 payload handling is introduced only behind a replaceable functional
storage interface:

```text
functional storage interface
        |
        +-- simulation/reference backing
        |
        +-- future SRAM realization
```

The present backing may verify fragment write/read, byte/sidecar preservation,
validity, identity/generation, and owner-only access.  It is not an SRAM macro
selection disguised as an implementation.  In particular, an arbitrary
register `Vec` backing must not be documented or treated as the eventual macro,
port count, latency, dynamic access energy, leakage, or physical layout.

The 32-KiB S2 payload capacity and its sidecar are logical resource contracts;
the P3 envelope is likewise a logical service/placement contract.  Neither
authorizes a physical macro, port count, or timing claim.  P3/S2/direct
transport copies never count as authoritative residency.

## RTL2.4 — Source service and multi-source composition

Connect owner-produced hot, direct-pending, and packed/S2 source facts to the
frozen source-instance and four-consumer protocol.  A source becomes
deliverable only after its own validity prerequisites; all four distinct GQA
consumer commits are required before its exact generation-bearing release.
The source mask and canonical order remain frozen as `hot -> pending -> packed`;
the RTL must not claim that arbitrary source reordering is bitwise equivalent.

The result is a functional source packet/fragment path, not a source scheduler,
HBM bandwidth model, or numeric merge implementation.

## RTL2.5 — R4 boundary activation with replaceable result stub

Activate the existing R4 packet/result/fault boundary using a deterministic
verification result stub.  The stub may issue an identity-matching success or
one numeric fault after a valid source-completion association, so that R6 has
one outward terminal route.  It may not be represented as an exp, floating
point, precision, partial-softmax, online-merge, latency, or numeric-correct
implementation.

The frozen R4 boundary remains the replaceable contract for
`merge_req`, partial header/value fragments, `merge_rsp`, and `numeric_fault`.
The actual numerical implementation is a later realization sub-gate.

## RTL2.6 — Active-state reset, fault, retirement, and reclaim

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

## RTL2 completion review

RTL2.0--RTL2.6 passing individually does not by itself complete production
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

The success branch may use the RTL2.5 result stub; no real floating-point merge
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
