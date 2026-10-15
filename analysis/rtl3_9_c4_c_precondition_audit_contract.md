# RTL3.9-C4-C — negative-event precondition audit

## Status

C4-C's precondition audit is complete and authorizes a narrow same-instance
negative witness. It does not implement C4-C yet. The machine-readable case
matrix is
[`rtl3_9_c4_c_precondition_audit.json`](rtl3_9_c4_c_precondition_audit.json).

## Available negative ingress and event expectations

The C3b harness already exposes stale R1 responses at the external functional
memory boundary, stale/mismatched R4 result or numeric-fault inputs at the
named outer R4 boundary, matching R4 numeric fault, reset, and all four
selected C4 event outputs. No additional event carrier, owner, retry, or
fallback is needed.

An event trace must be judged against an allowed prefix and forbidden suffix.
For stale R1 or R4 mismatch, the already-accepted `authority_transition` is a
legal prefix because it precedes the bad input; terminal, page-free, and
retire acknowledgement remain forbidden. A matching R4 numeric fault instead
permits one fault-valued terminal after authority, but forbids a later success
terminal, page-free, and retire acknowledgement. Reset while an event is
held ready-low permits no post-reset event without fresh initialization and a
new accepted path.

R5 `reclaim_complete` is not an event source, and the historical
descriptor-invalidate constants remain excluded. The checks must use actual
fires, not `valid` levels.

## C4-C implementation boundary

C4-C may add only testbench/host replay checks to the existing C3b harness:
negative ingress acceptance, selected-event fires, and the stated C0--C3b
boundaries. It may retain the outer functional memory, partial provider, and
R4 reference environments. It may not claim a production controller/macro,
HBM/SRAM, attention MAC, FP/exp pipeline, timing, throughput, area, energy,
PPA, model/GPU, or complete inference.
