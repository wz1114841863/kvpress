# RTL3.8.2 — functional sidecar delivery

**Status:** `complete_i4_functional_sidecar_delivery_i5_i8_open`.

RTL3.8.2 closes only retirement-map item **I4**.  The production-shaped top
no longer exposes `verification_s2_sidecar_fragment_in` or
`verification_s2_sidecar_complete_in`.  It replaces the former fixture-only
transport with `route_a_functional_sidecar_delivery_adapter` and a typed
`S2PackedSidecar` response endpoint.

```text
accepted packed association
  -> exact payload read / S2 fill terminal
  -> matching successful PackedReadReleaseObservation
  -> functional sidecar delivery adapter
  -> sole delivery-context registry / existing packed R2 read class / R1
  -> registry-resolved S2PackedSidecar endpoint
  -> S2 sidecar fragment(s), then sidecar complete
```

The sequence is deliberate.  The immutable sidecar handle/count, PageRef,
identity, S2 slot, and source generation are copied only from the accepted
association.  A successful payload terminal is a prerequisite to issuing the
sidecar request; it is not a sidecar completion.  The adapter asks the
existing registry for a distinct typed context and reuses the existing packed
read class, so it adds no R2 class, FIFO, priority, arbitration rule, credit,
or scheduler policy.

## Ownership and fail-closed behavior

| Fact | Sole owner / source | RTL3.8.2 use |
|---|---|---|
| payload and sidecar handles, live descriptor | R5 accepted descriptor grant | The association copies fields; the adapter transports the sidecar handle only. |
| packed authority and record count | R3 post-atomic publication | Already required by the accepted association; no new publication occurs. |
| S2 slot/generation/filling state | S2 | Exact lease determines allocation descriptor and endpoint acceptance. |
| delivery context and typed response association | delivery-context registry, R2/R1 | A separate sidecar context is allocated only after payload success. |
| sidecar record and completion mutation | typed sidecar endpoint then S2 | The endpoint emits one 8-B logical record per legal R1 response, and emits complete only after its final record handshakes. |

The following conditions are fail-closed:

- no sidecar work is accepted for `valid_records == 0` or `> 64`;
- a delayed/mismatched payload release cannot start a sidecar allocation;
- payload terminal fault consumes the obligation without sidecar read, sidecar
  fragment, completion, fallback, or authority transition;
- allocation acknowledgement must exactly echo the held sidecar allocation;
- `S2PackedSidecar` routing requires the existing packed class, exact identity,
  PageRef, slot/generation, filling state, `requires_sidecar`, legal count,
  response ordinal, and exact final marker;
- a sidecar R1 fault becomes an S2 fault terminal and can never emit a fragment
  or complete; and
- final fragment and complete are serialized: completion cannot be offered in
  the same state as the final fragment.

`S2PackedSidecar` is a logical typed-delivery target only.  It does not select
an SRAM port, sidecar physical format, controller command, HBM burst,
interconnect, clock, or service rate.  The `RouteAExclusivePackedS2ReadIngress`
and terminal ingress express the already-required payload-before-sidecar
dependency and reject simultaneous offers rather than introducing local
priority or arbitration.

## What is closed and what remains open

Closed:

- I4 fixture transport and both corresponding top verification ingress ports
  are retired from the production-shaped functional top;
- accepted association descriptor/lease facts uniquely establish the sidecar
  address, record count, PageRef, identity, slot, and generation;
- sidecar traffic uses the existing registry -> R2 -> R1 -> typed router path;
- S2 observes fragment-before-complete ordering and receives fault only as a
  fault terminal.

Still open:

- I5/I6 functional hot/direct-pending payload-sideband replacement;
- I7/I8 dynamic partial-provider and functional R4 reference replacement;
- RTL3.8.5 all-source-subset/full-path coverage and aggregate provenance;
- physical HBM/SRAM/controller implementation, sidecar macro/layout choice,
  numeric FP/exp pipeline, timing, throughput, area, energy/PPA, DC, and
  complete LLM inference.

Thus this is functional synthesizable-control and directed protocol evidence,
not a memory-realization, numeric-realization, performance, deadlock, or PPA
claim.  It does not reopen pruning, admission, page size, M2 organization,
queue/scheduler semantics, P3 mapping, S2 count, GQA legality, atomic commit,
or the Route-A choice.

## Directed checks

```bash
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl3.RouteAFunctionalSidecarDeliverySpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl3.RouteAPackedReadAssociationOwnerSpec -- -z "joins arbitrary-order"'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl2.RouteAPackedS2ReadPathSpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.r2.RouteADeliveryContextRegistrySpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.r2.RouteATypedDeliveryRouterSpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec'
.venv/bin/python tools/validate_rtl3_8_2_functional_sidecar_delivery.py
.venv/bin/python -m pytest -q tests/test_rtl3_8_2_functional_sidecar_delivery.py
```

The new directed suite proves successful payload-terminal gating, copied typed
read fields, payload-fault suppression, mismatched-release backpressure, final
fragment-before-complete ordering, and sidecar-fault mapping.  Existing
registry/router/packed-S2 suites re-check the modified target-class and typed
demultiplexing boundaries.  No model or GPU is invoked.
