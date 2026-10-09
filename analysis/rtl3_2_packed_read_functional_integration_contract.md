# RTL3.2 — packed-page functional read to S2

**Status:** `complete_testbench_composed_functional_packed_payload_path_with_explicit_sidecar_boundary`.

RTL3.2 implements the already frozen RTL3.2-A owner as the synthesizable
`route_a_packed_read_association_owner` and proves one composed functional
read path:

```text
four exact live grants
  -> route_a_packed_read_association_owner
  -> existing delivery-context registry
  -> existing R2/R1 typed packed read
  -> testbench Route-A functional-memory environment
  -> existing typed packed-S2 endpoint
  -> route_a_s2_gqa_source_wrapper
```

The four immutable inputs remain the RTL3.2-A contract's `PackedSourceDemand`,
`PublicationReadAuthorization`, `DescriptorLocationGrant`, and `S2FillLease`.
The owner accepts them in arbitrary order, checks exact identity and `PageRef`
equality, publication authority, population/sidecar count, R5 live-reference,
and S2 sidecar requirement. It emits the existing registry allocation only
after that exact join, and emits one `PackedS2ReadWork` only after the registry
echoes the matching allocation/context. The work now carries that acknowledged
context reference; the old C4 verification ingress retains zero and is bound
by its historical common bridge.

## Scope closed

- The owner is a real main-source Chisel module, not the historical
  `RouteARTL26PublicationS2Association` test-only join.
- A directed composed harness binds the owner to the existing registry,
  `route_a_core_side_arbiter`, `route_a_core_mem_if_v1`, typed delivery
  router, packed-S2 endpoint, and S2 wrapper.
- The RTL3.1 host-side functional environment now binds at the composed
  `CoreMemoryExternalPort`; a preloaded 2-record object returns its sixteen
  payload fragments only through accepted R1 request/response traffic.
- The functional test proves that payload completion alone leaves S2 in
  `FILLING`; explicit matching sidecar fragments plus sidecar-complete are
  still required before `READY`.
- Directed module tests also cover arbitrary grant order, allocation
  ready-low stability, no work before a matching allocation acknowledgement,
  terminal-release observation, and page mismatch fail-closed behavior.

## Explicit residual boundary

RTL3.2 deliberately does **not** invent a sidecar transport by interpreting
payload traffic. In the composed harness, sidecar fragments/completion are an
explicit testbench boundary carrying the association owner's accepted identity,
S2 slot, and source generation. `DescriptorLocationGrant.sidecar_handle` is
transported as an obligation in the allocation target descriptor, but this
phase does not choose how a future sidecar request is issued, scheduled,
returned, or stored. The harness also uses the existing S2 service lease
input; it does not create an S2 allocator.

The owner has a typed terminal/release-observation interface. The packed-S2
endpoint-to-owner terminal adapter is intentionally not activated by this
slice, so the composed payload witness does not claim owner release, GQA
release, R4 partial production, attention terminal, retirement, or reclaim.
Those associations remain at their existing owners and must be connected under
a separately reviewed functional closure.

## Negative boundaries

RTL3.2 does not bind this path into `route_a_kv_subsystem_top`, select a
packed-source schedule, change R2 FIFO/credit/arbitration, alter R3 atomic
publication or R5 invalidation-before-free, or create a second authority,
metadata table, page table, descriptor decoder, S2 allocator, or memory
controller. It makes no HBM/SRAM macro, burst/channel/CDC, latency, bandwidth,
throughput, area, energy, PPA, model/GPU, numeric-R4, attention-MAC, or new A4
DSE claim.

## Directed verification and provenance

Run the no-model checks from the repository root:

```bash
.venv/bin/python -m pytest -q \
  tests/test_rtl3_2a_packed_read_association_reference.py \
  tests/test_rtl3_2a_packed_read_association.py
.venv/bin/python tools/validate_rtl3_2a_packed_read_association.py
cd hardware/route_a/chisel
sbt -batch 'testOnly kvpress.routea.rtl3.RouteAPackedReadAssociationOwnerSpec'
```

The Chisel suite contains no model/GPU invocation and no cycle/timing,
throughput, PPA, or RTL-correctness proof claim. Its fixed simulation budget is
only a bounded directed-test watchdog, not a latency measurement. The current
source-hash binding and exact commands are in
[`rtl3_2_packed_read_functional_integration_manifest.json`](rtl3_2_packed_read_functional_integration_manifest.json).
