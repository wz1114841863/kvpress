# RTL3.9-C4-D — functional-subsystem completion review

## Status

C4-D is complete as a bounded review. Its directed Chisel validation passed
the C3b success/replay witness and all three C4-C negative witnesses. It
reviews the already-closed C0--C3b and C4-A/B/C evidence; it does not modify
an RTL owner, datapath, authority state, event carrier, or outer environment.

## Required evidence reconciliation

The review requires one owner-correct functional instance to retain all of the
following evidence without inventing an event or treating a testbench default
as an owner-produced fact:

| Criterion | Required prior evidence |
|---|---|
| One publication and authority boundary | B3 plus C0 actual R6 acceptance |
| No early packed first use | C0/C1 and C2 owner-checked association through S2 READY |
| Source service and one terminal | C3a four-consumer packed path and named outer partial/R4 environments |
| Reclaim before free and one retire acknowledgement | C3b functional retirement/reclaim path |
| Accepted-event provenance and success ordering | C4-P0/P1/P2, C4-A, and C4-B |
| Rejected stale/mismatch/fault/reset behavior | C4-C allowed-prefix/forbidden-suffix witnesses |

The directed validation ran the existing C3b C4-B success/replay witness and
all three C4-C negative witnesses from the current checkout. The review
classifies the declared subsystem as functionally closed only because the
declared no-model preflights also passed.

## Non-claims

Any C4-D conclusion remains limited to functional owner/protocol closure of
the declared subsystem. Functional memory, partial provider, and R4 reference
remain named outer environments. This review does not establish a production
memory controller or macro, HBM/SRAM behavior, attention MAC, FP/exp pipeline,
clocking, timing, throughput, area, energy, PPA, model/GPU result, or complete
LLM inference.
