# RTL2.3.3 — R2-owned dual logical ingress

**Status:** implemented and directed tested.  This closure adds an explicit
`read_candidate_in` to `route_a_core_side_arbiter`.  It ensures that a future
read ingress competes with the existing candidate ingress **inside R2**, never
through a top-level mux or source-owner arbitration.

The machine-readable companion is
[`rtl2_3_3_r2_dual_ingress_manifest.json`](rtl2_3_3_r2_dual_ingress_manifest.json).

## Exact behavior

For each cycle in which one or both logical ingress carriers are valid, R2
first applies its existing per-candidate admission conditions: drain rule,
no R1 request stall, frozen predicate eligibility, available candidate slot,
and class capacity.  If both are acceptable, R2 accepts exactly the lower
existing `(arrival_ordinal, candidate_id)` record.  The accepted record enters
the same existing R2 candidate storage; no duplicate FIFO, credit state,
read cursor, request-ID state, response state, or scheduler is created.

The original `candidate_in` port remains source-compatible with RTL1/RTL2.1
write-path harnesses.  `read_candidate_in` has the same protocol backpressure
rule and a ready-low stability assertion.  Existing R2 issue selection still
owns the frozen read rotation and advances it only on R1 acceptance.

## Production-top boundary

The production top instantiates neither the RTL2.3.1 adapter nor RTL2.3.2
read allocation bridge/merge.  It ties `arbiter.read_candidate_in` inactive
with a named carrier.  Consequently this is a real R2 ownership closure but
not a live read-source activation:

- no R3/R5 read descriptor/candidate can reach R2;
- no allocation competes with the existing write bridge for the sole registry;
- no R1 read request can be launched by this new ingress;
- no response can reach the typed read router or P3/S2/direct endpoint; and
- no source-deliverable, GQA, R4, authority, lifecycle, or scoreboard event is
  produced by this change.

This deliberate inactive binding is safer than constructing a top-side source
or a temporary registry mux.  A future integration closure must name one
shared registry-allocation composition owner and connect the three already
closed R3/R5 lanes without changing their immutable context fields.

## Directed evidence

The new focused R2 test supplies an existing ingress candidate and a lower
ordinal `pack_read` candidate simultaneously.  It proves that only the latter
is accepted, that the former receives no false ready, and that the selected
read request remains stable under R1 `ready` low.  Structural-top elaboration
checks the newly explicit tied-inactive port.

Run from `hardware/route_a/chisel`:

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  "testOnly kvpress.routea.r2.RouteACoreSideArbiterSpec -- -z \"accepts simultaneous logical read ingress\""
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  "testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec -- -z \"elaborate every frozen hierarchy module\""
```

Passing evidence is synthesizable functional-control/ownership evidence only:
no model/GPU, cycle, latency, throughput, PPA, physical-memory, controller,
numeric RTL, deadlock-freedom, or new A4 DSE claim.

Recorded result: `Test / compile` passed; the focused R2 dual-ingress test
passed 1/1; and focused structural-top elaboration passed 1/1.
