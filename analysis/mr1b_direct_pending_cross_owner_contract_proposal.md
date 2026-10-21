# MR-1B — Direct-pending cross-owner association contract proposal

**Status:** `implementation_in_progress`; the user approved the bounded
single-record MR-1B RTL scope on 2026-10-19. Each implementation batch remains
subject to its listed directed and non-regression checks.

## Implementation record — batch 1: provenance to pre-lease work

Batch 1 implements the real owner chain from pending descriptor registration
through descriptor-owner validation, R6 plan acceptance, exact endpoint
open/ack, and immutable `DirectPendingReadWork` into the pre-existing
R2/R1/registry/typed-endpoint path. The descriptor key stays outside
`SourceCompletionPlan`; R3's pack-read ledger is not queried. The endpoint now
retains the accepted R6 pending `SourceInstance` separately from its local
transport generation, so GQA commit/release use the accepted instance while
typed R1 fragments retain the local generation guard.

This batch intentionally does **not** claim lease, direct-class cancellation,
pending-to-packed race, or R6 failure completion. Those approved carriers are
the next implementation batch and remain fail-closed/inactive until connected;
no direct candidate is granted a lease merely by this batch's work creation.

### Batch-1 verification record

On 2026-10-19, the local no-model Chisel compile and the following bounded
checks passed after the production wiring change:

```text
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
testOnly RouteASourcePlanBinderSpec                 3/3
testOnly RouteAS2DirectPendingSpec                  3/3
testOnly RouteADirectPendingReadPathSpec            5/5
testOnly RouteAResetEpochIntegrationSpec            4/4
testOnly RouteAFourConsumerCompletionSpec           3/3
testOnly RouteAMeasurementDutR3Spec                 3/3
testOnly DualMeasurementDutStructuralSpec           2/2 (including B1 direct owner-chain guard)
git diff --check                                    pass
```

The reset rerun also elaborated the legacy composition-only
`RouteAKVSubsystemTop`. Its newly added MR-1B ports are explicitly tied
fail-closed there because that historical shell is not a descriptor owner or a
measurement DUT. This is an elaboration closure only; the production
owner-to-owner connection is exclusively in `RouteAMeasurementDut`.

## Implementation record — batch 2a: R2 stored-candidate causality

Batch 2a adds `DirectPendingAssociationId` to the immutable work and typed
direct descriptor. The ID contains only the accepted transaction, pending
`SourceInstance`, descriptor key, and endpoint-local generation. It carries
unchanged through the existing producer/registry/R2 direct-class path. R2 now
emits `DirectPendingCandidateAccepted` only on the existing direct candidate
ingress fire, after that exact candidate has been stored. The materializer
holds its one association in `AwaitCandidate` until this matching observation
arrives, so it cannot duplicate work or silently treat producer-side work fire
as R2 acceptance.

This is deliberately not a lease, grant, cancellation, or authority update:
R2's class ordering and cursor update remain at `core_mem_req.fire`, and no
new candidate is made issue-eligible by this carrier.

Verification on 2026-10-19:

```text
testOnly RouteASourcePlanBinderSpec            3/3
testOnly RouteADirectPendingReadPathSpec       5/5
testOnly DualMeasurementDutStructuralSpec      2/2
git diff --check                               pass
```

The structural guard now requires the materializer's accepted-observation
connection to R2 in addition to the batch-1 owner chain.

## Implementation record — batch 2b: read-only eligibility and joint issue lease

Batch 2b connects the pending descriptor owner's read-only eligibility query
and its state-changing lease commit to the existing R2 direct class in
`RouteAMeasurementDut`. A direct candidate is first stored by the pre-existing
R2 ingress. R2 then queries the exact immutable association ID and storage
generation; a descriptor-owner response merely caches grantability for that
stored slot. It does not allocate a lease.

Only after the existing R1 path reports the external request ready does R2
present `DirectPendingLeaseCommit`. The shared request is valid only while the
owner is ready to commit, so `r2.core_mem_req.fire`,
`r1.core_mem_req_in.fire`, `external_core_mem_if_v1.request.fire`, and the
lease-commit fire coincide. No external ready means no lease commit or owner
state mutation. The production route connects all three channels directly:

