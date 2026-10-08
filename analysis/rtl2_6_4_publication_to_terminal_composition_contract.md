# RTL2.6.4 — publication-to-terminal composition witness

**Status:** `implemented_single_instance_test_only_partial_retained_witness`.

RTL2.6.4 is the first same-instance composition that crosses the former
publication/S2 gap:

```text
real R3/R5/R2/R1 publication
  -> real R3 publication observation + pending-to-packed authority
  -> explicit RTL2.6.3 verification association
  -> real S2 service / READY
  -> four real R4 consumer commits
  -> real S2 release
  -> real R6 merge request
  -> real R4/R6 numeric-fault terminal
```

The R3/R5 child, association adapter, and S2/source/R4/R6 child are all
instantiated in one Chisel simulation. The only cross-child join is the
explicit test-only association required because publication does not carry an
attention request identity, S2 slot, or source generation. Its page reference,
transaction-group tag, valid-record count, and authority transition are checked
before S2 service begins.

This is not a production-top bridge, source scheduler, numeric merge, HBM/SRAM
controller, timing/throughput/PPA result, model/GPU experiment, or full RTL2.6
PASS. It exercises the numeric-fault terminal only. Still open are the success
terminal branch, R6 retirement and R5 reclaim in this same instance, complete
14-event capture/replay, stale-response and legal-stall variants of the full
composition, and the final completion review.
