# MR-1B — Direct-pending cross-owner association contract proposal

**Status:** `revised_proposed_waiting_user_approval`; no RTL change is
authorized by this document.

## Narrow purpose and revision decision

MR-1B closes only this missing association:

```text
R6-accepted pending SourceInstance
  -> immutable pending-payload descriptor and one accepted read lease
  -> DirectPendingReadWork / typed endpoint / source completion
```

It does not select a source, alter `SourceCompletionPlan`, add an authority
owner, alter admission, publication, page size, GQA legality, or R2 ordering.
`SourceInstance` remains neither a payload handle nor an address.

This revision makes five decisions that the first proposal left open:

1. The **pending-payload descriptor/location owner**, not the source-plan
   declaration owner and not R3, produces all payload/sequence provenance.
2. R3's admitted-member/binding ledger is **not** a universal direct-pending
   query source. It remains the pack-read ledger only.
3. R6 `SourceInstance`, pending-storage generation, and endpoint-local
   generation remain distinct identities with an explicit open acknowledgement
   relation; none is substituted for another.
4. The selected lifetime rule is a single immutable **accepted-read lease**.
5. A permanent association failure becomes one typed lifecycle failure, not
   indefinite `ready-low`, a fabricated source release, or a success terminal.

The current live production sources do not carry `source_last` or a complete
direct-pending descriptor. Consequently the necessary descriptor carrier is a
real interface addition, not a field that an existing top-level source-plan
producer may infer from group count, logical position, response `last`, or
private endpoint state.

## Provenance owner and immutable carrier

Add `PendingDirectAssociationDeclaration`, produced solely by the existing
logical **pending-payload descriptor/location owner**. That owner is the
authority for an already-selected pending payload's location and descriptor
facts; it gains no R6 source-selection or residency-authority role. It may
emit a declaration only after it has received the already-selected pending
`SourceInstance` from the declaration-side integration boundary and checked
that instance against its immutable descriptor. It cannot choose a different
instance.

The declaration is paired with `SourcePlanDeclaration` before R6 acceptance.
The source-plan declaration owner supplies only the selected source set; the
pending-payload descriptor owner supplies the association facts below. The
binder accepts neither half by itself when pending presence is set.

| Field | Sole legal production source | Binder/materializer check | Forbidden derivation |
| --- | --- | --- | --- |
| `transaction_identity` | both paired declaration owners | exact pair equality and later R6-copy equality | entry ID or payload reference |
| `pending_instance` | source-plan declaration owner; echoed only after descriptor-owner validation | exact equality with pending plan instance | endpoint observation or local generation |
| payload handle/address | pending-payload descriptor/location owner | copied unchanged into direct work | `payload_ref`, P3 state, or R1 response |
| pending-storage generation | pending-payload descriptor/location owner | exact lease and typed-read identity | R6 or endpoint generation |
| destination endpoint | pending-payload descriptor/location owner | exact work/lease equality | a default endpoint |
| `pending_ordinal` | immutable pending-source descriptor | direct record terminal order | logical position or group ordinal |
| `source_last` | immutable pending-source descriptor | copied unchanged to typed terminal | eighth-fragment `last`, group count, or absent next record |
| `valid_count` | direct descriptor's frozen one-record declaration | exact `1` in the first MR-1B scope | R3 `group_valid_records` |
| optional pack-member cross-reference | descriptor owner, if the same member is later packed | optional non-mutating R3 validation only | a requirement that all direct sources occupy R3's ledger |

The descriptor owner must form and retain `pending_ordinal` and `source_last`
at pending-payload descriptor creation/maturity, before declaration pairing and
before R6 plan acceptance. It must preserve them unchanged until the
associated lease resolves. Current code has no production carrier for this
fact: introducing it is mandatory, and source-plan-side reconstruction is
prohibited.

### Executable unique-key and descriptor-production rule

