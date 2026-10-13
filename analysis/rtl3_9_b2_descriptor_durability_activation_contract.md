# RTL3.9-B2 — R5 descriptor-durability functional activation

**Status:** `complete_functional_descriptor_durability_activation`.

RTL3.9-B2 closes the descriptor half of the already-composed Route-A write
chain.  It is deliberately narrower than atomic publication:

```text
R3 P3 COMPLETE
  -> R3 packed payload write / exact typed terminal
  -> R3 payload-durable fact
  -> R5 one-fragment descriptor-maintenance candidate
  -> existing delivery-context / R2 / R1 / typed router
  -> R5 aggregate descriptor-durability prerequisite
  -> R3 may begin its existing M2-member protocol
```

The test begins from the RTL3.9-A R3 materializer feedback path: it does not
inject `P3PackReadWork` or position sidecar as an external test fixture.  The
existing harness still retains its historical direct-work compatibility mode
for pre-B2 tests; B2 selects only the production-shaped materialized mode.

## Owner and exactness boundary

- R3 owns the immutable member/binding, P3 state, packed payload candidate,
  payload-durable acceptance, and acceptance of R5's prerequisite.
- R5 owns its post-payload one-fragment `new_page`/conditional `tail_link`
  maintenance candidate, descriptor durability aggregation, and its exact
  prerequisite result.
- Existing delivery-context composition, R2/R1, registry, and typed router
  retain the sole transport and response-association responsibility.
- The top remains composition-only.  Its legacy
  `descriptor_maintenance_terminal_in` tie-off remains inactive: the actual
  B2 descriptor terminal is `typed_delivery_router.r5_append_out` into
  `page_manager.append_delivery_in`.

The B2 directed path holds M2 member requests invalid after payload durability
and until the matching R5 descriptor terminal is accepted.  The R1 external
response port acknowledges a transport response; its `ready` is not an
architectural identity verdict.  Exact stale/mismatched append-delivery
rejection remains at the existing typed R2/R5 boundary, covered by
`RouteATypedDeliveryRouterSpec`'s
`fails closed on stale identity and routes descriptor terminals only to their
stored append or reclaim owner` test; it cannot expose an R5 prerequisite or
begin M2 work.  B2 covers the no-tail one-record functional baseline; tail-link
behavior remains the pre-existing R5 contract and is not reselected here.

## Explicit exclusions

Payload or descriptor durability is not `metadata_publish_commit`, descriptor
visibility, or a pending-to-packed authority handoff.  RTL3.9-B3 alone may
close the existing M2/publication/R5-visibility/R6 authority sequence.  B2
selects no HBM controller, SRAM macro, port count, physical descriptor layout,
clock/CDC, timing, throughput, area, energy, PPA, numeric RTL, model/GPU run,
or A4 DSE.

## No-model validation

```bash
.venv/bin/python tools/validate_rtl3_9_b2_descriptor_durability_activation.py --help
.venv/bin/python tools/validate_rtl3_9_b2_descriptor_durability_activation.py
.venv/bin/pytest -q tests/test_rtl3_9_b2_descriptor_durability_activation.py
cd hardware/route_a/chisel
sbt -batch 'Test / compile'
sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265a2PackReadPublicationSpec -- -z "materializes an A0-bound record"'
```

The selected Chisel/Verilator witness passed on 2026-10-13 with one test, zero
failures, and zero errors.  It is functional control/dataflow evidence only;
it makes no latency, throughput, physical-memory, numeric, or PPA claim.
