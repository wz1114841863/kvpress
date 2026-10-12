# RTL3.8.3 — source/partial boundary isolation

**Status:** `complete_i5_i6_ingress_isolation_partial_boundary_i7_i8_open`.

RTL3.8.3 closes the next narrow RTL3.8 step: it removes the remaining
interior top-level verification ingress for P3 pack-read work and
direct-pending open/read work, and replaces source-packet structural tie-offs
with one named `route_a_functional_partial_provider_boundary`.

```text
accepted R6 source plan + owner availability observations
       + named outer functional partial-provider packet carriers
                              |
                              v
 route_a_functional_partial_provider_boundary
                              |
                              v
 existing source-service packet adapter -> existing R4 boundary
```

The new boundary is transparent ready/valid transport only.  It does not
perform attention arithmetic, inspect K/V payload, generate source offers,
select sources, allocate storage, change source order, create a consumer
commit, release a source, or generate R4/R6 terminal behavior.  The existing
source-service packet adapter remains the acceptance authority for R6 plan,
hot -> pending -> packed order, owner availability, source instance,
identity, consumer, header, and eight-fragment structure.

## I5/I6 disposition

| Retirement item | RTL3.8.3 action | Current result |
|---|---|---|
| I5 `verification_p3_pack_read_work_in` | Removed from `RouteAKVSubsystemTop`; the carrier is explicitly inactive because no separately authorized R3 pack-read producer exists in this top. | Isolated; no top-generated P3 read, scheduler, or fallback. |
| I6 `verification_direct_pending_open_in` | Removed; `RouteADirectPendingEndpointV1` accepts only the existing R6 lifecycle open carrier. | Isolated; no mixed verification/R6 source. |
| I6 `verification_direct_pending_read_work_in` | Removed; the direct read producer work input is explicitly inactive until the named R6/direct owner can materialize immutable work. | Isolated; no synthetic direct read. |
| source packet tie-offs | Replaced by the named outer functional partial-provider boundary. | Activated boundary only; not a K/V or numeric implementation. |

The explicit inactive carriers are intentional.  They preserve the frozen
rule that the composition top cannot become a temporary R3/direct producer,
source scheduler, or Full-KV fallback.  A later closure must name the exact
R3/direct owner and immutable association before those carriers can become
live; merely adding a top input or testbench stimulus is prohibited.

## Owner and environment rules

- Hot, direct-pending, and S2 remain the sole owners of K/V payload,
  logical-position sideband, source identity, and generation.  None may
  produce `(m,l,o)` merely by owning storage.
- `route_a_functional_attention_partial_provider` remains the sole allowed
  outer producer of present `SourceServicePartialOffer` and
  `SourceServiceValueFragment` carriers.  Its query/position/RoPE contract is
  the already frozen RTL3.5-A boundary.
- The outer provider is constrained by the existing packet adapter and owner
  observations.  It does not gain authority, R2/R1 ownership, source release,
  R4 result, or outward terminal ownership.
- No new query/K/V transport, attention MAC, RoPE operation, exp/FP unit,
  numeric model, memory controller, SRAM/HBM macro, clock, port, scheduler,
  or PPA claim is made here.

## What is and is not closed

Closed for this slice:

- no `verification_p3_pack_read_work_in`,
  `verification_direct_pending_open_in`, or
  `verification_direct_pending_read_work_in` remains on the composed top;
- direct-pending open has one source: existing R6 lifecycle state;
- source packet carrier ingress has one named outer functional-provider
  boundary rather than six structural tie-offs; and
- ready-low pass-through and source-lane separation are directed-tested.

Still open:

- live R3 P3 pack-read producer and live direct-pending read-work producer;
- actual source-owner K/V/position lease export to the functional provider;
- I7/I8 dynamic functional R4 result/fault replacement;
- all-source-subset/full-path coverage in RTL3.8.5; and
- physical/numeric realization, controller/macro, timing, throughput, area,
  energy, PPA, DC, and complete LLM inference.

This is therefore **ingress isolation plus interface activation**, not full
functional-source payload realization or an RTL3 completion pass.

## Directed no-model checks

```bash
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.rtl3.RouteAFunctionalPartialProviderBoundarySpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec'
cd hardware/route_a/chisel && sbt -batch 'testOnly kvpress.routea.integration.RouteAInitDrainIntegrationSpec'
.venv/bin/python tools/validate_rtl3_8_3_source_partial_boundary_isolation.py
.venv/bin/python -m pytest -q tests/test_rtl3_8_3_source_partial_boundary_isolation.py
```

Evidence is directed ChiselSim/structural protocol evidence plus hash-bound
provenance only.  No model or GPU is run.
