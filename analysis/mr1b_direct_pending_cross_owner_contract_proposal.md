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

## Selected lease rule and authority-transition race

The selected rule is an **accepted direct-read lease**, owned by the
pending-payload descriptor/location owner. It is not a new residency authority
and does not delay or split the existing pending-to-packed atomic publication.

The exact rule is:

1. The materializer presents the R2 candidate and a matching lease-acquire
   request as one atomic owner-to-owner acceptance. The lease is created only
   when R2 accepts that exact candidate; before then there is no live direct
   lease or irrevocably accepted direct work.
2. Lease acquisition proves the payload was pending-authoritative at the R2
   acceptance edge and pins exactly that immutable handle/storage generation
   through the matching direct record terminal (success or fault). It neither
   creates a second authority nor grants a later retry.
3. If pending-to-packed happens after the atomic R2/lease acceptance, the
   accepted R1 request may finish using the lease. The transition remains the
   sole authority handoff; the lease is only a response-validity pin.
4. If the transition occurs before R2/lease acceptance, acquisition fails
   closed: no R2 candidate may fire and the accepted plan enters the typed
   association-failure path below. The materializer may not reinterpret the
   pending plan as packed or issue a new read after the transition.
5. The pending-payload owner releases the lease exactly when the matching
   typed direct terminal is accepted. Later four-consumer source release is a
   separate R6/source-service lifecycle event and is not a reason to retain
   a memory-read lease.

This needs a minimal lease-acquire/lease-release carrier between the direct
producer path and the descriptor owner. The producer gates candidate validity
on the owner's simultaneous lease acceptance, so R2's existing
`PendingAuthoritative` predicate still denotes a true authority proof at its
candidate-acceptance edge rather than an inferred sticky bit.

## Temporary backpressure versus permanent failure

`ready-low` is permitted only while a pair is incomplete, the direct endpoint
is occupied, or a lawful lease response is temporarily backpressured. It may
not be the response to a known missing/mismatched descriptor after R6 accepts
the plan.

Add `DirectPendingAssociationFailure { transaction_identity, pending_instance,
reason }`. The binder/materializer emits it exactly once when an R6-accepted
pair cannot open, cannot obtain a lease because authority has transitioned, or
finds an immutable identity/generation/descriptor mismatch. The lifecycle
adapter accepts it only for its matching live pending source plan and produces
the existing one outward fault terminal without a source release, GQA commit,
merge/R4 success, or retire acknowledgement. It clears the matching attention
tracker only when that fault terminal is accepted. This is fail-closed and
bounded; it is neither retry/fallback nor a new authority transition.

Reset clears paired binder state, association materializer state, endpoint
state, and live leases. A stale declaration, lease response/release, terminal,
or failure must match both transaction identity and its relevant accepted
instance/generation; otherwise it is rejected without a deliverability,
success terminal, release, or retire effect.

## Final minimum RTL scope if approved

Approval of this revised contract authorizes only the following MR-1B work:

- `RouteAInterfaces.scala`: association declaration, endpoint open/ack,
  direct lease, and typed association-failure carriers;
- `RouteAIncrementalSkeletons.scala`: paired binder retention, endpoint
  accepted-instance/local-generation relation, lease-gated association
  materializer, and lifecycle failure input;
- `RouteAMeasurementDut.scala`: production descriptor-owner boundary plus the
  owner-to-owner direct producer, delivery, terminal, release, and failure
  connections, with no test-only provider or tie-off;
- directed tests for exact success; descriptor/instance/storage-generation
  mismatch; missing counterpart; endpoint reuse; stale/reset; duplicate;
  plan/open/lease/R2 backpressure; R1 fault/malformed response; and both sides
  of pending-to-packed around R2 acceptance; plus W0/MR-1A non-regression and
  structural guards.

The direct-pending source must still be an explicit functional-memory boundary;
this proposal does not add an HBM controller, memory macro, attention PE,
numeric implementation, timing, throughput, PPA, or physical-memory claim.
