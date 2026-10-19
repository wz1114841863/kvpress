# MR-1B — Direct-pending cross-owner association contract proposal

**Status:** `proposed_waiting_user_approval`; no RTL change is authorized by
this document.

## Narrow purpose

This proposal closes only the missing association needed to form one existing
`DirectPendingReadWork` from an **R6-accepted** pending `SourceInstance` and
an already-recorded pending-payload binding. It neither selects a source,
creates an authority owner, changes an R6 source set, changes admission or
publication, nor changes the direct endpoint's eight-fragment functional
transaction.

The current fields are insufficient for an adapter alone:

```text
R6 accepted { attention identity, pending SourceInstance }
    X no immutable key to an R3 binding-ledger member
R3 binding { admission member key, handle, source generation, destination }
    X no attention/source-instance or direct-sequence association
direct endpoint { locally allocated generation, ordinal progress }
    X no relation to the accepted-plan generation
```

`SourceInstance` is explicitly not a payload reference or address, and
`source_last` is an independent immutable descriptor fact. The adapter must
not reconstruct either fact from a position, group count, response `last`, or
private endpoint state.

## Proposed minimum carrier and ownership

Add one immutable ready/valid **declaration-side** carrier,
`PendingDirectAssociationDeclaration`, paired with the existing
`SourcePlanDeclaration` before the source-plan binder. It is required iff the
plan's pending-presence bit is set; a plan without pending has no such carrier.
The existing upstream source-plan declaration owner is its sole producer. The
carrier describes an already selected association only: it cannot select a
source, initiate a read, grant authority, or allocate an endpoint.

| Field | Legal sole source | Consumer / exact validation | Forbidden derivation |
| --- | --- | --- | --- |
| `transaction_identity` | source-plan declaration owner | paired declaration and R6 accepted-plan copy | entry ID or payload reference |
| `pending_instance` | source-plan declaration owner | equality with paired plan pending instance | a later endpoint observation |
| R3 member key: entry/layer/head/position/payload-ref/group tag/member ordinal/group count | existing pending binding and admission coordinates | R3 immutable-ledger lookup | source-instance coordinate or a contiguous span |
| `pending_ordinal` | pending payload/source descriptor owner | direct terminal sequence | logical position without an explicit equality contract |
| `source_last` | pending payload/source descriptor owner | direct source close | eighth-fragment `last`, group count, or absent next member |
| `valid_count` | frozen C3 single-record rule | direct producer | R3 `group_valid_records`; first implementation fixes `1` only for a one-record declaration |
| handle/address, payload source generation, destination | pending-payload storage owner; already captured in R3 binding | exact R3 lookup response | payload ref, P3 generation, or R1 response |

The declaration carrier remains separate from `SourceCompletionPlan`; the plan
schema and R6 source-selection fields are unchanged. The existing binder only
retains and forwards the pair exactly. It does not validate residency, choose
among bindings, or inspect payload data.

## Unavoidable interface changes

1. **Binder pair:** `RouteASourcePlanBinder` needs paired association ingress
   and exact association-copy egress. It accepts neither half alone, holds the
   pair immutable under R6 backpressure, and exposes the copy only after the
   existing R6 plan-acceptance handshake.
2. **R3 read-only lookup:** `RouteAM2P3Wrapper` needs a request/response keyed
   by the full member key. It returns a recorded `PendingPayloadReadBinding`
   only on an exact live-ledger match; it neither creates a binding nor exposes
   payload bytes. Missing, duplicate, or mismatched keys are ready-low.
3. **Exact-instance endpoint open:** endpoint-open must carry the accepted
   `SourceInstance`; `RouteADirectPendingEndpointV1` must latch it rather than
   allocate an unrelated new generation. This removes the current plan/open
   generation cycle.
4. **One association materializer:** a small Route-A adapter joins accepted
   plan copy, paired declaration, and R3 lookup response. It emits one open
   and one work item only after exact equality. It is not a selector,
   authority table, scheduler, or second R6 owner.

The materializer may allocate candidate ordinal/ID as a local work-association
sequence, as the existing R3 pack-read materializer does. R2 retains all
eligibility interpretation and arbitration.

## Required lifetime decision before RTL

The current contracts do not say what preserves a pending payload after an
accepted direct R2/R1 request while the same member is packed and R6 accepts
pending-to-packed authority. This is a contract decision, not adapter detail.

Exactly one must be approved:

1. accepted direct work has an immutable pending-read lease through its direct
   terminal/source release; or
2. the pending-payload owner guarantees an accepted immutable binding remains
   response-valid through that terminal despite later packed authority.

The lease option must not delay, split, or add a second atomic publication. The
persistence option must not turn R3, the adapter, or R6 into a payload owner.
Until one is selected, direct work cannot safely coexist with packing or cross
the pending-to-packed handoff.

## Required fail-closed behavior

- Paired declaration, R6 accepted plan, R3 lookup, and endpoint instance all
  match exactly; otherwise neither open nor work fires.
- Reset clears binder pair, materializer state, and endpoint state. Old
  declaration, response, terminal, or release fails by identity and instance.
- The materializer holds an immutable joined record under backpressure and
  admits it once; duplicate pair/plan/lookup/work cannot issue another read.
- Direct and pack-read may observe the same immutable binding only under the
  approved lifetime rule. Neither consumes the other's membership fact or
  creates authority.
- Direct fault creates neither deliverability, consumer commit, release, nor a
  substitute packed source.

## Conditional RTL scope after approval

Only after approving the lifetime rule and the four changes above:

- `RouteAInterfaces.scala`: paired declaration, R3 lookup carrier, and
  exact-instance endpoint-open field;
- `RouteAIncrementalSkeletons.scala`: binder pair retention, R3 lookup,
  endpoint exact-instance latch, and association materializer;
- `RouteAMeasurementDut.scala`: existing direct producer, delivery ingress,
  endpoint, terminal, and release carriers through the materializer, with no
  test-only ingress or tie-off;
- focused MR-1B Chisel tests plus measurement structural and W0/MR-1A
  non-regressions.

The directed matrix is: one exact positive record; each key/instance mismatch;
stale/reset; duplicate pair/work; backpressure at plan/lookup/open/work; R1
fault/malformed response; and direct plus pack-read at the approved lifetime
boundary.

No controller, macro, numeric source-partial implementation, timing,
throughput, PPA, or physical-memory claim follows from this proposal.
