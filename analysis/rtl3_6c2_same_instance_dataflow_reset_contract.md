# RTL3.6-C2 — same-instance dataflow and reset-epoch composition

**Status:** `completed_testbench_only_composed_dataflow_reset_epoch_witness`.

RTL3.6-C2 composes the previously separate functional witnesses in one Chisel
instance.  It keeps the existing real R3 publication child, R6 terminal and
retirement owner, and same-child R5 durable reclaim.  It replaces that
witness's manual S2 payload/terminal ingress with the RTL3.2 association
owner, typed R2/R1 packed-read chain, endpoint deposition, and RTL3.6-C1
sidecar fixture transport.

## Bound witness

```text
real R3 pack-read / payload-write / descriptor durability / publication
  -> real publication + pending-to-packed observation
  -> verification-only identity/page/slot association
  -> S2 service request
  -> RTL3.2 association owner + exact allocation acknowledgement
  -> typed R2/R1 packed read
  -> endpoint payload deposition + C1 handle-keyed sidecar fixture
  -> S2 READY
  -> static RTL3.5-B packet fixture / structural R4 acceptance
  -> static RTL3.4-B terminal fixture
  -> real R6 four-consumer terminal / retirement
  -> same R5 durable invalidation/reclaim
  -> retire_ack
```

The C2 source read has its own test-harness R1 external port.  This is a
functional test composition boundary, not a second deployed memory path: no
production top is changed, and it does not select a controller, arbitration,
clock, or shared physical HBM interface.  The testbench still supplies only
the frozen verification association plus immutable packed-demand,
publication-authorization, descriptor-location, and S2-lease facts.  It does
not select an R3/R5 scheduler, reconstruct a descriptor, infer payload or
sidecar data, alter publication, or create authority.

## Reset-epoch witness

The composed harness destructively resets both R1 wrappers before a fresh
transaction.  A stale C2 external response has no matching live identity:
R1 may consume it to drain the environment carrier, but suppresses it from
the core.  Only after both new external `init_ack` handshakes can the fresh
publication-to-`retire_ack` witness restart.  This is reset stale-state
exclusion, not a reset-sequence, CDC, or latency claim.

## Assertions exercised

- Real publication remains prior to the verification-only S2 service join.
- The typed `S2Packed` read carries the frozen published-metadata eligibility
  bit; a R3 `pack_read` eligibility snapshot is not reused for that class.
- C1 sidecar data is emitted only from the accepted allocation's copied
  handle/count and exact S2 filling observation; it is not payload-derived.
- S2 becomes READY only after complete endpoint payload delivery and sidecar
  completion.
- The static terminal is withheld until all four fixture packets are accepted
  through the structural R4 boundary; R6 alone owns group terminal and
  retirement; existing R5 owns durable invalidation/reclaim.
- An old-epoch response cannot become a live core response or authorize a
  post-reset transaction.

## Evidence boundary

This is bounded no-model Chisel evidence.  It is not production-top
activation, live Python/Chisel co-simulation, a common deployed R1/HBM
controller, a numeric/FP/MAC/RoPE implementation, timing, throughput,
deadlock, area, energy, PPA, model/GPU result, or new A4 DSE.  It does not
turn testbench verification inputs into architecture-owned scheduling or
memory-realization facts.

## Validation

```bash
cd hardware/route_a/chisel
sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265eSameInstanceWitnessSpec -- -z "composes real publication"'
sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265eSameInstanceWitnessSpec -- -z "rejects a stale C2 response"'
cd ../../..
.venv/bin/python tools/validate_rtl3_6c2_same_instance_dataflow_reset.py
```
