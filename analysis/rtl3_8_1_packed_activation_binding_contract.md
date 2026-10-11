# RTL3.8.1 — packed activation binding

**Status:** `complete_functional_owner_binding_not_yet_functional_top_replacement`.

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
  -> PackedSourceDemand
  -> PublicationReadAuthorization
  -> DescriptorLocationGrant
  -> S2FillLease
                         |
                         v
route_a_packed_read_association_owner
```

This is a functional control/association binding.  It does not implement a
memory controller, SRAM macro, numeric datapath, throughput model, or PPA
model.

## Ownership and exact join

The binder is the sole owner of **materializing the four association inputs**;
it is not the owner of any input fact.

| Fact | Sole producer/owner | Binder responsibility |
|---|---|---|
| source-set and selected packed `SourceInstance` | R6 accepted plan | Require packed-presence and exact packed slot/generation match. |
| published page, tag, valid-record count | R3 post-atomic commit observation | Require legal `1..64` record count and copy it only after exact page join. |
| payload/sidecar handles and live descriptor reference | R5 | Require exact page/count and `live_reference_held`; never decode or mutate the descriptor. |
| S2 slot, generation, sidecar requirement | S2 | Require exact identity/page and exact match to R6 packed `SourceInstance`; never allocate or infer a slot. |

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

## What is and is not closed

Closed for RTL3.8.1:

- I0--I3 have an executable **single exact association materializer** with
  ready/valid stability assertions;
- a demand cannot be created from a plan lacking packed presence;
- page, descriptor, lease slot/generation, record-count, sidecar, and
  identity disagreement are fail-closed;
- directed ChiselSim tests prove the output bundle is exact and stable under
  output backpressure.

Not closed:

- production-top replacement of the current verification ingress;
- an R5 top-level readable-descriptor producer and S2 top-level lease producer
  connected to this binder;
- I4 functional sidecar delivery, I5/I6 source payload activation, I7/I8
  dynamic partial/R4 replacement, and RTL3.8.5 full-path coverage;
- physical memory, numeric FP/exp, controller, macro, timing, area, energy,
  throughput, DC, or PPA realization.

Accordingly, this record must not be interpreted as retiring the current top
verification ingress yet.  It creates the tested owner boundary that later
steps must connect; it does not conceal missing producers behind a top-level
tie-off.

## Directed checks

The exact no-model command is:

```bash
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl3.RouteAPackedReadActivationBinderSpec'
```

The four deterministic checks cover exact positive materialization,
ready-low stability, descriptor/page mismatch, absent packed source, and S2
lease slot/generation mismatch.  The separate provenance validator verifies
the hash-bound source set.

## Evidence boundary

This is pure synthesizable-control and directed ChiselSim protocol evidence.
It makes no model/GPU, full-inference, numeric correctness, RTL performance,
cycle/timing/throughput/deadlock, physical memory/controller/macro, area,
energy/PPA, DC, or new A4 DSE claim.  It does not reopen pruning, admission,
page size, M2 organization, queue/scheduler semantics, P3 mapping, S2 count,
GQA legality, atomic commit, or Route-A/Route-B choice.
