# MR-2 M2 storage unit and production-facts audit

**Status:** storage-unit directed verification is in progress; production
lifecycle integration is blocked on the facts recorded below.  The runtime
scope decision is recorded in
`mr2_m2_runtime_semantics_implementation_decision.md`: Package A remains a
bounded storage-unit candidate, while A4's detailed source-FIFO lifecycle is
not thereby promoted to a production owner.  This is a narrow follow-up to the
approved Package A decision and not a new architecture/MBR/SRP phase.

## Scope separation

`RouteAM2EntryStorage` accepts only the typed
`M2EntryUpdateDeclaration` carrier.  In this sub-batch that carrier is driven
solely by the dedicated storage-unit directed test.  It is not instantiated in
`RouteAMeasurementDut`, has no top-level ingress, and cannot cause an R3 member
response, publication candidate, R6 transition, R2 request, or terminal.  Its
test result consequently establishes only **storage RTL unit behavior**.

The unit's bounded anchor state is:

| State | Actual state and key | Reset/reuse rule | Cost status |
|---|---|---|---|
| `head_control` | Two mirrored 128-bit entries for each direct `(layer[5:0], kv_head[2:0])` key, 36 x 8 keys.  Each word holds two source FIFO head/tail handles and selection state. | Reset invalidates all entries; each accepted guarded head operation writes both replicas in one clock edge. | Route-A incremental, `unestimated_not_zero`. |
| `span_owner` | 614 independently addressed 128-bit entries.  A live identity is array `slot[9:0]` plus stored `generation[7:0]`; the word holds source, layer/head, birth, sequence, remaining count, and links. | Only a zero-remaining `release_span` frees a slot.  It increments generation; `255` faults rather than wraps.  Reset invalidates all slots and resets next generation. | Route-A incremental, `unestimated_not_zero`. |
| allocator/RMW/result state | First-free selection, generation vector, declaration/result skid state, comparison/fault logic, and replica guard. | A request is one operation only on `declaration_in.fire`; result backpressure prevents a second acceptance. | Route-A incremental, `unestimated_not_zero`; never array-only. |

The entry interiors are 128 bits each.  The A4 59/50-bit values remain only
historical accounting baselines; no storage result converts either figure into
a macro, CACTI, DC, timing, area, energy, or PPA claim.

The implementation fixes the otherwise unspecified bit allocation as follows:

| Entry | Fields | Bits |
|---|---|---:|
| `head_control` | `valid`; four `{valid,slot,generation}` handles; selection valid/source/epoch; zero reserve | `1 + 4×19 + 18 + 33 = 128` |
| `span_owner` | `valid`, source, generation, layer/head, birth/sequence/remaining, previous/next handles, zero reserve | `1 + 1 + 8 + 6 + 3 + 3×16 + 2×19 + 23 = 128` |

For `span_owner`, `slot` is the bounded array address and carrier handle field,
not a duplicate entry field; `{slot,generation}` remains its full stale-safe
identity.  This implementation packing is an approved bounded anchor-DUT
choice, not an assertion about a future physical memory layout.

## A. Production lifecycle-event fact audit

The only current production event carrying M2-adjacent information is the
three-way retained-member join in
`RouteAAdmissionPublicationIngressAdapter`, later mirrored by R3.  Its
accepted facts are `(entry_id, layer, kv_head, logical_position, payload_ref,
stage/tag/member ordinal)` plus the pending-location owner's opaque mapping
reference/owner.  The R3 contract explicitly permits non-contiguous retained
members.  None is a source class, birth opportunity, FIFO sequence, count,
semantic span handle, or source-service event.

| Semantic operation | Required accepted event and facts | Current unique production owner/event | Conclusion |
|---|---|---|---|
| `append_span` | source, birth, sequence, positive initial count, and the exact head key; a group association only when it truly participates in R3 packing. | No owner/event exists.  `r6_admission_context_in.fire` plus `pending_payload_binding_in.fire` has group and opaque mapping provenance only. | **Absent.** It cannot be inferred from member ordinal, first logical position, tag, payload reference, or opaque mapping reference. |
| `select_oldest` | accepted source-service choice over live source FIFO state, exact selected handle/source. | No source-service selection carrier or owner exists in the production Chisel tree. | **Absent.** `SourceCompletionPlan` is not M2 FIFO selection state. |
| `dequeue_span` | accepted source-service consumption with exact handle and positive amount. | No production dequeue carrier or owner exists. | **Absent.** A direct/packed read terminal is not a semantic FIFO dequeue declaration. |
| `release_span` | accepted terminal source-service release after the corresponding remaining count reaches zero. | No production release carrier or owner exists. | **Absent.** R5/R6 reclaim cannot be reinterpreted as M2 source-span release. |