```text
R2 direct stored slot
  -> PendingDescriptorOwner.lease_eligibility_query_in
  -> R2 cached read-only eligibility
  -> PendingDescriptorOwner.lease_commit_in at existing joint issue fire
```

The Full-KV measurement DUT and the historical composition-only top keep these
Route-A-only sideband ports inactive. The latter is not used as a measurement
DUT. The legacy direct-path regression was upgraded to register a matching
production descriptor owner; it no longer ties off lease traffic or supplies a
fabricated eligibility response. Its directed ready-low check observes that no
lease commit is asserted until the real external request becomes ready.

Verification on 2026-10-19:

```text
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'  pass
testOnly RouteADirectPendingReadPathSpec                                      5/5
git diff --check                                                              pass
```

`RouteACoreSideArbiterSpec` is temporarily not a valid execution signal after
this carrier expansion: its direct-root ChiselSim Verilator bridge emits calls
for several nested association fields without the corresponding DPI symbols.
The same R2 implementation is exercised as a child in the passing production
descriptor-owner path above. This is a simulator bridge/code-generation defect
at that root interface, not a semantic failing assertion; it must be repaired
or replaced by a flattened R2 harness before the final MR-1B non-regression
record. It does not authorize skipping the later cancel, transition, abort,
R6-terminal, or lease-release directed cases.

## B2c transition-association amendment — approval required

This is a narrow correction for the already-approved B2c cancellation scope.
It neither changes R6 authority nor makes the descriptor owner a residency
owner. It supplies the missing provenance needed for that owner to withdraw
**read eligibility only** after an accepted R3 pending-to-packed transition.

### Audit result

`PendingPayloadReadBinding` is the real pending-payload/location-owner carrier
and already contains `{ transaction_identity, entry_id, transaction_group_tag,
source_generation, layer, kv_head, logical_position, payload_ref,
group_member_ordinal, group_valid_records }`. The R3/M2 owner stores that
binding at its accepted admission join and emits the actual
pending-to-packed `R6AuthorityTransition` only for that stored entry.

The current `PendingSourceDescriptorRegistration` has neither `entry_id` nor
group tag/member scope, and the current transition has neither transaction
identity nor pending-storage generation. Consequently neither carrier alone
can identify a direct descriptor. Adding only `entry_id` would still admit a
stale tag/generation or a same-entry multi-record ambiguity; no RTL may infer
the missing fields from a source instance, ordinal, R3 private state, or a
payload address.

### Minimal proposed carrier change

1. Extend the immutable descriptor-owner registration with the copied
   provenance fields `{ entry_id, transaction_group_tag,
   group_member_ordinal, group_valid_records }`. The pending-payload
   descriptor/location owner must copy them from its own
   `PendingPayloadReadBinding` at descriptor creation; the existing
   `pending_storage_generation` must equal that binding's `source_generation`.
   The descriptor owner validates the complete equality of transaction,
   entry, tag, layer/head/position, payload reference, member scope, and
   storage generation before registration becomes live.
2. Add one read-only R3 accepted-event observation,
   `PendingToPackedReadEligibilityWithdrawal`, emitted only on the existing
   accepted pending-to-packed authority-transition fire. It carries exactly
   `{ transaction_identity, entry_id, transaction_group_tag,
   pending_storage_generation }`, copied from the stored pending binding and
   the accepted transition. It is not an authority command, source selector,
   or second residency table.
3. The descriptor owner matches this observation against its immutable
   registration key `{ transaction_identity, entry_id, transaction_group_tag,
   pending_storage_generation }`. Before lease commit it permanently withdraws
   eligibility and emits the existing B2c cancellation/failure sequence; after
   lease commit it retains the exact live lease until its matching typed R1
   terminal. If transition acceptance and issue would otherwise coincide, the
   accepted withdrawal has priority, so no issue or lease commit fires.

For the approved `valid_count = 1` MR-1B scope, duplicate live direct
registrations for this key are rejected fail-closed. A future one-entry to
multiple-direct-record scope must retain an explicit set of immutable
`PendingDescriptorKey`s and apply the one accepted withdrawal observation to
every matching record; it cannot choose one record by ordinal or address.

### Required B2c tests after approval

- exact transition withdraws a stored pre-issue candidate; unrelated entry,
  stale tag, or stale storage generation does not;
