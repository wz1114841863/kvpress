# RTL2.6.5a.2 — R3 pack-read to P3 composition

**Status:** `implemented_directed_tested_no_model`.

This narrow RTL2.6.5a.2 witness activates no new producer and does not choose
a pack-read issue schedule. It composes one existing R3 immutable member-work
carrier with the already frozen typed read and write paths:

```text
R3 admitted member + pack_read_work
  -> read-issue adapter -> unified delivery-context allocation
  -> existing R2 read ingress / R1
  -> registry-resolved P3 pack-read endpoint -> P3
  -> existing R3 packed-write candidate
  -> existing R2 write ingress / R1 -> R5 descriptor durability
  -> existing M2 member/publication protocol
```

The same R3 instance owns both the eight-fragment `pack_read` and its later
packed-write candidate. The unified bridge retains one registry association
across a write request and all associated write-data carriers, and waits for
terminal release only after the final data carrier. This makes the existing R1
transaction granularity explicit; it is not a FIFO, credit, arbitration,
retry, scheduling, controller, or service-rate change. Read and write still
enter R2 through their distinct existing ingress merges.

Directed Chisel evidence in `RouteARTL265a2PackReadPublicationSpec` covers:

- matching retained member -> exactly one eight-fragment R1 read -> P3;
- P3 COMPLETE before its actual packed write, R5 descriptor write, exact M2
  member responses, and atomic publication acknowledgement;
- stale response identity makes no P3 deposit; and
- matching read terminal fault leaves P3 faulted and emits neither M2 member
  work nor a publication candidate.

The test contains no model/GPU invocation and no numerical merge, timing,
throughput, HBM/controller, SRAM/macro, area, energy, PPA, or RTL-correctness
claim. It does not select whether later retained members issue serially or
concurrently, create a production R3/R5-to-S2 bridge, connect retirement or
reclaim, or capture/replay the fourteen-event scoreboard trace. Those remain
RTL2.6.5b--d work.