The frozen A4 replay does define these operations for analysis, using
`(source, birth_opportunity, sequence_start, count)`.  It is a trace-derived
model and must not be renamed as a Chisel production owner.

### Minimum missing production boundary

Production integration requires a separately approved metadata boundary.  The
current selected branch first requires only an explicit admission-derived
append fact; it does not authorize a source-FIFO/sequence/source-selection
subsystem.  If a later runtime service contract genuinely requires the four
semantic operations, its local source-FIFO/sequence/count state, declaration
queueing, and fail-closed status path must be separately approved and costed.
Neither branch may choose KVzap admission, create R6 authority, issue R2 work,
or replace R3's publication owner.  A fixture or empty top ingress cannot
supply this missing owner.

## B. Semantic-operation to current R3-member audit

The existing `head_control_rmw` and `span_owner_rmw` requests are an exact
two-member, all-or-fault prerequisite for a *packed publication group*.  They
are emitted only after the existing P3 payload/descriptor prerequisites and
provide no semantic operand.

| Semantic operation | Potential objects touched | Valid mapping to current R3 pair? | Reason |
|---|---|---|---|
| `append_span` | head-control FIFO endpoint plus span-owner allocation/link | Conditional only after a real append declaration exists.  It can lower to the two existing members exactly once for a true packed-group association. | Current group facts do not prove a contiguous source span or provide its operands. |
| `select_oldest` | head-control selection state | No current grouped-member mapping. | It is an ungrouped source-service action; forcing it into the publication pair would fabricate a span-owner commit and publication prerequisite. |
| `dequeue_span` | span remaining count; may change head selection at a defined semantic boundary | No current one-to-one mapping. | The current pair does not name the count/old value or say whether the head word changes. |
| `release_span` | span unlink/free and affected head endpoint | No current one-to-one mapping. | A terminal source release is not presently associated with R3 publication and must not be synthesized from a non-contiguous group. |

Thus the storage unit can verify its own RMW transforms, but it cannot be
connected to `RouteAM2ProductionControlOwner` as a production completion until
the producer gives each grouped/ungrouped declaration an exact accepted-fire
relationship.  For a grouped append, the lowerer must retain the declaration
until both exact member completions commit; a fault or response backpressure
must preserve the existing all-or-fault publication gate.  This audit does not
change that gate.

## C. Unified carrier schema and fire rule

Package A and the earlier declaration proposal are merged in the one existing
typed `M2EntryUpdateDeclaration` bundle.  There is no second entry/update
bundle in the RTL.

| Field class | Fields | Producer rule / storage use |
|---|---|---|
| Operation identity | `operation_id`, `update_kind`, `expected_old_valid`, `operand_mask` | A future lifecycle producer assigns exactly one canonical transform.  Storage accepts it only on `declaration_in.fire` and reads its own old state. |
| Semantic entry identity/operand | `layer`, `kv_head`, `source`, `birth_opportunity`, `sequence_start`, `initial_or_dequeue_count`, `span_slot`, `span_generation` | The producer must carry actual semantic facts; storage never derives them from group/member or fixture data. |
| Group association | `grouped`, `member`, `stage_generation`, `transaction_group_tag`, `opaque_mapping_ref`, `mapping_owner` | Meaningful only for a proven packed-group operation.  When `grouped=0`, all association fields are required zero; they are association-only, never an entry key/address. |

`M2EntryUpdateResult` returns the exact operation identity, copied association,
status `{ok,fault}`, private reason, and the resulting/checked span handle.
Exactly-once here means one mutation for one accepted declaration fire; it does
not yet prove a production producer will not replay an operation.  That replay
and source-lifecycle responsibility remains with the missing producer.

## Current conclusion and next permitted boundary

1. **Storage RTL unit:** independently implementable and currently under
   directed regression.
2. **Production lifecycle connection:** **BLOCKED** by the four absent
   accepted lifecycle events above.  No Route-A top integration is authorized
   from this audit alone.
3. **M2 array-only boundary:** not yet complete.  Only after a real production
   wrapper exists may the entry-array interiors be separated; allocator,
   generation, RMW, replica, association, and publication control remain in
   synthesizable Route-A control RTL.

This preserves the frozen non-contiguous admission contract, R3's atomic
publication, R6's sole authority, and R2 scheduling while making the missing
production boundary explicit.
