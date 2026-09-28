# Route-A hardware evidence boundaries

## A4.12 metadata/control path

```text
arrival -> local/shared/staging logical queues -> metadata state
        -> RMW/scoreboard/commit service
```

The left side is frozen only as a logical contract.  CACTI can characterize
candidate SRAM arrays but cannot establish a real multi-port macro, a
scoreboard implementation, arbitration, clock frequency, sustained issue
rate, or commit timing.

The evidence chain must remain:

```text
frozen transaction/binding evidence
  -> declared cycle/service model (A4.12.2)
  -> macro access counts
  -> public-CACTI pJ/access proxy
  -> estimated dynamic energy
```

No stage may skip from transaction counts directly to measured energy.

## A4.13 payload path

Payload page IDs, offsets, bank indices, handles, physical page count, pending
KV placement, packed cold layout, transport, multi-source attention reads, and
softmax merge are outside A4.12's semantic entry widths.  A4.13 determines
those parameters; only then may metadata pointer-dependent widths be
back-filled without reopening metadata semantics.

## A4.14 final ledger and architecture-spec entry

A4.14.1 is the evidence-classified join point.  It reports common S2
source-buffer provision separately from Route-A-specific M2 provision and
workload-dependent payload/control activity.  Its positive omitted-cost budget
is a conditional margin:

```text
Route-A unestimated dynamic cost - Full-KV unestimated dynamic cost
    < reported omitted-cost budget
```

It is not an assertion that unestimated modules cost zero.  P3 staging macro
and dynamic access energy, M2 queue/staging accesses, packed sidecar/page
management, partial-state storage/merge arithmetic, controller/interconnect,
clock/wire/leakage and HBM physical area remain unestimated.  Payload and
metadata service coordinates have no shared timing/overlap model and must not
be summed.

The next artifact may freeze a reviewed architecture specification.  It may
not silently add an A4.14 DSE variant or begin RTL until that specification
defines the concrete implementation boundary and validation plan.

## Non-backtracking rule

An unfavorable metadata or payload cost enters the later partial/full ledger.
It does not authorize changing frozen pruning, admission, execution-granularity,
queue, scheduler, or commit semantics to improve a cost number.
