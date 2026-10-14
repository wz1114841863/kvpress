# RTL3.9-C3a — packed source service to R6 terminal

**Status:** `complete_functional_packed_source_service_to_terminal`.

C3a continues the C2 same-instance witness only after S2 is `READY`. The
already accepted packed-present plan reaches the existing S2 service owner,
the existing packet adapter, the named functional partial-provider boundary,
the existing R4 reference boundary, and the existing R6 terminal owner.

```text
C2 S2 READY + accepted packed plan
  -> R6 S2 service request -> S2 availability
  -> packet adapter + four outer packed partial packets
  -> existing R4 packet acceptance / four consumer commits
  -> S2 release after its four commits
  -> R6 four merge works + outer R4 results
  -> existing merge boundary -> one R6 attention terminal
```

The partial-provider and R4 result carriers remain explicit functional outer
environments. They neither select a source, own S2 state, release a source,
create a terminal, nor implement an attention MAC, RoPE, FP/exp pipeline, or
physical memory/controller.

The same-instance directed witness uses the real B3/C0/C1/C2 path, makes S2
`READY`, then supplies four exact packed packets and four matching R4 success
results. It observes one R6 success terminal for the exact identity. The S2
owner alone receives the four commits and only then releases its packed source.

C3a deliberately stops after R6 terminal. Runtime retirement, joined drain
status, R6 reclaim permit, R5 invalidation/page free, reclaim completion, and
session retire acknowledgement remain C3b. C4 remains responsible for the
cross-owner event-scoreboard and aggregate fault/stall/reset review.

## Validation

```bash
.venv/bin/python tools/validate_rtl3_9_c3a_packed_source_service_terminal.py
.venv/bin/pytest -q tests/test_rtl3_9_c3a_packed_source_service_terminal.py
cd hardware/route_a/chisel
sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265a2PackReadPublicationSpec -- -z "continues the first post-R6 packed read"'
```

The selected Chisel/Verilator test passed on 2026-10-14: one test, zero
failures/errors, 781.062 seconds. This is functional protocol evidence only;
it establishes no timing, throughput, PPA, numeric RTL, controller/macro, or
complete-inference result.
