# RTL3.8.1 — packed activation binding

**Status:** `complete_production_shaped_i0_i3_owner_binding_i4_sidecar_open`.

RTL3.8.1 implements `route_a_packed_read_activation_binder`, the narrow
I0--I3 materializer named by the RTL3.8.0 ingress-retirement freeze.  It turns
one exact set of already-owned facts into the four input carriers consumed by
`route_a_packed_read_association_owner`:

```text
R6 accepted SourceCompletionPlan (packed present)
R3 post-atomic PublicationCommitObservation
R5 readable DescriptorLocationGrant
S2 owner-local S2FillLease
                         |
                         v
route_a_packed_read_activation_binder
  -> DescriptorLocationRequest -> R5 -> DescriptorLocationGrant
  -> S2FillLeaseRequest        -> S2 -> S2FillLease
  -> PackedSourceDemand
  -> PublicationReadAuthorization
  -> DescriptorLocationGrant
  -> S2FillLease
                         |
                         v
route_a_packed_read_association_owner
```

RTL3.8.1 now also binds those already-owned facts into the production-shaped
top.  The top's exact plan fork gives the original R6 plan to the existing
source-packet path and gives a packed-present copy to this binder.  The
downstream owner-built allocation reuses the existing R5/S2 packed ordering
lane in the sole delivery-context bridge; it does not create a new allocation
owner, R2 class, priority, or scheduling rule.  The final packed endpoint
terminal passes through a named bridge to both S2 and the association owner.

This is a functional control/association binding.  It does not implement a
memory controller, SRAM macro, numeric datapath, throughput model, or PPA
model.

## Ownership and exact join

The binder is the sole owner of **materializing the four association inputs**;
it is not the owner of any input fact.  It now issues two address-free owner
queries after holding the R6 plan and R3 publication fact.  The R5 and S2
responses are connected back to the binder in one same-instance integration
harness; tests no longer supply descriptor handles or lease slot values.

| Fact | Sole producer/owner | Binder responsibility |
|---|---|---|
| source-set and selected packed `SourceInstance` | R6 accepted plan | Require packed-presence and exact packed slot/generation match. |
| published page, tag, valid-record count | R3 post-atomic commit observation | Require legal `1..64` record count and copy it only after exact page join. |
| payload/sidecar handles and live descriptor reference | R5 | Require exact page/count and `live_reference_held`; never decode or mutate the descriptor. |
| S2 slot, generation, sidecar requirement | S2 | Require exact identity/page and exact match to R6 packed `SourceInstance`; never allocate or infer a slot. |

R5 accepts a descriptor query only for an allocated, post-publication readable
page with exact generation and record count.  It owns the existing functional
page layout mapping: payload handle `page_id * 33,280` and sidecar handle
`payload + 32,768`.  These are logical functional-memory handles inherited
from the packed-page realization, not HBM physical addresses or a controller
mapping.

The binder does not request S2 state until the R5 descriptor grant has arrived
and itself matches the held identity, page, record count, sidecar count, and
live-reference requirements.  Thus a stale, unpublished, aliased, or malformed
R5 page cannot strand an S2 slot in FILLING while waiting for a usable
descriptor response.  R5 additionally rejects page IDs outside its allocator
entry range rather than allowing low-bit index aliasing.

S2 accepts a lease request only when the selected source kind is packed, the
selected coordinate names one of its two logical slots, that slot is EMPTY,
and its next owner generation equals the R6-selected generation.  Acceptance
atomically reserves the slot as FILLING and returns the exact lease.  A legacy
explicit service request and a lease request cannot win simultaneously.

The R3 observation has no transaction identity by design.  It is safe to bind
it to the R6 transaction only after `PageRef`, record-count, S2 lease, and R5
descriptor facts all join exactly.  A mismatched page, identity, slot,
generation, sidecar count, non-live descriptor, absent packed source, or
illegal record count causes fail-closed discard and produces no demand,
publication authorization, descriptor grant, or lease output.

The binder has one bounded held association.  This is a conservative
functional realization baseline and does **not** alter the frozen R2
FIFO/eligibility/credit/arbitration contract or select a page/source.

## Materialized fields and limits

- `PackedSourceDemand.page_ref` is copied from R3's post-atomic publication
  fact; it is never inferred from an S2 slot, page ID bit slice, or test
  default.
- `PublicationReadAuthorization.packed_authoritative` is true only because
  the input is R3's post-atomic publication observation.  The binder emits no
  publication request, acknowledgement, or authority transition.
