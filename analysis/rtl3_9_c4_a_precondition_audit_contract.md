# RTL3.9-C4-A — event-capture precondition audit

## Status

C4-A's precondition audit is complete; C4-A capture itself is not. This audit
restores the planned C4-A/B/C/D structure after the narrow C4-P2 precursor.
P2 bound authority transition, terminal, and retire acknowledgement, but it
did not close C4-A and does not authorize replay.

The machine-readable result is
[`rtl3_9_c4_a_precondition_audit.json`](rtl3_9_c4_a_precondition_audit.json).

## Per-event result

`attention_terminal` and `retire_ack` remain eligible through their exact
outward accepted carriers already bound by C4-P2. `page_free` is also eligible:
R5's `allocator_release_out.fire` carries the exact old `PageRef` only after
the matching durable invalidation terminal. The live C3b harness currently
consumes that carrier with `ready := true`; C4-A may replace only that
testbench sink with the existing zero-buffer reclaim adapter.

`descriptor_invalidate` is not eligible. The release carrier contains the old
page reference, but not `descriptor_operation` or `delivery_context_ref`.
The historical RTL2.5.5 adapter represents those two fields with fixed
schema-level constants. Under the C4-P1 rule that every captured field must
come from the same accepted owner carrier, C4-A must not relabel those
constants as owner-produced fields. A descriptor line, later
`reclaim_complete`, outer functional-memory traffic, or private R5 state is
not a substitute.

## Consequence and remaining phases

C4-A may next bind the eligible R5 `page_free` observation in the C3b harness
and retain the already-bound terminal/retire observations. It must leave
`descriptor_invalidate` excluded unless a future separately audited carrier
contains all of its fields. It may not infer an event or add an R5/R6 owner.

- **C4-B** is the subsequent success and bounded legal-backpressure event
  replay phase; it is not authorized until the eligible C4-A capture is
  implemented and witnessed.
- **C4-C** separately covers stale/mismatch, numeric fault, and reset without
  fabricated events or violations of no-early-read, no-repeat,
  one-terminal, or reclaim-before-free boundaries.
- **C4-D** updates contracts and runs directed Python/Chisel validation before
  a bounded RTL3 functional-subsystem completion review.

This audit remains testbench/functional evidence only. It makes no
production-top, controller/macro, HBM/SRAM, numeric/MAC/FP/exp, timing,
throughput, area, energy, PPA, model/GPU, or complete-inference claim.
