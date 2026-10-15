# RTL3.9-C4-D — functional-subsystem completion review

## Decision

**Complete at the declared functional-subsystem scope.** C4-D reconciles the
existing C0--C3b and C4-A/B/C evidence and finds one owner-correct packed
first-use path, its accepted-event observations, and its stated negative
boundaries closed. This is an RTL3 functional-subsystem conclusion only; it is
not a physical-realization, numerical-datapath, performance, PPA, model/GPU,
or complete-inference conclusion.

## Evidence reviewed

| Review criterion | Functional evidence |
|---|---|
| Unique publication and authority | B3's immutable publication provenance plus C0's R3-led all-member R6 acceptance |
| No early first use through S2 READY | C0/C1/C2 composed association, visible descriptor, typed payload and sidecar path |
| Source service and terminal | C3a's S2 service, four packed consumer commits, named functional partial/R4 environments, and one R6 terminal |
| Reclaim before free and one acknowledgement | C3b's retirement, durable R5 invalidation/page-free, final drains, and R6 retire acknowledgement |
| Success event ordering | C4-P0/P1/P2 and C4-A/B exact accepted-event provenance plus two-cycle legal stalls |
| Negative event boundaries | C4-C stale R1, stale/mismatched R4, matching numeric fault, and held-event reset witnesses |

The C4-D directed Chisel command passed the C3b success/replay witness (one
test) followed by all C4-C negative witnesses (three tests), with SBT exit
code 0 on 2026-10-15. Its no-model review set also passed 15 validators and
16 targeted Python tests from the current checkout.

## Retained boundary

The functional external-memory responder, functional partial provider, and R4
reference remain explicit outer environments. The review preserves the frozen
KVzap mask, admission, 64-token page, M2/P3 organization, S2 mapping, legal
GQA, queue/scheduler, and single atomic-publication semantics. It adds no
controller/macro, HBM/SRAM, attention MAC, FP/exp pipeline, clock/timing,
throughput, area, energy, PPA, fallback, or second owner.

The next work is a separately authorized synthesis-realization partition and
eligibility plan. It must not treat this functional review as physical or
performance evidence.
