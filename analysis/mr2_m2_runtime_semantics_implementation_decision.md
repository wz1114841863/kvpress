# MR-2 M2 runtime-semantics implementation decision

**Status:** decision proposed from frozen contracts and current production RTL;
no metadata-lifecycle producer is implemented by this record.  The concurrent
four-case `RouteAM2EntryStorageSpec` run may establish only the separately
labelled storage-unit result.

## Decision

**Selected implementation branch:** retain the A4 private/shared,
birth-ordered span lifecycle as an *accounting/replay contract*, not as an
implicitly required new Route-A runtime producer.  Implement the smaller
Route-A M2 runtime required by the architecture only after an explicit
production `MetadataAppend` fact carrier is approved and connected.  Until
then, production M2 entry integration remains **BLOCKED**.

This decision does not remove the frozen logical queue/credit/ownership
contract.  It distinguishes that contract from the A4 replay implementation:
the architecture requires M2/lifecycle state to preserve pending membership,
credit, ownership, and append order; it does *not* freeze the replay's two
source FIFOs, oldest-source comparator, birth counter, dequeue protocol, or
release protocol as existing Chisel runtime events.

## Evidence for the distinction

| Evidence | What it establishes | What it explicitly does not establish |
|---|---|---|
| `architecture_spec.md` §7 | Pending logical state is M2/lifecycle pending membership, credit, ownership, and append order; admission emits an append record plus metadata members. | A wire ABI for source, birth, sequence, count, semantic span handle, or a physical FIFO implementation. |
| `architecture_spec.md` §8 | Eight head-affine logical banks, two atomic head-control replicas, one span-owner store, and `local32/shared256/staging512` as lossless logical queue/credit capacities. | Physical FIFO depth/topology/replication, a source-selection algorithm, port schedule, or timing. |
| A4.14.0 binding contract | Retained-token-to-span lowering is deterministic conversion; bank/queue/service are declared model quantities. | A hardware `fire`, ready/valid carrier, controller, or runtime lifecycle owner. |
| `analyze_kvzap_route_a4681_representation_access_contract.py` | `BirthOrderedAccessState` replays source FIFO append/select/dequeue/release from trace-derived events. | A production RTL owner or accepted event. |
| Current Chisel ingress/R3/R6/S2 | R3 accepts retained-member provenance and issues two opaque M2 members; R6 owns authority/lifecycle; S2 owns payload fanout/release. | Any accepted source/birth/sequence/count or source-FIFO select/dequeue/release event. |

The existing architecture therefore requires a **minimal metadata runtime
semantic boundary**, but it gives no authority to silently promote the A4
analysis object's detailed queue policy into production logic.

## Current production facts and required additions

| M2 semantic need | Current owner / accepted event | Decision | Additional runtime logic, if later approved |
|---|---|---|---|
| Pending membership, applicable credit, ownership, append order | Architecture-level admission output; current Chisel preserves only group identity and opaque mapping provenance at `r6_admission_context_in.fire` plus `pending_payload_read_binding_in.fire`. | Required Route-A function, but the concrete update operand is absent. | One explicit `MetadataAppend` producer at the admission/metadata-mapping boundary. It must carry only accepted append facts, not select a mask/source/authority. |
| `append_span` in A4 replay | No current source/birth/sequence/count carrier or owner. | Not a currently proven runtime event. It may be the lowering of future `MetadataAppend`, subject to a separately approved field definition. | Append-record validation, bounded association/declaration queue, M2 storage RMW and status path. |
| `select_oldest` | No production source-FIFO selection event. `SourceCompletionPlan` chooses an attention source, not an M2 span. | Accounting replay only in the present DUT. | Only if a future runtime service contract names a semantic metadata consumer; it must be distinct from R6 attention-source planning and R2 arbitration. |
| `dequeue_span` / `release_span` | No accepted metadata consumption/release event. R1 terminals, R5 reclaim, and R6 terminal/retire are not span operations. | Accounting replay only in the present DUT. | Only with the same future service contract, exact live handle/count facts, and independent failure handling. |

`RouteAM2MetadataLifecycleOwner` is consequently **not authorized as a new
full lifecycle subsystem**.  If the selected branch is implemented, its sole
first responsibility is a bounded `MetadataAppend` lowerer/association owner.
It must not choose KVzap admission, attention source, R6 authority, R2 grant,
or R3 publication.  The missing input carrier remains a separate, narrowly
specified approval item; the current `opaque_address_ref`, group member,
logical position, payload reference, and fixture data are not substitutes.

