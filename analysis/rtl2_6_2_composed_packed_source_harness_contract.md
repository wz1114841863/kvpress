# RTL2.6.2a — composed packed-source terminal harness

**Status:** `implemented_narrow_test_only_composition_not_full_retained_transaction`.

This is the first executable portion of RTL2.6.2's single-instance composed
transaction harness. It covers this real owner chain in one Chisel
simulation:

```text
verification S2 fill ingress
  -> real S2 READY observation
  -> test-only observation seam into packet availability
  -> four real R4 consumer commits
  -> real S2 source release
  -> real R6 merge request
  -> real R4/R6 numeric-fault terminal
```

The seam copies only S2's public identity and source-instance observations.
It does not create a source plan, delivery context, payload-page association,
or authority fact. Packet payload/header fragments and the S2 fill remain
explicit verification ingress. This is therefore **not** an implementation of
a production `R3/R5 publication -> PackedS2ReadWork -> S2` bridge.

The directed cases cover a matching packed source and a mismatched source
generation. They establish owner-local `READY`, four consumer commits,
release, merge, and one fault terminal; they make no numeric datapath, timing,
throughput, PPA, model/GPU, or full retained-transaction claim.

Still open for the complete RTL2.6.2 witness are the real R3/R5 publication
segment, its explicit test-only association into this S2 ingress, scoreboard
event emission for all fourteen schema events, retirement/reclaim, and the
full success/fault/stall transcript. A production bridge remains a separate
architecture decision and is not introduced here.
