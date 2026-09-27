# A4.13.4 — page-source reuse and merge interface freeze

## Purpose

A4.13.4 freezes the payload datapath lifecycle required by the accepted
A4.13.3 fair legal-GQA comparison.  It does **not** select an HBM controller,
native transaction or burst, source-buffer macro/ports, attention lane timing,
area, energy, or RTL.  Its output is the action-level interface that A4.13.5
will map to a target memory-system profile.

The only inputs are the accepted A4.13.3 report (SHA-256
`fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1`) and
the three A4.13.1 external-storage manifests bound by that report.  The
workloads, Qwen3-8B dimensions, original mask, all-layer/all-KV-head coverage,
window 128, page 64, budget 512, P3 staging mapping, and event-level legal
four-query-head GQA groups remain fixed.

## Frozen page lifecycle

```text
packed page + position sidecar
        | FILL
        v
source buffer READY
        | multicast consume by query heads 0..3
        v
four partial attention states updated
        | hot / pending / packed online merge complete
        v
source buffer RELEASE
```

A packed page may transition from `READY` to `RELEASE` only after all four GQA
consumer completions for that page and their partial-state updates.  A4.13.1
has no physical timestamp or issue-order observation, so this is a correctness
and ownership rule, not a measured residency duration.

The Full-KV fair counterpart follows the same `FILL -> READY -> four-head
consume -> partial update -> RELEASE` lifecycle for each causally required
64-token page.  It has no position sidecar and one logical source, hence no
cross-source merge action.

## Source actions and internal units

| Source | Frozen actions |
|---|---|
| packed | page payload fill, 512-B sidecar fill, READY, four page-consume actions, partial updates, RELEASE |
| hot / pending | direct source delivery to the shared GQA fanout, four-head record consumption, partial updates, online merge |
| Full-KV | causal page payload fill, READY, four page-consume actions, partial updates, RELEASE |

`256 B` is an **internal interface/accounting beat** only.  A 32 KiB payload
page is 128 such beats and its 512-B sidecar is two.  This name intentionally
does not imply an HBM transaction, burst length, channel, interleave, or
controller command.  Those are target-profile choices for A4.13.5.

## GQA local state and partial state

One fetched page is shared only by the exact four verified members of one
GQA group.  It is retained from `READY` until all four consumers complete; it
cannot be reclaimed after only a subset of query heads has consumed it.

Each active GQA group requires four `(max, exp_sum, weighted-V)` partial
states.  The frozen interface is `4 * (128 + 2) * 4 = 2,080 B` under the
existing FP32 representation.  A4.13.4 places this logically as
**pipeline-local state** from source initialization through final online merge.
It is not a selected register file or SRAM macro.  Any later implementation
that spills it must explicitly account for the spill reads/writes in A4.13.5;
it may not treat the state as free.

The report records per trace phase and workload: partial-state initialization,
record updates, source finalization, and cross-source merge actions.  It does
not convert these into clocked operations or physical accesses.

## S1/S2 overlap condition

Let `T_fill(page)` include the packed payload and sidecar fill under a later
target profile, and let `T_consume(page)` include completion of the four
query-head consumers and their required partial-state updates.

```text
S1 (one 32 KiB buffer): T_page = T_fill + T_consume
S2 (two ping-pong buffers): steady-state T_page = max(T_fill, T_consume)
next-page fill is fully hidden iff T_consume(current) >= T_fill(next)
```

S2 still has warm-up and drain.  The condition is symbolic in A4.13.4 because
no HBM service time or consumer throughput has been selected.  A4.13.5 will
instantiate it using one primary and one one-factor sensitivity profile.

## Exit boundary

Success requires exact A4.13.3 input binding; fair Full-KV/Route-A GQA group
identity; page/beat conservation; source lifecycle, release, partial-state and
merge action accounting; and no unregistered source-buffer candidate.  The
stage makes no physical HBM, timing, bandwidth, utilization, energy, area,
speedup, net-benefit, architecture-spec, or RTL claim.

