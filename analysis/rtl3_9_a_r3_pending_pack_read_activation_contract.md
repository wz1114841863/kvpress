# RTL3.9-A — R3 pending pack-read functional activation

**Status:** `complete_functional_pending_to_p3_fill_activation`.

RTL3.9-A activates the A0/A1-authorized path from an R3 immutable member and
its exact pending binding, through R3-owned `P3PackReadWork` and
`P3SidecarBind`, then the existing checked R3-to-R2-to-R1 typed endpoint path.
The composition top only feeds R3-owned carriers into existing checked inputs.

R3 emits at most one eight-fragment work item per bound member. Its local
submission sequence advances only on work acceptance; it is not an R2 winner,
global queue, physical FIFO, service-rate, or permanent scheduling rule. The
functional baseline has one active member per P3 stage in immutable ordinal
order. Any concurrency or reorder expansion needs a separate R2/R3 closure.

The sidecar comes from the same member ledger. A reservation starts after work
acceptance and ends after matching payload terminal plus sidecar acceptance, or
a matching fault. During it, hot P3 payload and sidecar offers must be invalid.
Both mergers fail closed on simultaneous hot/pack offers; neither has priority.

`p3_packed_write` remains inert. This does not establish durability,
publication, authority handoff, direct/S2 replacement, numeric RTL,
HBM/SRAM/controller realization, timing, throughput, PPA/DC, model/GPU
behavior, or complete inference.

## No-model verification

```bash
cd hardware/route_a/chisel
sbt -batch 'Test / compile'
sbt -batch 'testOnly kvpress.routea.rtl3.RouteARTL39AMaterializationSpec'
sbt -batch 'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec'
```

Evidence is directed functional control/dataflow only: no model/GPU,
cycle/timing/throughput/deadlock, numeric-RTL correctness, PPA, or A4 DSE claim.
