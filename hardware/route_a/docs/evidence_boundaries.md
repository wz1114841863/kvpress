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

## Non-backtracking rule

An unfavorable metadata or payload cost enters the later partial/full ledger.
It does not authorize changing frozen pruning, admission, execution-granularity,
queue, scheduler, or commit semantics to improve a cost number.
