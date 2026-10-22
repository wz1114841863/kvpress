# MR-2 M2 four design-decision proposal

**Status:** Package-A storage-encoding proposal and historical input only.  Its
recommended full lifecycle-lowering branch is superseded for production scope
by `mr2_m2_runtime_semantics_implementation_decision.md`: A4's detailed
private/shared birth-ordered lifecycle remains replay/accounting evidence until
a real runtime service-event source is separately selected.  This file does
not authorize Chisel, macro, DC/CACTI, or PPA work.

## Evidence boundary and recommendation

The frozen A4 metadata replay has `private` and `shared` source FIFOs and
semantic `(source, birth_opportunity, sequence_start, count)` spans.  It
creates, selects, dequeues, and releases those spans.  The current Chisel
retained group is explicitly non-contiguous and has only record position,
payload/group identity, and opaque mapping facts; it has no source class,
birth/sequence/count, dequeue, or release carrier.  Consequently a group tag,
member ordinal, first position, opaque reference, or fixture cannot be treated
as a semantic span key or operand.

The recommended approval package explicitly adds the missing metadata-lifecycle
source to produce `M2EntryUpdateDeclaration`.  It preserves R3's two existing
M2 members and its sole publication point, R6 authority, admission, P3 mapping,
and R2 order.  The smaller alternative of only recording current R3 group
provenance is implementable today, but is a journal, not full M2 storage, and
is rejected as MR-2 closure.

## 1. Entry encoding / valid semantics

**Preferred: select two 128-bit actual entry encodings.**  This is intentionally
not the frozen 59/50-bit (64/64 padded) accounting envelope: the wider layout
does not truncate anchor-width lifecycle data.

| Entry field | Bits | Semantics |
| --- | ---: | --- |
| `head_control`: private/shared head and tail valid plus handles | `4 × (1 + slot[9:0] + generation[7:0]) = 76` | Two FIFO endpoints for each source.  Append changes a tail and possibly an empty head; terminal release changes a head and possibly a tail. |
| `head_control`: selection valid/source/epoch | `1 + 1 + 16 = 18` | Written only by accepted canonical oldest-source selection/dequeue. |
| `head_control`: reserved zero | 34 | Must never hold payload/address data. |
| **head-control word** | **128** | Copied to both replicas by one guarded commit or neither is modified. |
| `span_owner`: valid/source/self handle | `1 + 1 + 10 + 8 = 20` | A live semantic span and exact stale-safe identity. |
| `span_owner`: birth/sequence/remaining | `16 + 16 + 16 = 48` | Full anchor-width lifecycle values.  Dequeue subtracts only from the stored old value. |
| `span_owner`: previous and next valid handles | `2 × (1 + 10 + 8) = 38` | FIFO ownership links. |
| `span_owner`: reserved zero | 22 | Must remain zero. |
| **span-owner word** | **128** | Independently updated from head control. |

`valid=0` means no semantic record.  Reset clears every valid bit.  A release
clears a span only after the terminal release RMW commits.  The entry arrays
alone require `288 × 2 × 128 + 614 × 128 = 152,320` bits, **2.84×** the
frozen 53,696-bit padded accounting proxy, before lookup tags, free-list,
declaration queues, RMW comparison logic, or error state.  Every such added
term is Route-A incremental and `unestimated_not_zero`.

**Alternative rejected:** use the 64-bit proxy and reject values that exceed
the A4 6/11-bit accounting fields.  That silently makes the frozen workload
range a functional precondition and is not a general production encoding.

## 2. Key / generation / reuse

**Preferred: direct `(layer, kv_head)` head key and an M2-local span-handle
table.**

| Item | Decision |
| --- | --- |
| Bank | Accepted `kv_head[2:0]` remains the frozen logical bank selection only. |
| Head key | `(layer[5:0], kv_head[2:0])`, direct over 36×8 = 288 logical heads.  It is neither `opaque_address_ref` nor a physical row. |
| Span key | `M2SpanHandle={slot[9:0], generation[7:0]}` allocated by M2 storage.  The declaration carries explicit semantic identity `(layer, kv_head, source, birth, sequence)` which storage matches or allocates; a group identity is association-only, never the key. |
| Capacity | 614 live spans: the frozen joint-safe modeled peak, now explicit for the bounded anchor DUT.  Exhaustion is a typed fault, never eviction. |
| Reuse | Only `release_span` returns a slot and increments generation.  Reset invalidates all handles.  Generation wrap faults; it never aliases an old key. |
| Stale rule | Invalid handle, generation/key/source mismatch, duplicate append, nonterminal release, or dequeue old-value violation faults with no mutation. |

**Alternative rejected:** `(layer,head,logical_position >> 6)` assumes a
contiguous timeline group, while `(tag,stage_generation)` turns a transaction
association into an address.  Neither is allowed by the frozen retained-group
contract.

## 3. Lifecycle-to-RMW lowering

**Preferred unique owner:** the upstream **admission/metadata mapping owner**
is sole producer of `M2EntryUpdateDeclaration`; a new
`RouteAM2MetadataLifecycleOwner` is the sole in-DUT lowerer and association
owner.  It cannot select admission, source, authority, publication, or R2
work; it only verifies/stages upstream-declared lifecycle facts until storage
can execute them.