- duplicate registration is rejected in the single-record scope;
- matching transition with external ready-low and transition/issue same cycle
  produces no R1 request or lease commit, then performs exact cancel/abort/R6
  fault handling;
- transition after joint issue preserves only the matching lease through typed
  terminal, and transition thereafter cannot admit a new candidate.

This amendment requires the two carrier changes above. It is submitted for
authorization before B2c RTL implementation.

### Implementation precondition found after approval — additional observation required

The two changes above are necessary but not sufficient for an executable
owner-to-owner proof in the current live graph. The registration currently
enters `RouteAMeasurementDut` on an independent outer channel, while the real
`PendingPayloadReadBinding` is consumed by the atomic
`AdmissionPublicationIngressAdapter` three-way acceptance. There is no common
accepted event from which the descriptor owner can verify that a registration
actually names the binding R3 accepted. Field equality on an independently
injected registration would not establish that fact.

Before B2c RTL, add one more read-only carrier:

```text
AcceptedPendingPayloadBindingObservation { PendingPayloadReadBinding }
```

It is produced by the admission owner only after its existing atomic
`admission-context + R6 hot->pending authority + pending-payload-binding`
fire. The descriptor owner stores this immutable observation and accepts a
direct descriptor registration only on complete equality with it, including
the added entry/tag/member fields and `pending_storage_generation ==
source_generation`. It emits no authority, allocation, or source-selection
event.

The withdrawal must also be an **atomic fanout** of the existing R3
pending-to-packed transition: lifecycle/R6 and descriptor-owner withdrawal
arms fire together from the one M2P3 transition offer. A later queued
observation is insufficient because it could permit a conflicting R2 issue in
the accepting cycle. The descriptor owner may deassert the matching
lease-commit readiness combinationally while that exact offered transition is
valid; the transition has no effect unless the shared fanout fires. This
preserves R6 as sole authority and makes no delayed observation masquerade as
same-cycle arbitration.

These two wiring/observation requirements are an implementation-scope
expansion beyond the originally approved two carrier edits. No B2c RTL is
authorized by this document until they are explicitly approved.

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

The `DirectPendingReadWork`/candidate exists before any lease commits. The
lease is state only at the later joint R2/R1 issue edge; it is never a
precondition for constructing or retaining the immutable work record.

This implementation-level revision closes exactly three protocol points before
RTL work: (a) work/candidate custody precedes lease state, (b) a stored but
unissued direct-class candidate has an acknowledged cancellation path, and
(c) lease eligibility is read-only and separate from the issue-edge state
commit, including a deterministic pending-to-packed same-cycle priority.

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
3. The association materializer joins only the R6-accepted association copy
   and `DirectPendingOpenAck`. It then emits exactly one immutable
   `DirectPendingReadWork` using the descriptor owner's handle, destination,
   ordinal, and `source_last`, and the endpoint's local generation. The work
   is retained by the existing direct-class candidate slot before any lease
   exists; it never waits for, carries, or implies a committed lease. It is
   not a selector, authority table, queue, or scheduler.
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

Thus MR-1B does **not** acquire a lease at R2 ingress. The exact sequence is:

1. The association materializer creates immutable
   `DirectPendingReadWork { DirectPendingAssociationId, descriptor facts }`
   before a lease exists. Its existing zero-buffer producer/bridge chain is
   required to preserve the assertion `work_in.fire iff
   r2_direct_candidate_in.fire`; that fire stores the candidate in R2 and
   emits `DirectPendingCandidateAccepted` back to the materializer.
2. R2 sends a read-only `DirectPendingLeaseEligibilityQuery` for the stored
   association ID. The descriptor owner returns an exact
   `DirectPendingLeaseEligible` response only while the descriptor is live,
   the accepted pending instance/key/generation match, and pending authority
   is currently present. This response changes no lease state.
3. A selected direct slot with a matching cached eligibility response may
   expose the existing `core_mem_req` request. In the same cycle that R1 and
   the external port make that request fire, R2 presents
   `DirectPendingLeaseCommit`. The descriptor owner rechecks the same facts
   and commits the one lease only on that joint fire.

`DirectPendingAssociationId` is the exact cancellation/lease key:

```text
{ attention transaction_identity, accepted pending SourceInstance,
  PendingDescriptorKey, endpoint_local_generation }
```