`SourceInstance` alone is not a payload key: its current fields are only
`{source_kind, instance_coordinate, generation}` and do not name a KV record,
address, layer/head/position, or `source_last`. MR-1B therefore requires one
new immutable `PendingDescriptorKey`:

```text
{ pending_descriptor_ref, pending_descriptor_generation }
```

and a production `PendingSourceDescriptorRegistration` record:

```text
PendingDescriptorKey
+ { layer, kv_head, logical_position, payload_ref }
+ { payload_handle_or_address, pending_storage_generation, destination_endpoint }
+ { pending_ordinal, source_last, valid_count = 1 }
```

The pending-payload descriptor/location owner creates that registration at the
same accepted pending-maturity event that establishes the immutable
pending-payload location. `source_last` must arrive on this registration as an
already-declared end-of-source fact from the pending-source descriptor builder;
that builder is the sole producer of the fact and may not derive it from a
page/group count, a missing neighbour, an R1 fragment, or a later attention
plan. The descriptor/location owner stores the literal bit with the rest of
the immutable descriptor and is only a custodian thereafter.

The source-plan declaration side additionally emits the selected
`PendingDescriptorKey` beside its selected `pending_instance`. The key is a
selection association supplied by the existing source-plan declaration
boundary, not a handle/address invented by the binder. The pending descriptor
owner validates exactly:

```text
{ attention transaction_identity, pending SourceInstance,
  PendingDescriptorKey, pending_storage_generation }
```

against its immutable registration before issuing
`PendingDirectAssociationDeclaration`. This proves which descriptor belongs to
which selected pending source without treating `SourceInstance` as an address.
The plan-side source selector is still responsible only for selecting an
already-described source/key pair; the descriptor owner remains the sole
authority for all payload, generation, ordinal, and terminal facts.

These two carriers are not present in the current Chisel production graph.
They are unavoidable minimal interface additions, not an assertion that an
unnamed existing owner already provides the mapping. The descriptor-directory
state, association comparison, lease state, and their dynamic accesses are
Route-A incremental **direct-pending transport/control** cost. The opaque
payload and descriptor backing addressed by the record remain declared
external-memory-service cost; neither may be silently charged as zero.

## Coverage boundary: R3 is not the direct association owner

The existing R3 ledger contains admitted retained members for P3 pack-read
materialization. It does not prove coverage for every pending `SourceInstance`:
it has a different admission purpose and may be released/reused while an
attention plan still names a pending source. Therefore MR-1B removes the
earlier proposed R3 read-only lookup from the direct path.

The pending-payload descriptor/location owner must cover every pending source
that may legally occur in `SourcePlanDeclaration`. Pairing rejects a source
plan declaration with pending presence if the exact descriptor declaration is
not available. R3 may receive an optional matching member cross-reference for
diagnostic, non-mutating consistency validation, but its result cannot create,
block indefinitely, or revoke direct work. Pack-read and direct read may
observe the same immutable location facts without either becoming the other's
membership or authority owner.

## Exact pairing, endpoint identities, and one work item

The following interface changes are unavoidable.

1. `RouteASourcePlanBinder` gains a paired
   `PendingDirectAssociationDeclaration` ingress and an immutable
   post-acceptance association-copy egress. For a plan with pending presence,
   it accepts the plan only when both valid carriers have equal identity and
   `pending_instance`; it holds the pair stable under backpressure. Its plan
   output handshake with R6 is the actual acceptance boundary. Only after that
   handshake may the association copy become visible downstream. A plan without
   pending presence requires no companion carrier.
2. `DirectPendingOpen` gains the accepted `pending_instance`. The direct
   endpoint latches that R6 identity **and** independently increments its
   existing endpoint-local generation on open. It emits a new
   `DirectPendingOpenAck { identity, accepted_pending_instance,
   endpoint_generation }` only after this state is live.
3. The association materializer joins the R6-accepted association copy,
   `DirectPendingOpenAck`, and the accepted-read lease. It emits exactly one
   `DirectPendingReadWork` using the descriptor owner's handle, destination,
   ordinal, and `source_last`, and the endpoint's local generation. It is not
   a selector, authority table, queue, or scheduler.
