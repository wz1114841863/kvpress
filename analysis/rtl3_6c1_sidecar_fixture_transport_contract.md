# RTL3.6-C1 — S2 sidecar fixture transport closure

**Status:** `completed_testbench_only_named_sidecar_fixture_transport`.

RTL3.6-C1 closes the former direct testbench `s2_sidecar_fragment` /
`s2_sidecar_complete` injection in the RTL3.2 functional packed-read harness.
It does not physicalize sidecar storage or choose a memory request protocol.

## Unique testbench-only composition

```text
accepted RouteAPackedReadAssociationOwner allocation
  -> RouteARTL36cAllocationSidecarTap
  -> SidecarFixtureObligation
  -> RouteARTL36cSidecarFixtureTransport
  -> existing S2 sidecar fragment / complete inputs
  -> S2 READY only after existing payload completion too
```

The tap forwards the unchanged allocation to the existing delivery-context
registry. Its second output is a lossless testbench-only copy containing only
the allocation's already-selected identity, PageRef, S2 slot, generation,
descriptor-sidecar handle, and `expected_fragment_count / 8` sidecar record
count. It does not decode a descriptor image, derive an address, inspect a
payload response, select an S2 slot, alter R2 ordering, or own R5/M2/R3
authority.

The transport owns a finite test fixture keyed by the copied sidecar handle.
It waits for an exact S2 `FILLING + fill_open` observation with matching
identity, PageRef, and source generation. Only then does it emit the existing
ordered 64-bit `S2SidecarFragment` records and one `S2SidecarComplete`.
The harness reads the resulting value back through S2's existing sidecar-read
owner interface; it does not infer completion merely from `READY`.

## Fail-closed rules

- An invalid allocation shape, unknown fixture handle, or mismatched sidecar
  count produces no sidecar fragment or complete carrier.
- A stale/mismatched S2 identity, PageRef, or generation during `FILLING`
  moves the fixture transport to fail-closed state.
- In fixture-selected elaboration, the legacy manual sidecar ingress has
  `ready = 0`; a testbench cannot bypass this owner.
- Payload does not create or reconstruct sidecar data. The R1 functional
  payload path remains the existing RTL3.1/RTL3.2 evidence.

## Evidence and boundary

`RouteAPackedReadAssociationOwnerSpec` now verifies a functional-memory
payload read, accepted-allocation sidecar fixture replay, S2 `READY`, and a
sidecar readback of the fixture's first logical position. The isolated fixture
suite verifies unknown-handle and stale-generation failure cases. These are
bounded no-model tests; their watchdogs are not timing or throughput claims.

This C1 closure remains testbench-only. It does **not** create a production
top binding, live Python/Chisel co-simulation, HBM/sidecar controller request,
burst/address/port mapping, macro, MAC/RoPE/FP implementation, timing,
throughput, PPA, model/GPU result, or A4 DSE. Full reset-epoch composition
and the one-instance complete dataflow witness remain RTL3.6-C2 work.

## Validation

```bash
cd hardware/route_a/chisel
sbt -batch \
  'testOnly kvpress.routea.rtl3.RouteAPackedReadAssociationOwnerSpec' \
  'testOnly kvpress.routea.rtl3.RouteARTL36cSidecarFixtureTransportSpec'
cd ../../..
.venv/bin/python tools/validate_rtl3_6c1_sidecar_fixture_transport.py
```