- `DescriptorLocationGrant` and `S2FillLease` are transported unchanged.
- The local monotonic demand ordinal is a one-entry materialization label.  It
  is neither an R2 scheduler decision nor an outstanding-request bound.  The
  existing R2 owner still consumes the frozen eligibility snapshot and chooses
  among accepted candidate work.
- The current functional target uses opaque logical destination code `0`, the
  same non-physical core-memory placeholder used by the existing functional
  path.  It is not an HBM channel, port, bank, controller, or macro decision.
  A later functional-top connection must bind a named existing R1 logical
  destination without changing scheduler semantics.

## Production-shaped composition and what is closed

The resulting I0--I3 carrier path is:

```text
R6 accepted plan --exact fork--> packet path
                 \--packed-present copy--> activation binder
R3 publication observation ----------------------^
R5 descriptor query/grant -----------------------^
S2 lease request/grant ---------------------------^
                                                |
                                                v
                                      association owner
                                                |
                       prebuilt allocation through existing packed lane
                                                |
                                                v
                              sole delivery-context registry -> R2/R1
                                                |
                                                v
        typed packed endpoint -> terminal bridge -> S2 and association owner
```

The bridge does not make endpoint payloads, mark S2 READY, create a source
release, or create an R4/R6 terminal.  A stale terminal identity cannot pass
the bridge.  The only existing verification ingress retired here is the
packed-path pair `verification_s2_service_req_in` and
`verification_packed_s2_read_work_in`; the separate I4 sidecar verification
ingress remains explicit and is the scope of RTL3.8.2.

Closed for RTL3.8.1:

- I0--I3 have an executable **single exact association materializer** with
  ready/valid stability assertions, and are connected into the
  production-shaped top rather than held behind those two packed verification
  ingress ports;
- R5 and S2 have explicit owner-local request/grant protocols wired directly
  to the binder in a same-instance functional integration harness;
- descriptor handles and S2 lease slot/generation are no longer testbench
  inputs in that integration path;
- a demand cannot be created from a plan lacking packed presence;
- page, descriptor, lease slot/generation, record-count, sidecar, and
  identity disagreement are fail-closed;
- directed ChiselSim tests prove the output bundle is exact and stable under
  output backpressure, exact plan fanout, existing-lane allocation/ack routing,
  and final-terminal association.

Not closed:

- I4 functional sidecar delivery: `verification_s2_sidecar_fragment_in` and
  `verification_s2_sidecar_complete_in` remain intentional, visible
  verification ingress and must not be reclassified as owner-produced data;
- I5/I6 source payload activation, I7/I8 dynamic partial/R4 replacement, and
  RTL3.8.5 full-path coverage;
- physical memory, numeric FP/exp, controller, macro, timing, area, energy,
  throughput, DC, or PPA realization.

Accordingly, this record must not be interpreted as full functional-source
replacement.  It retires only the packed I0--I3 work/service verification
pair, preserves the I4 sidecar boundary explicitly, and does not conceal a
missing sidecar or partial producer behind a top-level tie-off.

## Directed checks

The exact no-model command is:

```bash
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl3.RouteAPackedReadActivationBinderSpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl3.RouteAPackedActivationOwnerFactIntegrationSpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl3.RouteAPackedReadAssociationOwnerSpec -- -z "joins arbitrary-order"'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl3.RouteAPackedActivationCompositionSpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl3.RouteAPackedAssociationAllocationBridgeSpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec'
```

The four binder checks cover exact positive materialization, ready-low
stability, descriptor/page mismatch, absent packed source, and S2 lease
slot/generation mismatch.  Four same-instance owner tests additionally cover
an R5-published descriptor plus S2 reservation without test-supplied
handle/slot facts, stale R5 generation plus invalid S2 next-generation
fail-closed behavior, and rejection of an out-of-range page ID that would
otherwise alias an allocator entry.  The three new composition checks cover
the exact plan fork under independent stall, stale-terminal rejection plus
final terminal association, and existing-packed-lane allocation/ack routing.
The separate provenance validator verifies the hash-bound source set.

## Evidence boundary

This is pure synthesizable-control and directed ChiselSim protocol evidence.
It makes no model/GPU, full-inference, numeric correctness, RTL performance,
cycle/timing/throughput/deadlock, physical memory/controller/macro, area,
energy/PPA, DC, or new A4 DSE claim.  It does not reopen pruning, admission,
page size, M2 organization, queue/scheduler semantics, P3 mapping, S2 count,
GQA legality, atomic commit, or Route-A/Route-B choice.
