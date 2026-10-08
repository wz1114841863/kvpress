# RTL2.6.5b — terminal-to-reclaim composition

**Status:** `implemented_directed_tested_no_model`.

RTL2.6.5b composes existing owners in one Chisel instance:

```text
S2 READY -> four packed-source consumer commits -> R4 numeric-fault terminal
  -> accepted R6 attention terminal
  -> matching environment runtime-retire request
  -> existing R6 fixed-membership drain and reclaim permit
  -> R5 descriptor-reclaim candidate -> R2 -> R1
  -> matching durable invalidate terminal -> R5 reclaim_complete
  -> R6 final drain pass -> retire_ack
```

The test-only `RouteATerminalRetireAssociation` is intentionally narrow: it
records an accepted existing R6 attention terminal and forwards an
environment-originated `runtime_retire_req` only when its identity matches.
It does **not** claim that attention terminal behavior autonomously initiates
retirement, nor does it add a production lifecycle policy, source scheduler,
or authority owner.

R3 and direct-pending retain their explicit deferred-owner drain facts in this
slice. R1, both R2 drain partitions, R5, S2, and R4 supply the composition's
status facts through their actual instantiated owner outputs and the existing
fixed-membership status collector. R5 alone produces the reclaim candidate,
and only the matching successful R1 terminal produces its existing durable
invalidation/free transition and `reclaim_complete`.

Directed tests cover a matching fault terminal followed by same-identity
retirement/reclaim to one `retire_ack`, reject a mismatched runtime-retire
identity, and show that an R1 reclaim terminal fault leaves retirement
incomplete. These are no-model, no-GPU functional protocol tests only. They
do not establish production R3/R5-to-S2 realization, full retained-path event
capture/replay, numeric RTL, deadlock freedom, timing, throughput, HBM/SRAM
implementation, or PPA. RTL2.6.5c--d remain open.
