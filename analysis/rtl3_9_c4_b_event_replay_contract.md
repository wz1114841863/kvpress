# RTL3.9-C4-B — accepted-event replay and bounded legal backpressure

## Status

C4-B is complete in the C3b testbench. Its directed Chisel witness compiled
the host replay oracle and passed the one C3b success-path test with the four
bounded stalls. It consumes only the four already-authorized event
observations:

```text
R3 -> R6 Pending-to-Packed authority acceptance
  -> R4/R6 attention terminal
  -> R5 old-PageRef page-free observation
  -> R6 retire acknowledgement
```

The host-side replay oracle has no Chisel state, event FIFO, owner, or
production-top role. It appends an event record only after the corresponding
event/output handshake has taken its clock edge, then requires exactly one
record of each class, in the stated order, with their immutable fields and
terminal/retire identity relation preserved.

## Bounded legal backpressure

The same C3b success witness holds each of the four selected event outputs
with `ready=0` for exactly two cycles. During each hold, the event remains
valid while its named observed carrier cannot fire; release after the two
cycles causes one atomic acceptance. The test does not infer an event from
R5 `reclaim_complete`, a descriptor line, a READY level, or outer functional
memory traffic.

`page_free` remains a post-durability R5 observation: its event backpressure
does not redefine the owner-local `reclaim_complete` level. The replay order
therefore describes accepted testbench observations, not an additional R5/R6
retirement condition.

## Boundaries and next phase

This is a success-path and finite legal-stall replay only. It does not cover
stale/mismatch, numeric fault, reset, a persistent cross-run trace format,
production scoreboard integration, HBM/SRAM, numeric/MAC/FP/exp, timing,
throughput, area, energy, PPA, model/GPU, or complete inference. Those
negative scenarios remain C4-C; C4-D remains validation and bounded
functional-subsystem completion review.