It is carried in the direct-class candidate's new association sideband through
the existing producer/bridge/R2 path; non-direct candidates carry no live
association ID. This carrier is needed because `candidate_id`, request ID, and
endpoint coordinate alone are not globally unique across reuse.

The direct-class-only pre-issue gate therefore has two separate phases:
eligibility is a non-mutating descriptor-owner response; state commit occurs
only at the existing issue fire. `r2.core_mem_req.fire`,
`r1.core_mem_req_in.fire`, `external_core_mem_if_v1.request.fire`, and
`DirectPendingLeaseCommit.fire` are required to be the same cycle. The lease
owner checks the descriptor key, descriptor generation, accepted pending
instance, and current pending authority at that exact edge, then records one
lease through the matching typed direct terminal.

This is an explicit, limited **R2 semantic interface extension**: the direct
class gains a descriptor-owner proof at its existing issue fire. It does not
add a queue, change candidate ordering, alter the round-robin cursor rule, or
create a second arbiter. The cursor still advances only on the existing
`core_mem_req.fire`. Before a direct candidate has a grantable lease, R2 treats
it as not issue-eligible and may select another already-eligible class using
the frozen ordering rule.

There is no combinational handshake loop: registered R2 candidate fields drive
the eligibility query and later lease-commit `valid`; descriptor-owner
eligibility/commit readiness depends only on registered descriptor, authority,
and lease state, never on R2/R1/external readiness. R2 exposes
`core_mem_req.valid` from a registered candidate plus matching non-mutating
eligibility and commit-ready condition. The lease-commit `valid` is additionally
gated by the existing R1-ready/external-ready issue condition, so external
ready-low cannot commit a lease early. R1/external ready may hold the candidate
without mutating descriptor state or its eligibility response. A lease is
accepted once because R2 removes the candidate only at the joint fire while
the owner marks the exact association ID live at that same edge.

The resulting race rule is:

1. pending-to-packed before the joint fire: descriptor-owner eligibility and
   commit readiness are withdrawn; no R2/R1/external request fires. The
   association enters the cancellation/failure/abort path below.
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

If the descriptor owner's pending-to-packed authority-acceptance observation
and a matching lease-commit are both offered in one cycle, authority transition
has deterministic priority. The owner rejects the commit, R2 does not issue,
and the candidate follows cancellation. This conservative same-cycle rule
never creates a lease or an R1 request after the transition edge.

### Required directed proof points

The first implementation must demonstrate these exact observable boundaries:

| Case | Required observation |
| --- | --- |
| candidate before issue | `DirectPendingReadWork` and `direct_candidate_in.fire` occur while no lease state is live; `DirectPendingCandidateAccepted` names the stored association ID |
| external ready-low | the candidate and read-only eligibility may persist, but R2/R1/external request and `DirectPendingLeaseCommit.fire` are all low and no lease bit changes |
| ordinary joint issue | the four fire events (`r2.core_mem_req`, `r1.core_mem_req_in`, external request, lease commit) occur together exactly once for the association ID |
| permanent pre-issue failure | cancel fire/ack removes the exact stored slot; no subsequent request or cursor advance is possible for that ID |
| transition-versus-issue tie | a same-cycle pending-to-packed acceptance suppresses all four issue/commit fires, then follows cancel, endpoint abort, and R6 failure |
| post-issue transition | the existing request completes only through its typed R1 terminal and releases exactly its one lease; no cancel or endpoint abort occurs |

## Direct-class cancellation before issue

A stored direct candidate is not self-invalidating. Add the following exact
carriers:

```text
DirectPendingCandidateAccepted { DirectPendingAssociationId }
DirectPendingCandidateCancel    { DirectPendingAssociationId, reason }
DirectPendingCandidateCancelAck { DirectPendingAssociationId }
```

The materializer may send cancel only after candidate acceptance and before
the joint R2/R1 issue. R2 accepts cancel only if the exact direct-class slot is
still stored and has no issue commit. It removes that slot and returns the
acknowledgement; no slot, candidate-class credit, or outstanding-R1 identity
remains live. Candidate removal has priority over selection for the same
association ID in that cycle: R2 masks it from `core_mem_req.valid`, accepts
cancel, and does not advance the read cursor. This leaves all noncancelled
candidate ordering and the existing round-robin update rule unchanged.

