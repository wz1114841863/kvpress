# MR-2 M2 entry-update declaration contract proposal

**Status:** production-data semantic closure is **blocked pending four explicit
researcher decisions**. This is a narrow interface proposal, not an RTL
authorization, entry-layout selection, macro decision, or PPA result.

The final four-decision approval package is
`analysis/mr2_m2_four_design_decision_proposal.md`. It makes explicit that the
frozen A4 two-source lifecycle facts are absent from the current non-contiguous
R3 packed-group carriers; a group provenance journal must not be relabelled as
M2 lifecycle storage.

## Scope and outcome

`9c7541a` supplies a bounded production owner for the existing M2 group
control: exact two-member identity, head-bank selection, paired head-control
provenance, private completion, and publication eligibility. It does not hold
M2 entry words. This review determines whether its existing upstream facts can
lawfully drive a real M2 read-modify-write (RMW) array.

They cannot. The frozen A4 material identifies the semantic *classes* which
would have to be represented, but deliberately stops at a trace-derived
accounting model. No current production carrier names a logical entry,
provides a valid-state transition, supplies an RMW operand, or owns the
meaning of a resulting word. Therefore no M2 storage RTL or array-only split
is authorized by this proposal.

## Frozen facts versus unselected realization data

| Object | Frozen semantic-accounting facts | Required for a real entry, but not frozen or carried today |
| --- | --- | --- |
| `head_control` | Per-head modeled object; two logical `frontier_control` records and one `selection_control` record. With the joint-safe model widths, each frontier record is `valid(1)+source(1)+span_slot(6)+birth(6)+sequence(11)=25` bits and selection is `valid(1)+source(1)+selection_epoch(7)=9` bits: `2*25+9=59` raw bits, with a **candidate accounting** padding to 64 bits. The two replicas must update atomically. | Actual word encoding/bit ordering; whether this is one or several implementation entries; a real `(layer, kv_head)` key plus any live namespace/generation; the valid-state meaning; and the RMW transform/operand. |
| `span_owner` | The modeled co-located object comprises a `span_descriptor` (`valid(1)+source(1)+birth(6)+sequence(11)+remaining_count(11)+span_slot(6)=36` bits) and an `ownership_link` (`valid(1)+source(1)+2*span_slot(6)=14` bits): `50` raw bits, with **candidate accounting** padding to 64 bits. | Actual span key and lifecycle/reuse generation; word encoding/bit ordering; valid/release meaning; and create, remaining-count, unlink, and release operands/transforms. |

The 59/50 and padded 64/64 numbers are a useful upper-bound candidate for a
later chosen word representation, but are not an existing physical entry
definition. In particular, the joint-safe accounting records
`span_generation_bits=0` and has no payload address/handle field. It cannot
make `m2_group_opaque_address_ref`, a member ID, or a fixture value into an
entry key or data word.

The frozen semantic replay observes `admission_create` (span create plus
ownership link), non-terminal dequeue (frontier/selection and remaining-count
updates), and terminal dequeue (release plus unlink and frontier update). It
explicitly states that these are semantic transaction boundaries, not a
hardware operation or cycle. The present R3 pair
`head_control_rmw`/`span_owner_rmw` preserves the required all-or-fault
publication prerequisite; it does **not** specify which of those semantic
updates it represents or supply their data.

## Production-owner audit

| Needed declaration fact | Existing source and accepted event | Result |
| --- | --- | --- |
| Immutable group identity | R3/P3 accepted group carries `(layer, kv_head, stage_generation, transaction_group_tag, member)` into `M2GroupMemberRequest.fire`. | Present; it binds a declaration to one existing M2 member. |
| Logical bank selection | Accepted `kv_head` selects the frozen head-affine logical bank. | Present; it is not an entry key or physical-bank decision. |
| Logical mapping provenance | Pending-payload/location owner emits immutable `m2_group_opaque_address_ref` and `m2_group_owner` at `pending_payload_read_binding_in.fire`; admission checks agreement and R3 stages them. | Present only as opaque mapping provenance. Neither field owns metadata contents or an RMW decision. |
| Queue/credit eligibility | Existing metadata local/shared/staging owners may delay the accepted group. | Present only as capacity eligibility; it does not create entry content. |
| Semantic record key, valid transition, operation, operand, old/new value, mask, or storage-fault origin | No production carrier or accepted event. A4 recordization/replay is a frozen analysis input, not a Chisel production owner. | **Absent.** R3, `RouteAM2ProductionControlOwner`, the pending-payload/location owner, R2/R1, and test fixtures are all prohibited from synthesizing it. |

Thus the only possible single producer is a newly named **M2 metadata semantic
update-decision owner**, after a researcher selects the four decisions below.
It is a data-decision producer only: it must not choose admission, authority,
publication, source selection, or R2 arbitration. No existing owner can be
renamed as that producer without supplying the missing facts.

## The one proposed typed carrier

After those decisions are approved, add exactly one decoupled carrier,
`M2EntryUpdateDeclaration`, from that decision owner to the M2 storage/wrapper
owner. It must be independently accepted before the matching
`M2GroupMemberRequest` may be accepted; R3 continues to issue the pre-existing
two members and consumes only their typed status responses.