4. The endpoint uses endpoint-local generation only for typed R1/direct
   fragment and terminal matching. Its GQA commit and `direct_release_out`
   use the latched R6 accepted `pending_instance`. Thus reset, endpoint reuse,
   stale R1 responses, and generation wrap retain the old local transport
   guard while R6 sees the source identity it actually accepted.

The opening materializer must preserve an immutable record under downstream
backpressure and admit it once. Duplicate declarations, duplicate open acks,
or duplicate work cannot produce a second lease or R1 request.

## Exact R2/R1/lease handshake and authority-transition race

The selected lifetime rule is one immutable **accepted-read lease**, owned by
the pending-payload descriptor/location owner. It is not a new residency
authority and does not delay or split pending-to-packed atomic publication.

The current R2 has these distinct events:

| Event | Current meaning | Lease effect in MR-1B |
| --- | --- | --- |
| `direct_candidate_in.fire` | candidate is stored in an R2 class slot | no lease; this is only queue ingress and may later become stale |
| R2 selection | combinational choice of the oldest eligible stored candidate | no architectural grant handshake exists yet |
| `r2.core_mem_req.fire` | selected candidate is accepted by R1 | this is the **direct lease-acquire fire** |
| `r1.core_mem_req_in.fire` | same wire handshake as the preceding R2 fire | identical event |
| `external_core_mem_if_v1.request.fire` | R1 issues the exact request externally | identical event in the current R1, because R1 only raises ready when the external request is ready |

Thus MR-1B does **not** acquire a lease at R2 ingress. It introduces a
direct-class-only pre-issue gate: a selected direct candidate may assert
`core_mem_req.valid` only when the descriptor owner accepts a matching
`DirectPendingLeaseAcquire`. That handshake and
`r2.core_mem_req.fire`/R1/external-request fire occur in the same cycle. The
lease owner checks the descriptor key, descriptor generation, accepted pending
instance, and current pending authority at that exact edge, then records one
lease through the matching typed direct terminal.

This is an explicit, limited **R2 semantic interface extension**: the direct
class gains a descriptor-owner proof at its existing issue fire. It does not
add a queue, change candidate ordering, alter the round-robin cursor rule, or
create a second arbiter. The cursor still advances only on the existing
`core_mem_req.fire`. Before a direct candidate has a grantable lease, R2 treats
it as not issue-eligible and may select another already-eligible class using
the frozen ordering rule.

There is no combinational handshake loop: registered R2 candidate fields
drive lease-acquire `valid`; descriptor-owner `ready` depends only on its
registered descriptor/authority/lease state, never on R2 ready, R1 ready, or
external ready; R2 exposes `core_mem_req.valid` only from the registered
candidate plus lease-ready condition. R1/external ready can withhold the
single joint fire without mutating the candidate, descriptor, or lease. A
lease is accepted once because R2 removes the candidate only at the joint
fire, while the owner marks the exact key live at that same edge.

The resulting race rule is:

1. pending-to-packed before the joint fire: descriptor-owner lease `ready`
   stays low; no R2/R1/external request fires. The association enters the
   failure/abort path below.
2. pending-to-packed after the joint fire but before any response: the request
   continues. The live lease pins only response validity for the exact
   handle/storage generation through terminal; authority remains solely with
   the already-completed atomic transition.
3. R1 fault or malformed response after the joint fire uses the typed endpoint
   terminal path; it is not reclassified as an association failure and cannot
   create delivery/release.
4. the matching terminal (success or fault) releases the one lease. GQA
   source-release remains a later, distinct lifecycle event and never retains
   a memory-read lease.

## Temporary backpressure versus permanent failure

`ready-low` is permitted only while a pair is incomplete, the direct endpoint
is occupied, or a lawful lease response is temporarily backpressured. It may
not be the response to a known missing/mismatched descriptor after R6 accepts
the plan.