## Grouped append and R3 two-member atomicity

The present R3 protocol is deliberately sequential:

```text
R3 request head_control member -> wait matching response
  -> R3 request span_owner member -> wait matching response
  -> R3 may request publication
```

`RouteAM2ProductionControlOwner` currently mutates its control state on each
individual response fire.  This is enough to gate publication, but it is **not
enough for data-state atomicity**: the first actual metadata write could remain
after a later span failure.  Conversely, making the first response wait for the
second request deadlocks the current R3 sequencing.

For a future grouped append, the minimum legal all-or-nothing mechanism is
therefore a new **single grouped transaction ingress**, accepted before the
legacy two response tokens:

1. `MetadataAppendGroupDeclaration.fire` carries one immutable group identity,
   both object operands, and a canonical association to the actual accepted
   append fact.  It is not inferred from the two R3 requests.
2. The M2 transaction coordinator validates capacity, both old-state
   preconditions, key/generation, mapping provenance, and both transforms
   before making any entry visible.
3. A single local commit atomically writes both head-control mirrors and the
   paired span-owner state.  If validation fails, it writes neither object.
4. Only after that internal outcome is durably held may the existing sequential
   member requests receive matching `ok` (one per request), or matching
   `fault` outcomes.  Response backpressure holds the outcome stable and never
   replays or partially mutates data.
5. R3 remains the sole publication issuer.  It sees both `ok` responses only
   after the atomic M2 commit; any `fault` leaves the group nonpublishable.

This adds a transaction coordinator, declaration/outcome holding state, and
two exact response associations.  It does **not** move R3's publication
linearization point, add a second authority, or change R2 scheduling.  A
future implementation must add a transaction-level carrier rather than trying
to retrofit atomic data semantics into the current per-member response fires.

## Cost comparison and retained evidence labels

| Choice | New control/state/interface scope | Status for cost evidence |
|---|---|---|
| Full A4 replay lifecycle in runtime | Two source FIFO head/tail sets, source-oldest comparator, birth/sequence counters, dequeue/release state machine, semantic service ingress, lifecycle declaration queue, 614-slot allocator/RMW, grouped-transaction coordinator. | Every added term is Route-A incremental `unestimated_not_zero`; A4 proxy/trace counts cannot price or justify it as an implemented runtime. |
| Selected smaller M2 runtime | Explicit admission-derived append record, bounded declaration/association state, key/valid/credit/ownership checks, grouped-transaction coordinator, head/span entry storage and RMW; no new source selector/dequeue/release engine. | Also Route-A incremental `unestimated_not_zero`. The 128-bit Package-A unit is an implementation candidate, not a production cost measurement. |
| Current control/provenance owner only | Two opaque member responses, mirrored control provenance and group completion gate. | Functionally integrated but insufficient to claim metadata data semantics, array-only boundary, or synthesis eligibility. |

No option may turn an omitted runtime item into zero cost.  The BOM must retain
the selected future lowerer, coordinator, RMW peripherals, queues/staging, and
entry-array interior as incremental unresolved evidence.

## Permitted next RTL branch and acceptance conditions

No lifecycle RTL is authorized by this decision alone.  The next approval,
if desired, should be limited to a `MetadataAppend`/group-declaration carrier
with:

- a named admission/metadata-mapping production owner and an exact accepted
  event for source-independent append facts;
- explicit membership/credit/ownership/append-order operands, key/reuse and
  valid rules; no derivation from R3 member order or non-contiguous retained
  groups;
- the transaction-level all-or-nothing adapter above; and
- directed tests for both-object failure, response backpressure, duplicate or
  stale declaration, reset, capacity fault, and proof that no publication
  occurs before both matching post-commit responses.

If later research requires A4 source-order select/dequeue/release at runtime,
that is a separately scoped extension with an explicit service-event contract
and incremental-cost review.  It cannot be smuggled into the append lowerer.

## Current disposition

| Item | Result |
|---|---|
| A4 detailed private/shared span lifecycle as automatically required production RTL | **No** — replay/accounting only under current contracts. |
| Architecture-required minimum M2 semantic responsibility | **Yes** — pending membership, credit, ownership, and append order, but carrier/data implementation still absent. |
| Package-A `RouteAM2EntryStorage` | Storage-unit candidate only; full four-case result recorded separately. |
| Production M2 entry storage / array-only boundary / synthesis eligibility | **BLOCKED** pending the explicit minimal append and transaction carrier. |