| Field | Legal producer / creation event | Consumer and use |
| --- | --- | --- |
| `layer`, `kv_head`, `stage_generation`, `transaction_group_tag`, `member` | The update-decision owner copies the already accepted immutable group identity; declaration `fire` must match exactly one subsequent member request. | Storage wrapper exact association; R3 does not reinterpret it. |
| `object` | Derived from the fixed member (`head_control_rmw` or `span_owner_rmw`) and asserted equal, never independently selected. | Selects one frozen logical object class. |
| `entry_key` | New decision owner, from the selected semantic namespace rule; it is not `opaque_address_ref`. | Storage lookup/RMW target. |
| `expected_old_valid` | New decision owner, from the selected operation's semantic precondition. | Storage checks stale/create/release misuse before mutation. |
| `update_kind` | New decision owner, from a selected finite mapping of semantic create/dequeue/release behavior. | Selects the storage-local canonical RMW transform. |
| `update_operand` | New decision owner, from the corresponding accepted metadata lifecycle fact. | Storage reads the old entry and combines it with `update_kind`; it is not a complete next word. |
| `operand_mask` | New decision owner, from the selected entry encoding and operation. | Limits storage mutation; it must not be invented from the group tag or fixture. |
| `declaration_owner` | The decision owner's immutable identifier. | Exact provenance comparison and fault reporting only; it is not R3/R6 authority. |

The key, operand, mask, and `update_kind` encodings deliberately have no
Chisel width yet: assigning 64-bit words, a span-generation field, or an enum
now would silently make the unapproved realization choice. Once the four
decisions are selected, their widths must be fixed in the same contract; the
existing 64-bit accounting candidates may be selected then, but are not an
implicit default.

## Required storage behavior after authorization

1. The storage wrapper accepts the declaration and its matching member only
   with exact identity and provenance. It reads the true old entry, checks
   `expected_old_valid`, executes the selected canonical transform, and commits
   the resulting word. No upstream producer may provide a full new word unless
   it is separately proved to own the old state and transform.
2. A `head_control` successful member commits the two replicas together before
   the one `ok` response. Either both words change or a typed fault is
   returned; no replica-visible partial state is allowed. `span_owner` is an
   independent keyed RMW.
3. Private member completion remains an exact-status prerequisite of the
   existing production-control candidate. A declaration/key/old-valid/commit
   failure returns the matching member `fault`, leaves the group
   non-publishable, and cannot return a publication success. Reset clears
   declaration association and wrapper state using the existing R3 reset/init
   discipline.
4. Backpressure before declaration or member acceptance mutates nothing. The
   carrier creates no scheduler, authority owner, publication point, or second
   source of queue credit.

## Four minimal researcher decisions still required

1. **Entry encoding and validity:** select the exact bit encoding and valid
   meaning for each object. This may select the frozen 64-bit accounting
   candidate, but must not call it previously frozen hardware.
2. **Key and reuse rule:** select the full head and span keys, including any
   span namespace/generation and the event which permits reuse. The current
   accounting's zero generation bits are insufficient as a runtime stale-key
   rule.
3. **Lifecycle lowering and unique producer:** map each accepted metadata
   lifecycle fact to one `update_kind` and operand, and name the one
   production update-decision owner and its declaration `fire`. The mapping
   must cover create, non-terminal update, and terminal release/unlink or
   explicitly limit the first RTL scope.
4. **Typed storage fault contract:** select the storage-fault producer and
   fault status encoding so R3's existing fail-closed member response can
   distinguish a failed mutation from `ok` without a fabricated response.

These are the minimum semantic choices, not permission to add a scheduler,
new authority, memory macro, timing parameter, or physical address scheme.

## Conditional implementation and directed regression

Only after the four decisions are approved, the minimal RTL touch set is:

- `RouteAInterfaces.scala`: one declaration/key/operand bundle and channels;
- `RouteAM2P3Wrapper` plus the named decision owner: exact declaration/member
  association, no data inference;
- `RouteAM2ProductionControlOwner` (or a contained M2 storage child): real
  keyed storage, atomic dual-replica commit, typed fault response, and reset
  clearing; and
- `RouteAM2ProductionControlOwnerSpec` plus composed measurement-DUT tests.

The tests must cover normal create/update/release, wrong group/key/owner,
old-valid mismatch, mask/operand rejection, one-replica fault atomicity,
independent span access, backpressure, reset/stale reuse, member fault blocking
publication, and the existing W0/MR-1A/MR-1B plus M2/R3 and dual-DUT structural
non-regressions. No Chisel test is run for this proposal because it changes no
executable RTL.

## Cost and evidence boundary

The declaration producer, association registers, key/valid/operand checks,
RMW peripheral logic, dual-replica atomic commit, storage error path, and
entry-array interior are Route-A incremental costs. They remain
`unestimated_not_zero`; the A4 accounting proxy cannot zero them or substitute
for a selected wrapper. A future array-only boundary may exclude only the
selected entry/data-array interior, never these controls or R3 publication
responsibility.

## Evidence consulted

- `analysis/architecture_spec.md`, §8 and
  `analysis/architecture_gate_a_r3_m2_p3_wrapper_contract.md`: frozen M2
  interface and all-or-fault group rule.
- `analysis/route_a4120_metadata_interface_inventory_contract.md` and frozen
  A4.9.1 report: semantic accounting widths and their explicit non-physical
  boundary.
- `tools/analyze_kvzap_route_a471_metadata_transaction_contract.py` and
  `tools/analyze_kvzap_route_a4720_metadata_storage_sufficiency.py`: semantic
  record classes and trace-derived transaction grouping only.
- Current `PendingPayloadReadBinding`, `M2GroupMemberRequest`,
  `RouteAM2P3Wrapper`, and `RouteAM2ProductionControlOwner` sources.