Permanent association mismatch, descriptor invalidation, or pending-to-packed
before issue causes this order:

```text
descriptor-owner permanent failure
  -> R2 candidate cancel fire / cancel ack
  -> endpoint abort fire / abort ack
  -> R6 pending-source-failure fire
```

If failure occurs before candidate ingress, the cancellation pair is skipped;
the materializer aborts any opened endpoint before notifying R6. If reset
occurs, R2 clears stored candidates and the descriptor owner clears eligibility
and lease state; no cancel acknowledgement is required across reset. The
zero-buffer acceptance assertion, no-issue-after-cancel assertion, and
candidate-slot-count conservation are mandatory Chisel assertions.

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

## B2c bounded reconciliation implementation record

The approved first B2c sub-batch is deliberately narrower than the later
withdrawal/cancel/fault work.  It adds a read-only reconciliation journal to
the existing `RouteAM2P3Wrapper` and connects it to the production
`RouteAPendingDescriptorOwner`:

```text
accepted admission + immutable PendingPayloadReadBinding
  -> Valid-only AcceptedPendingPayloadBindingObservation
  -> fixed [0, 63] reset-only reconciliation journal
  -> PendingPackingReconciliationLookup / Result
  -> descriptor owner
```

The journal is not an authority owner.  A slot is written only on the existing
accepted three-way admission (`admission_context_in.fire` together with its
matched authority and binding), and its `transitioned_packed` bit may only be
set on the matching accepted existing R3-to-R6 pending-to-packed transition.
The observation is `Valid`, not a new ready/valid input: no lookup, descriptor
owner, or future withdrawal consumer can backpressure admission, publication,
or R6 authority acceptance.

Within the current `RouteAMeasurementDut`, `RouteAAdmissionPublicationIngressAdapter`
accepts one group containing at most 64 members and does not rearm before
reset.  The journal is therefore a fixed 64-entry, reset-only tombstone.  It
has an explicit `PopCount <= 64` structural assertion; it has no speculative
eviction, runtime-retire deletion, or unbounded/reusable-adapter claim.

An exact lookup compares all immutable binding provenance:
`{transaction_identity, entry_id, layer, kv_head, logical_position,
payload_ref, transaction_group_tag, group_member_ordinal,
group_valid_records, payload_handle_or_address, pending_storage_generation ==
source_generation, destination_endpoint}`.  It returns only:

| Result | Meaning |
| --- | --- |
| `unseen` | no exact accepted admission fact has yet been observed; this is not a permanent negative and an ordinary direct source remains eligible under its real pending-authority rule |
| `pending_member` | the exact immutable binding is an accepted packing member and no matching accepted transition has been observed |
| `transitioned_packed` | the exact member has an accepted pending-to-packed transition recorded |

The result channel is independently backpressurable and held stable, but it
does not feed any original admission/publication ready equation.  Both legal
orders are supported: registration before admission first observes `unseen`
and later captures the Valid-only exact admission observation; admission before
registration finds the retained immutable tombstone.  A same-cycle lookup and
admission resolves to `pending_member`.  A transition-after-registration late
lookup resolves to `transitioned_packed`; the subsequent B2c sub-batch must
turn that observation into the already-approved atomic withdrawal, R2
cancel/ack, endpoint abort/ack, and R6-owned fault path.

This new journal/query/control state is Route-A incremental measurement DUT
logic.  It must remain in the differential hardware BOM as an unestimated,
non-zero control cost; it is neither an array-only proxy nor an external-memory
service.

P0 verification on 2026-10-20 used the no-model Chisel commands
`testOnly kvpress.routea.rtl2.RouteAR3PackReadPathSpec` (6/6) and
`testOnly kvpress.routea.rtl2.RouteADirectPendingReadPathSpec
kvpress.routea.DualMeasurementDutStructuralSpec` (5/5 and 3/3).  The latter
also elaborates both measurement DUTs.  These are functional/provenance checks
only; they do not select a storage realization or provide synthesis, timing,
area, energy, HBM-controller, or PPA evidence.

