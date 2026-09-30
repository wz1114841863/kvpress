# RTL1-I2 — Admission / publication association contract

**Status:** `rtl1_i2_admission_publication_behavior_complete; later delivery/source/reclaim integration_pending`.

RTL1-I2 closes only the cross-owner control association from a previously
accepted `RETAIN` maturity to R3's bounded record membership, and the
post-`metadata_publish_commit` observation path.  It does not select an
admission policy, page packing policy, physical P3/M2 storage, HBM transport,
controller schedule, numeric datapath, source service, or reclaim mechanism.

## Immutable admission context

`AdmissionContext` is an internally clocked ready/valid carrier with these
fields:

| Field | Meaning | Source / owner |
|---|---|---|
| `entry_id`, `layer`, `kv_head`, `logical_position` | Exact retained record coordinate; the canonical coordinate equation must hold. | Hot/admission lifecycle owner |
| `payload_ref` | Opaque association to the already-existing pending payload backing. | Hot/admission lifecycle owner |
| `transaction_group_tag` | Opaque finite publication-group identity.  Its width remains a parameter. | Admission owner |
| `group_member_ordinal`, `group_valid_records` | Explicit member identity and population in `1..64`; positions need not be contiguous. | Admission owner |

R3 may accept a context only for a matching live P3 group.  It validates the
coordinate, group tag, population and ordinal, rejects duplicate ordinals, and
records each member explicitly.  It must not infer members using a
`first_entry + count` span.  `payload_ref` is association-only: recording it
does not move payload, create a P3 data copy, or create another authoritative
residency.

The group identity and membership values are supplied after the already frozen
DROP/RETAIN decision.  RTL1-I2 therefore does not revisit pruning, admission,
page size, scheduling, or page mapping.  A later source may choose how a
frozen group is formed, but must supply this exact immutable contract.

## Publication observations

The sole atomic visibility and authority handoff remains the existing
`metadata_publish_commit` / nested R3--R5 acknowledgement.  On a successful
existing publish acknowledgement, R3 produces exactly:

1. one `PublicationCommitObservation`; then
2. one `PublicationMemberObservation` and one matching pending-to-packed
   `R6AuthorityTransition` for each explicit member ordinal.

Ready-low may delay either observation carrier, but cannot cause a second
metadata publication, omit a member, duplicate a member, release the group
for reuse early, or alter the original commit instant.  A failed publication
emits neither successful observation nor pending-to-packed handoff.

The membership ledger is logical, bounded to the frozen 64-record page
population, and is not an SRAM macro, a P3 payload store, or an authority
table.  R6 continues to consume event-level handoffs only; it does not become
a long-lived token residency owner.

## I2 evidence and limits

The required ChiselSim tests cover a retained non-contiguous group, duplicate
member rejection, fault/non-publication, and an atomic-visibility sequence.
They are directed functional protocol evidence only.  They make no RTL
correctness proof, timing, throughput, PPA, model/GPU, HBM, or new A4 DSE
claim.  The following later work remains explicitly out of scope: R2/R1
delivery, P3 payload fragments, R4/source completion, R5 invalidation/reuse,
and physical queue/macro realization.

## Implemented RTL1-I2 closure

`RouteALifecycleAdapter` stages the immutable context together with the same
RETAIN maturity's `hot -> pending` event; it holds both under ready-low and
does not clear the lifecycle event until hot control, authority handoff, and
context have all been accepted.  The three group fields enter through the
existing frontend tagged union only for an accepted RETAIN maturity.  They are
opaque, upstream-frozen group association values, not an R6 policy decision.

`RouteAM2P3Wrapper` joins those two R6 facts atomically, validates the exact
coordinate and matching live P3 claim, records explicit ordinals in its
bounded logical ledger, and adds membership completion to the pre-existing
publication prerequisites.  A successful existing publication acknowledgement
first creates one group observation, then emits one record observation and one
matching R6 `pending -> packed` event per ordinal.  A failed P3/publication
path produces no successful observation.  The production top wires the
R6--R3--R6 carriers but still has no P3-claim/payload publisher; the directed
R3/R5 harness supplies those later-owner inputs solely to test the frozen
association.
