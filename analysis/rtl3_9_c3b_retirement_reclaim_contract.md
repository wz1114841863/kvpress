# RTL3.9-C3b — packed first-use retirement and reclaim

**Status:** `complete_functional_retirement_reclaim_witness`.

C3b continues the same B3/C0/C1/C2/C3a packed first-use witness only after
the one matching R6 attention terminal has been accepted. It composes the
existing R6 lifecycle adapter, production-shaped component-status collector,
R5 page manager, R2/R1 typed descriptor-maintenance path, and functional
external-memory response boundary.

```text
C3a one accepted R6 terminal
  -> exact runtime-retire request to R6
  -> R2-payload/R2-descriptor/R1/R3/S2/direct/merge drain collection
  -> R6 reclaim permit -> R5 descriptor invalidate write
  -> matching R1 terminal -> R5 durable page free / reclaim complete
  -> final R2-descriptor + R1 drains and R5 drain
  -> one matching R6 session-retire acknowledgement
```

The harness selects the collector only in the C3b retirement mode. The
ordinary R6 initialization facts are accepted through the existing predecessor
fixture before that mode begins; masking collector inputs before C3b prevents
an earlier init-level status from occupying its one-record staging latch.
Once enabled, its source order and final-pass R1/R2-descriptor replay are the
unchanged production collector behavior. The direct-pending drained status is
an explicit outer functional environment because this packed-only witness does
not instantiate a direct-pending data source; it supplies neither page data,
source selection, authority, nor a second retire/reclaim owner.

R6 remains the sole lifecycle/retirement authority. R5 accepts only R6's
retirement permit and performs its existing descriptor invalidation. R2/R1
continue to own the typed maintenance request/response association. R5 may
free a page only after the matching durable terminal, and R6 may acknowledge
retirement only after reclaim completion and final drain membership.

The external memory response remains a functional outer environment. This
does not implement or claim an HBM controller, SRAM macro, attention MAC,
numeric/FP/exp pipeline, schedule, timing, throughput, area, energy, PPA, or
complete LLM inference.

## Validation

```bash
.venv/bin/python tools/validate_rtl3_9_c3b_retirement_reclaim.py
.venv/bin/pytest -q tests/test_rtl3_9_c3b_retirement_reclaim.py
cd hardware/route_a/chisel
sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265a2PackReadPublicationSpec -- -z "retires the first post-R6 packed read"'
```

The selected Chisel/Verilator witness passed on 2026-10-14: one test, zero
failures/errors, 729.721 seconds (743 seconds total command time). It proves
the declared functional protocol sequence only.