The following B2c withdrawal sub-batch adds
`PendingToPackedReadEligibilityWithdrawal`.  It is a `Valid`-only fanout of
the exact immutable binding and is asserted only when the existing
`authority_transition_out.fire` has accepted the R3-to-R6 transition.  The
descriptor owner matches the complete binding before withdrawing its local
pending-read eligibility.  Consequently, a matching same-cycle R2 lease
commit/R1 request is suppressed, while an already issued lease remains outside
this gate and an unrelated binding is unaffected.  This sub-batch does not
backpressure the authority event or alter R2 ordering.  It intentionally does
not yet reclaim a pre-issue R2 slot or abort an opened endpoint; those are the
next approved cancel/ack and abort/ack sub-batches.

Withdrawal verification on 2026-10-20 used
`testOnly kvpress.routea.rtl2.RouteADirectPendingReadPathSpec` (7/7), followed
by `testOnly kvpress.routea.rtl2.RouteAR3PackReadPathSpec
kvpress.routea.DualMeasurementDutStructuralSpec` (6/6 and 3/3).  The latter
guards the production `authority_transition_out.fire` relation and both DUT
elaborations.  These remain functional control/provenance regressions only.

### B2c P2a cancellation/fault implementation record — 2026-10-21

The next bounded sub-batch connects the exact pre-issue failure sequence,
without changing R3 publication, R6 authority ownership, or R2's ordinary
ordering rule:

```text
accepted transition withdrawal for an exact declared association
  -> R2 direct-class candidate cancel / exact ack
  -> direct endpoint abort / exact ack
  -> typed association failure
  -> R6 lifecycle adapter emits the sole outward fault terminal
```

The R2 cancel carrier matches the complete `DirectPendingAssociationId` and is
accepted only for a live, unissued direct-class slot. Its accepted edge
suppresses ingress, R1 issue, and direct lease commit for that cycle. The
endpoint accepts abort only before delivery or source release and clears only
its local endpoint occupancy; it cannot emit a release, terminal, or success
packet. The materializer may report typed failure only after both exact acks.
The lifecycle adapter accepts it only for the exact pending instance of a live
R6-accepted plan and remains the sole owner of the outward fault terminal.

The local directed witness
`RouteAMeasurementDutR3Spec` passed 4/4 on 2026-10-21. Its new case holds the
real external R1 request unaccepted, allows the actual R3/R6 transition to be
accepted, observes no issue after cancellation, then observes the matching
R6-owned fault terminal. This is limited single-record functional control
evidence. It does not close the final B2c non-regression/structural gate,
multi-record coverage, physical memory, timing, PPA, or synthesis claims.

## Final minimum RTL scope if approved

Approval of this revised contract authorizes only the following MR-1B work:

- `RouteAInterfaces.scala`: association declaration, endpoint open/ack,
  descriptor registration/key, direct candidate association/accept/cancel
  sideband, split lease eligibility/commit, issue/abort/ack, and typed
  association-failure carriers;
- `RouteAIncrementalSkeletons.scala`: paired binder retention, endpoint
  accepted-instance/local-generation relation, descriptor-owner registration
  and lookup boundary, R2 direct-class candidate cancellation plus pre-issue
  eligibility/commit gate, association materializer, endpoint abort, and
  lifecycle failure input;
- `RouteAMeasurementDut.scala`: production descriptor-owner boundary plus the
  owner-to-owner direct producer, delivery, terminal, release, and failure
  connections, with no test-only provider or tie-off;
- directed tests for exact success; descriptor/instance/storage-generation
  mismatch; missing pre-acceptance counterpart; endpoint reuse; stale/reset;
  duplicate; plan/open/lease/R2/R1 backpressure; R1 fault/malformed response;
  candidate-before-lease causality; cancel-before-issue; no-issue-after-cancel;
  no-abort-after-issue; external-ready-low with no lease state; and both sides
  of pending-to-packed including the same-cycle priority around the joint
  R2/R1 lease fire; plus W0/MR-1A non-regression and structural guards.

The approved scope is **single-record MR-1B only**: `valid_count = 1` and one
immutable `source_last` descriptor fact. A passing MR-1B implementation is not
evidence of multi-record direct-pending coverage; any such extension requires
a separately reviewed multi-record association, lease, terminal, and test
contract.

The direct-pending source must still be an explicit functional-memory boundary;
this proposal does not add an HBM controller, memory macro, attention PE,
numeric implementation, timing, throughput, PPA, or physical-memory claim.
