# RTL2.6.5e — same-instance real-owner retained-path witness

**Status:** `implemented_directed_tested_no_model_functional_completion`.

This testbench-only witness closes the exact gap recorded by RTL2.6.5d. In one
Chisel instance it composes:

```text
R3 retained member pack_read -> P3 -> payload/descriptor durability
  -> atomic publication / pending-to-packed observation
  -> explicit verification association -> real S2 service and READY
  -> four packed GQA commits -> R4 result-stub terminal -> R6
  -> matching environment retire -> same R5 durable reclaim
  -> R2/R1 invalidate terminal -> retire_ack
```

The R3/R5/R2/R1 publication child is the existing RTL2.6.5a.2 path. Its R5
reclaim permit, completion, and drain/status hooks are exposed only to this
test harness, allowing R6 to reclaim the exact page allocated and published
by that same child. The pre-existing publication-to-S2 association remains
explicit and test-only; it supplies neither a production source scheduler nor
an authority fact.

The directed Chisel witness proves a successful R4 result-stub terminal and
subsequent matching retirement/reclaim. It also attempts a stale page
association before the matching association (rejected), and holds the terminal
consumer ready low for one bounded cycle while identity remains stable. The
existing RTL2.6.5c accepted-carrier trace/replay contributes the all-fourteen
event vocabulary plus success, fault, stale-response, and bounded ready-low
oracle cases. Together these close RTL2 only as
`testbench_only_functional_transaction_dataflow`.

The S2 payload and sidecar arrival in this witness remain the existing,
explicitly owned **verification** S2-fill ingress. They do not select a
packed-read scheduler, create a production R3/R5-to-S2 producer bridge, or
realize HBM/SRAM storage. Likewise, RTL2.6.5c remains the declared
event-level testbench adapter: this directed Chisel test does not export a
waveform trace into Python. The constrained review composes this real-owner
path evidence with that frozen accepted-carrier contract, rather than claiming
cycle-correlated trace extraction.

This is not a production-top integration, physical memory realization, R4
numeric implementation, controller/macro selection, timing, throughput,
deadlock-freedom, PPA, model/GPU, or A4 DSE result.
