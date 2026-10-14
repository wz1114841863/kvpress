# RTL3.9-C2 — post-publication packed read to S2

**Status:** `complete_functional_post_publication_read_to_s2`.

## Purpose and fixed boundary

C2 extends the completed C0/C1 first-use gate through one actual typed read
and fill path.  It starts only after the existing R3 publication, R5-visible
descriptor, and R6 acceptance facts have formed C1's exact packed-read
association.  C2 does not change the production top, pruning, admission,
page size, M2/P3 or S2 mapping, GQA legality, R2 scheduling, or the sole R3
atomic-publication boundary.

```text
C1 held packed-read association
  -> existing allocation mux / unified allocation bridge / sole registry
  -> existing typed R2/R1 read, delivery router, and endpoint demultiplexer
  -> packed payload endpoint -> S2 payload fill
  -> functional sidecar delivery adapter -> sidecar endpoint -> S2 sidecar fill
  -> existing S2 owner: matching payload + sidecar + terminal => READY
```

`RouteARTL265a2PackReadPublicationHarness` is a test-only same-instance
composition.  It wires existing owners; it is not a production-top change,
a second authority, a new descriptor owner, or a read scheduler.

## Owners and provenance

- R3 keeps the immutable membership ledger and the unique publication fact;
  R6 accepts the existing packed authority transition; R5 owns descriptor
  visibility; and S2 alone owns its slot state and `READY` decision.
- The existing packed allocation mux serializes mutually exclusive payload and
  sidecar allocations.  The existing unified bridge, sole context registry,
  R2/R1 interfaces, typed delivery router, and endpoint demultiplexer retain
  their established ownership of allocation, transport, resolution, and
  response routing.
- The existing packed terminal bridge creates no authority: it forwards the
  C1 association work to the packed S2 producer and returns only the exact
  endpoint terminal needed by the association owner.  The existing functional
  sidecar adapter waits for its matching payload-release observation before
  issuing its distinct read.
- R1 response data are supplied by the already-authorized functional-memory
  outer environment.  That environment is neither an HBM controller nor an
  SRAM macro.  C2 assigns no attention computation, numeric implementation,
  service rate, or performance property to it.

## Directed evidence and fail-closed behavior

The no-model Chisel/Verilator witness runs the actual B3 publication and C0/C1
activation sequence, then drives the existing functional R1 response boundary.
It proves one owner-correct payload and one sidecar reach S2 `READY`.  Before
the matching payload response, a stale request identity is offered and S2
remains `FILLING`.  A destructive reset after `READY` returns the slot to
`EMPTY`.  On a matching payload terminal fault, S2 becomes `FAULTED`, no
sidecar request issues, and `READY` is impossible.

The reused packed endpoints retain their direct checks for exact page,
generation, slot, fragment count/ordinal, and terminal association.  C2 does
not weaken those checks or accept a reconstructed response context.  This
same-instance C2 witness specifically exercises stale identity, payload
terminal fault, and reset; endpoint-level stale page/generation/slot tests
remain the established focused evidence for those distinct ingress fields.

## Explicit stop point

C2 ends when S2 reaches `READY` or fail-closes to `FAULTED`.  It does not
activate S2 source service, any source packet, consumer partial commit, the
permitted outer partial-provider/R4 boundary, R6 attention terminal, runtime
retirement, or R5/R6 reclaim.  Those are C3/C4 work.  In particular, C2 does
not claim completion of whole-page lifecycle or an RTL3 PASS.

## Validation

```bash
.venv/bin/python tools/validate_rtl3_9_c2_functional_read_to_s2.py --help
.venv/bin/python tools/validate_rtl3_9_c2_functional_read_to_s2.py
.venv/bin/pytest -q tests/test_rtl3_9_c2_functional_read_to_s2.py
cd hardware/route_a/chisel
sbt -batch 'Test / compile'
sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265a2PackReadPublicationSpec -- -z "delivers the first post-R6 packed payload"'
```

The selected same-instance test passed on 2026-10-14 with one test, zero
failures/errors (689.439 s, including Verilator generation and C++ build).
This is functional control/dataflow evidence only.

## Evidence boundary

C2 establishes no physical HBM/controller/SRAM realization, attention MAC,
FP/exp/RoPE pipeline, clock/CDC, timing, bandwidth, throughput, area, energy,
PPA, model/GPU result, or complete LLM inference engine.  It introduces no
new DSE and reopens none of the frozen KVzap or Route-A architectural choices.
