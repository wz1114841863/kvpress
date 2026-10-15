# RTL3.9-C4-P2 — selected accepted-event binding

## Status and selection

C4-P2 is complete as a narrow testbench-only binding.  It implements the
three outward C3b candidates selected by C4-P1:

1. the actual C0 R3-to-R6 `Pending -> Packed` authority acceptance;
2. the existing R4-origin / R6-outward attention terminal binding; and
3. the existing R6 outward retirement acknowledgement binding.

The complete machine-readable mapping is
[`rtl3_9_c4_p2_accepted_event_binding_manifest.json`](rtl3_9_c4_p2_accepted_event_binding_manifest.json).
The observer is zero-buffer and testbench-only.  Its event output and observed
carrier fire atomically; event-ready low applies verification backpressure and
cannot yield an event or carrier fire by itself.  It stores neither event nor
authority state.

For authority only, the event selection predicate is the pre-existing C0
`from=Pending, to=Packed` transition.  A different authority transition can
continue through the harness but cannot create this selected event.  This
does not add an R6 page/ordinal table or another authority owner.

## Explicit exclusions

The observer does not bind `page_free`, `descriptor_invalidate`, metadata
publication, S2 READY/availability, outer functional-memory traffic, or any
other P1 non-selected event.  In particular, `publication_commit` lacks the
immutable metadata member fields and `reclaim_complete` is not page-free.

The existing attention-terminal adapter is reused directly.  The selected
retire-ack observer preserves the exact existing RTL2.5.5 acknowledgement
field mapping while deliberately omitting the separate R5 release branch.

## Directed witness and validation

The C3b test stalls each selected event output before releasing it, then
checks the exact authority, terminal, and retirement acknowledgement fields.
It proves that no selected carrier can be accepted separately from its event.

```bash
.venv/bin/python tools/validate_rtl3_9_c3b_retirement_reclaim.py
.venv/bin/python tools/validate_rtl3_9_c4_p0_event_scoreboard_provenance.py
.venv/bin/python tools/validate_rtl3_9_c4_p1_c3b_event_provenance_matrix.py
.venv/bin/python tools/validate_rtl3_9_c4_p2_accepted_event_binding.py
.venv/bin/python -m pytest -q tests/test_rtl3_9_c4_p2_accepted_event_binding.py
cd hardware/route_a/chisel
sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265a2PackReadPublicationSpec -- -z "retires the first post-R6 packed read"'
git diff --check
```

The Chisel command is the functional same-instance witness; it must be run in
a visible tmux session because it is long-running.

## Boundary and remaining C4 work

C4-P2 does not create an all-event trace, replay events through the Python
oracle, or close legal-stall, stale/mismatch, fault, or reset coverage.  It
makes no production-top, controller/macro, HBM/SRAM, numeric/MAC/FP/exp,
timing, throughput, area, energy, PPA, model/GPU, or complete-inference claim.

C4-A has now bound the eligible R5 page-free release without inferring
descriptor-invalidate. C4-B next consumes the selected same-instance event
trace and establishes success plus bounded legal-stall replay. C4-C covers
stale/mismatch, fault, and reset; C4-D performs the bounded validation and
functional-subsystem completion review.
