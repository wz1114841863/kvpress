# RTL3.8.5 — full-path closure coverage

**Status:** `complete_directed_functional_path_coverage_pre_final_rtl3_review`.

RTL3.8.5 is a directed, no-model coverage closure over one elaborated
production-shaped Chisel harness.  It composes existing R6 lifecycle, the
functional partial-provider boundary, source-service packet adapter, R4 packet
acceptance boundary, RTL3.8.4 functional-R4 reference boundary, and the
existing R4-to-R6 terminal chain.

```text
named partial-provider packets
  -> source-service packet acceptance
  -> four consumer partial commits per selected source
  -> test-only completion observer
  -> R6 selected-source releases
  -> four R6 merge works
  -> functional-R4 packet/work boundary
  -> dynamic success XOR fault response
  -> existing R4/R6 terminal
```

The harness's commit/release observer is verification infrastructure only.  It
observes four exact existing `ConsumerPartialCommit` carriers and emits an
existing `SourceRelease`; it neither chooses sources, emits partials, selects
admission/mask/authority, changes source order, or becomes a production owner.
Hot/direct/S2 ownership therefore remains unchanged.

## Historical provenance

The original aggregate `source_sha256` snapshot belongs to immutable coverage
closure commit `ade9d37fc10c261377ba4ab49ac87d0b683dd0ff`.  The validator now
replays it through `git show`, using
[`rtl3_8_5_full_path_closure_coverage_historical_provenance.json`](rtl3_8_5_full_path_closure_coverage_historical_provenance.json).
It therefore preserves historical coverage evidence without treating later
valid changes to shared source or the live phase ledger as a failure; it does
not certify C0--C3 or physical implementation.

## Directed coverage

Using one elaborated harness and reset epochs between independent transactions,
the success path covers source-presence masks `001` through `111`.  For every
mask it verifies:

- each selected source sends four consumer packet/commit sequences;
- R6 sees releases only after four exact commits per selected source;
- the R4 reference boundary emits exactly four ordered consumer work items;
- dynamic matching success responses yield one R6 group success terminal.

Additional paths cover:

- packet-accept ready-low followed by exact packet delivery;
- merge-work ready-low followed by a dynamic numeric fault and one group fault
  terminal;
- a stale R4 response that remains rejected and produces no terminal; and
- destructive reset clearing the held stale-response state.

## RTL3.8.4 protocol repair observed by this closure

The first all-subset run found that `route_a_functional_r4_reference_boundary`
could reissue a completed consumer while `route_a_merge_boundary` retained its
active observation during terminal handoff to R6.  RTL3.8.5 adds a
completion-quiescent association latch:

```text
matching R4 response accepted
  -> completed (identity, consumer) quiescent
  -> no repeat work for that association
  -> rearm only after observation disappears or switches identity/consumer
```

This changes no numeric result, source schedule, ownership, authority,
admission, or terminal route.  It is a necessary ready/valid correctness
repair discovered by the coverage harness.

## Aggregate current closure record

This stage creates a *current* aggregate manifest referencing RTL3.8.0--3.8.5
and the live implementation/test sources.  Older manifests intentionally
remain immutable historical records; their hash validators need not replay
after later shared-source evolution and are not rewritten here.

## Remaining limits

RTL3.8.5 does **not** close RTL3 or authorize physical/numeric/PPA work:

- I5/I6 still have no live named R3 P3-read/direct-read work producer, and
  actual source-owner K/V/position lease export remains open;
- the partial packets in this coverage harness are named outer functional
  environment packets, not attention-MAC/RoPE implementation;
- the R4 responder is a dynamic protocol fixture.  The frozen Python
  RTL3.4-B oracle remains separate pure-software evidence; no same-simulation
  Python/Chisel co-simulation is claimed;
- the test-only release observer is not a source owner or synthesis candidate;
- no HBM/SRAM/controller/CDC, FP/exp/MAC pipeline, timing, throughput,
  deadlock, area, energy, PPA, DC, model/GPU, complete inference, or new A4
  DSE claim follows.

## No-model verification

```bash
cd hardware/route_a/chisel && sbt -batch \
  'testOnly kvpress.routea.rtl3.RouteARTL385FullPathClosureSpec' \
  'testOnly kvpress.routea.rtl3.RouteAFunctionalR4ReferenceBoundarySpec' \
  'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec' \
  'testOnly kvpress.routea.integration.RouteAInitDrainIntegrationSpec'
.venv/bin/python -m pytest -q \
  tests/test_route_a_merge_numeric_reference.py \
  tests/test_rtl3_3_r4_functional_profile.py \
  tests/test_rtl3_4b_functional_r4_provider.py \
  tests/test_rtl3_8_5_full_path_closure_coverage.py
.venv/bin/python tools/validate_rtl3_8_5_full_path_closure_coverage.py
```