| Intent | Producer accepted event and input facts | Storage action / existing relation |
| --- | --- | --- |
| `append_span` | Accepted lifecycle append/maturity: layer, head, source, birth, sequence, initial remaining, semantic span identity; when packed-group-coupled, exact accepted stage/tag/opaque-ref/mapping-owner association. | Allocate/lookup a span, link its source FIFO, and atomically update head replicas.  Matching `head_control_rmw` and `span_owner_rmw` return `ok` only after both operations commit. |
| `select_oldest` | Accepted source-service selection with live source heads and chosen source. | Check true head state and write selection state in both replicas.  Ungrouped M2 operation; cannot publish. |
| `dequeue_span` | Accepted source-service dequeue with exact handle and positive amount. | Read true old span, check `remaining >= amount`, subtract, and update head state only if required.  Ungrouped. |
| `release_span` | Accepted terminal source-service release after zero remaining. | Check old value, unlink, atomically update affected head replicas, clear span, then free its slot.  It creates neither R6 authority nor page-free. |

No upstream producer supplies a full next word: M2 storage reads its own old
entry and executes the transform.  For current R3 publication, a declaration
must be accepted before its exact member request; R3 continues consuming only
`ok/fault` member responses.

**Necessary approval condition:** current Chisel has no source-service
`select_oldest`/`dequeue_span`/`release_span` production carrier and no source,
birth, sequence, or count input.  Package A therefore requires the explicit
upstream declaration producer.  Without it, only `append_group` provenance
journaling is possible and it must not be called M2 storage realization.

## 4. Typed storage-fault semantics

**Preferred: retain public `m2_op_rsp.status={ok,fault}` and add a private
fault-reason enum for assertions and coverage.**

| Condition | Producer | Effect |
| --- | --- | --- |
| Declaration genuinely pending | Lifecycle owner queue | `ready=0`, no state change or completion. |
| Missing/mismatched declaration; stale/invalid key; old-valid/precondition violation | Storage wrapper | No mutation; public member `fault`; private reason `declaration_mismatch`, `stale`, or `semantic_precondition`. R3 faults the stage; no publication. |
| Pool full or generation wrap | M2 allocator | No mutation; public `fault`; private `capacity` or `generation_exhausted`. |
| Dual-replica guard failure | One storage guarded commit | No replica-visible partial state; public `fault`; private `atomic_commit`. |
| Response backpressure | Existing response owner | Hold result stable; commit only on an `ok` result, never merely on `ready=0`. |
| Reset | Existing R3 init/reset discipline plus wrapper | Clear declaration, entry, tag, and free-list state; block traffic until named initialization conditions hold. |

There is no fabricated SRAM/ECC fault.  Only protocol, capacity, semantic,
generation, and guarded-atomicity faults are modeled; the reason enum is not a
second public status, terminal, or authority owner.

## Proposed carrier and cost ownership

`M2EntryUpdateDeclaration` is the sole new typed data carrier.  Its producer
is the admission/metadata mapping owner; its consumers are the lifecycle owner
and M2 storage.  It carries:

| Field | Width / source |
| --- | --- |
| `update_kind` | 2 bits: append/select/dequeue/release, from one accepted lifecycle event. |
| `layer`, `kv_head`, `source` | 6, 3, 1 bits; source is explicit semantic data, never an owner-ID inference. |
| `birth_opportunity`, `sequence_start`, `initial_or_dequeue_count` | 16 bits each; full anchor-width operands. |
| `span_slot`, `span_generation` | 10 and 8 bits; zero for append allocation, exact live handle otherwise. |
| `stage_generation`, `transaction_group_tag`, `opaque_mapping_ref`, `mapping_owner` | Existing parameterized widths; only for packed-group association and exact checking. |
| `expected_old_valid` | 1 bit checked by storage. |

The producer/lifecycle queue, direct head records, span pool, tag/free-list,
fault state, and RMW peripheral all stay inside the Route-A DUT and are
incremental `unestimated_not_zero` cost.  A later array-only boundary may omit
only entry-array interiors, never those controls.

## Chisel scope and acceptance after approval

- Modify `RouteAInterfaces.scala` for the bundle/channel, then
  `RouteAIncrementalSkeletons.scala` for the source/lifecycle owner and real
  storage child inside `RouteAM2ProductionControlOwner`.
- Add one named production source ingress to `RouteAMeasurementDut`; do not use
  a test-only provider or add Route-A logic to Full-KV.
- Preserve exact member/private-completion/publication candidate gates.
- Directed tests: append; all listed fault classes; backpressure; duplicate
  association; stale generation; release/reuse; generation wrap; two-source
  select; partial dequeue; terminal release; replica atomicity; reset; member
  fault blocking publication.
- Run M2/R3, W0, MR-1A, MR-1B, and dual-DUT structural non-regressions.

## Four-decision approval table

| Decision | Existing frozen fact | New choice requiring approval | Recommendation |
| --- | --- | --- | --- |
| Encoding/valid | 59/50 raw and two logical replicas | 128-bit words and release/reset meaning | Approve 128/128; account for 2.84× entry-array bits before additional control. |
| Key/reuse | eight banks, head scope, 614 modeled peak | 10-bit slot, 8-bit generation, bounded allocation/free | Approve pool, release-only reuse, no wrap. |
| Lowering | two grouped R3 members/all-or-fault publication prerequisite | explicit source/birth/sequence/count carrier and lifecycle owner | Approve package A; otherwise stop at non-closure journal. |
| Faults | public `ok/fault` and R3 fail-closed stage behavior | reason taxonomy and capacity/stale/atomic checks | Approve generic fault plus private reason enum; no SRAM/ECC claim. |

Package A is the minimum honest route to production M2 lifecycle storage.  It
is a bounded MR-2 realization decision, not a new planning phase.
