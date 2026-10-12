# RTL3.9-A0 — pending-payload read-association closure

**Status:** `complete_pending_payload_provenance_binding_pre_rtl3_9_a_materialization`.

RTL3.9-A0 closes the provenance gap discovered by RTL3 completion Review-04:
an immutable R3 admission member had a logical `payload_ref`, but neither the
request identity nor the pending payload owner's opaque handle/generation was
available to form a safe later `P3PackReadWork`.

This change introduces the logical, ready/valid
`PendingPayloadReadBinding` association:

```text
pending_payload_storage_owner
  -> pending_payload_read_binding
  -> R6 retained admission / authority pair
  -> route_a_admission_publication_ingress_adapter
  -> R3 immutable member ledger
```

It does **not** activate `p3_pack_read_work`, choose a member issue order,
change the fixed one-member/eight-fragment transaction granularity, alter R2
FIFO/arbitration/credit policy, or select a memory address encoding,
controller, burst, port, macro, clock, or performance model.

## Sole owner and exact association

`pending_payload_storage_owner` is the sole producer of the opaque pending
location fact.  It may provide only:

- `transaction_identity`;
- immutable admission coordinates (`entry_id`, layer, KV head, logical
  position, `payload_ref`, group tag, member ordinal, valid-record count);
- `payload_handle_or_address`, `source_generation`, and opaque logical
  `destination_endpoint`.

The handle is not derived from `payload_ref`; the source generation is not
derived from a P3 stage generation; and identity is not reconstructed from
`entry_id`.  These distinctions are mandatory for stale-response exclusion.

The admission-publication adapter accepts a retained member only when the
existing R6 `AdmissionContext`, hot-to-pending authority transition, and this
binding all match and fire atomically.  It stores all three by immutable member
ordinal, obtains the pre-existing R5 allocation and R3 P3 claim, then relays
the same three facts atomically to R3.

R3 records the binding beside its existing immutable admission ledger.  A
future `P3PackReadWork` may be accepted only when its `payload_ref`, identity,
opaque handle, source generation, and destination endpoint exactly equal the
recorded binding.  An absent binding remains permitted only for the existing
hot-payload-only R3 unit paths; it cannot authorize a pending-memory
`pack_read`.

## Fail-closed rules

- Split context/authority/binding offers do not consume any member fact.
- Any coordinate, `payload_ref`, group tag, ordinal, or record-count mismatch
  is ready-low and records no binding.
- A duplicate ordinal cannot replace an existing immutable binding.
- Work with a correct member reference but mismatched identity, opaque handle,
  source generation, or endpoint is not accepted and cannot create an R1
  request or P3 deposit.
- Destructive reset clears the in-flight adapter group and R3 binding presence
  together with the corresponding transient stage state.

## Scope boundary and next step

This is an interface/association closure only.  The top still ties
`p3_pack_read_work` inactive; RTL3.9-A may now be evaluated separately as a
small R3-owned materializer from recorded member binding to one immutable
eight-fragment work item.  That later step must not make this binding a
scheduler, reorder policy, physical address translation, or new authority
owner.

The direct-pending producer, source K/V-plus-position lease export,
test-only release observer retirement, live source-to-partial realization,
numeric RTL, memory/controller/macro, timing, throughput, area, energy, PPA,
DC, model/GPU evaluation, and complete LLM inference remain out of scope.

## No-model verification

```bash
cd hardware/route_a/chisel
sbt -batch \
  'testOnly kvpress.routea.rtl2.RouteAAdmissionPublicationIngressAdapterSpec' \
  'testOnly kvpress.routea.rtl2.RouteAR3PackReadPathSpec' \
  'testOnly kvpress.routea.rtl2.RouteARTL265a2PackReadPublicationSpec' \
  'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec'
```

The machine-readable manifest and its validator hash-bind the current source,
contract, interface manifest, and directed test sources.  Evidence labels are
functional control/provenance protocol only: no model/GPU, cycle/timing,
throughput/deadlock, numeric RTL correctness, PPA, or new A4 DSE claim.