Add `DirectPendingAssociationFailure { transaction_identity, pending_instance,
endpoint_generation, reason }`. The binder/materializer emits it exactly once
when an R6-accepted pair cannot open, cannot acquire the joint R2/R1 lease
because authority has transitioned, or finds an immutable
identity/key/generation/descriptor mismatch.

This requires a separate **R6 lifecycle interface extension**, not an adapter
terminal: `RouteALifecycleAdapter` gains a matching pending-source-failure
input. It accepts the event only for its live R6-accepted plan, and **R6**
alone asserts the existing outward `attention_terminal_rsp` with fault status.
The adapter cannot assert a terminal directly. R6 performs no source release,
GQA commit, merge/R4 success, or retire acknowledgement for that failed plan;
it clears the attention tracker only when its one outward fault terminal fires.

If an endpoint has opened but the joint R2/R1/lease fire has not occurred,
the materializer first sends `DirectPendingAbort { transaction_identity,
pending_instance, endpoint_generation }`. The endpoint accepts abort only
while active, nondeliverable, and before its `DirectPendingIssueObservation`
has fired; it clears its local occupancy and returns an abort acknowledgement.
Only after that acknowledgement may the materializer send the association
failure into R6. The same reset clears endpoint, materializer, descriptor
lease, and R2 candidate state.

After `DirectPendingIssueObservation` (the joint R2/R1 fire), abort is illegal:
the endpoint must await its typed R1 terminal so a late response cannot become
an unconsumed outstanding delivery. A fault/malformed terminal then emits the
same R6 pending-source-failure input with the exact endpoint/accepted-instance
identity. This produces the R6-owned outward fault terminal rather than
leaving an opened endpoint, R2 outstanding slot, or lifecycle tracker stuck.

Pre-acceptance absence is intentionally different. If a plan declaration has
pending presence but its companion descriptor declaration is absent, the binder
applies ordinary pre-acceptance backpressure and does not send a plan to R6;
there is no accepted plan and therefore no association-failure terminal. Once
R6 has accepted the paired plan, every permanent failure follows the bounded
R6 path above.

Reset clears paired binder state, association materializer state, endpoint
state, and live leases. A stale declaration, lease response/release, terminal,
or failure must match both transaction identity and its relevant accepted
instance/generation; otherwise it is rejected without a deliverability,
success terminal, release, or retire effect.

## Final minimum RTL scope if approved

Approval of this revised contract authorizes only the following MR-1B work:

- `RouteAInterfaces.scala`: association declaration, endpoint open/ack,
  descriptor registration/key, direct lease, issue/abort/ack, and typed
  association-failure carriers;
- `RouteAIncrementalSkeletons.scala`: paired binder retention, endpoint
  accepted-instance/local-generation relation, descriptor-owner registration
  and lookup boundary, R2 direct-class pre-issue lease gate, lease-gated
  association materializer, endpoint abort, and lifecycle failure input;
- `RouteAMeasurementDut.scala`: production descriptor-owner boundary plus the
  owner-to-owner direct producer, delivery, terminal, release, and failure
  connections, with no test-only provider or tie-off;
- directed tests for exact success; descriptor/instance/storage-generation
  mismatch; missing pre-acceptance counterpart; endpoint reuse; stale/reset;
  duplicate; plan/open/lease/R2/R1 backpressure; R1 fault/malformed response;
  abort-before-issue; no-abort-after-issue; and both sides of pending-to-packed
  around the joint R2/R1 lease fire; plus W0/MR-1A non-regression and
  structural guards.

The approved scope is **single-record MR-1B only**: `valid_count = 1` and one
immutable `source_last` descriptor fact. A passing MR-1B implementation is not
evidence of multi-record direct-pending coverage; any such extension requires
a separately reviewed multi-record association, lease, terminal, and test
contract.

The direct-pending source must still be an explicit functional-memory boundary;
this proposal does not add an HBM controller, memory macro, attention PE,
numeric implementation, timing, throughput, PPA, or physical-memory claim.
