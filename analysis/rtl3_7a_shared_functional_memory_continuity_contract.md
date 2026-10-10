# RTL3.7-A — shared functional-memory object continuity

**Status:** `completed_testbench_only_shared_functional_memory_continuity`.

## Purpose

RTL3.7-A closes one narrow gap found by RTL3 completion cross-owner review 02:
the C2 packed-source read must consume the exact packed object made durable by
the real R3 payload write, rather than a separately injected source-read
payload fixture.

The closure shares one host-side `RouteAFunctionalMemoryStore` between two
independently reset `RouteAFunctionalMemoryEnvironment` endpoints in the
existing same-instance witness:

```text
R3 real pack_read -> R2/R1 -> P3 -> packed write durable
  -> testbench-only shared functional object store
  -> C2 typed packed source read -> S2 payload deposition
```

The test derives the C2 descriptor payload handle from the accepted R3
packed-write observation.  It then proves that the eight delivered C2 payload
fragments equal the one accepted R3 durable payload object.

## Functional-store key refinement

`CoreMemoryRequest.address_ref` is intentionally an opaque logical carrier,
not a selected physical/HBM address.  In the existing functional testbench
environment, a packed payload write (eight fragments) and a descriptor update
(one fragment) can therefore use the same opaque `address_ref`.  RTL3.7-A
prevents a false host-side alias by keying the **testbench-only** store by:

```text
(address_ref, expected_fragment_count)
```

This is not a new R1 port field, a physical address encoding, a memory-map
selection, or a claim that fragment count is a deployed address-space tag. It
only preserves the existing accepted R1 transaction granularity so that the
functional reference model does not overwrite an eight-fragment payload with
a one-fragment descriptor line at the same opaque handle.

## What remains deliberately open

- C2 demand/publication/descriptor/lease grants remain verification facts;
  RTL3.7-A does not make R3/R5 produce them autonomously.
- The C2 source endpoint remains a separate test-harness R1 port with its own
  queues and reset/init state. Sharing host-side object contents is neither a
  common deployed controller nor common HBM arbitration.
- C1 sidecar transport remains its declared fixture transport.
- RTL3.6-B's static packet and R4 terminal fixtures remain static; no live
  attention partial producer, numeric RTL, or R4 functional datapath is added.
- Terminal-to-release completion and global R6 drain/reclaim association remain
  RTL3.7-B work.

## Directed evidence

The new same-instance Chisel test checks all of the following in one bounded
transaction:

1. R3 reads the pending eight-fragment object through the functional R1
   environment and makes one successful packed durable write.
2. An R5 descriptor durability write at the same opaque handle cannot overwrite
   that payload object in the testbench store.
3. C2 receives the actual R3 durable payload handle, reads the exact eight
   fragments from the shared store, fills S2, and continues through the
   existing static terminal / R6 / R5 retirement witness.
4. A direct unit test proves payload and descriptor objects remain separate
   only by their existing expected-fragment cardinality in the functional
   store.

## Evidence boundary

This is pure Chisel/Scala and Python manifest evidence: no model/GPU, no
cycle/timing/throughput/deadlock claim, no PPA claim, no production-top
activation, no native-HBM/controller/macro implementation, no numeric/FP/MAC
implementation, and no new A4 DSE. It does not change pruning, admission,
publication, R2 scheduling, source ownership, page size, M2/P3 organization,
or atomic-commit semantics.

## Validation

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl3.RouteAFunctionalMemoryEnvironmentSpec'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265eSameInstanceWitnessSpec -- -z "reads the exact R3-durable"'
cd ../../..
.venv/bin/python tools/validate_rtl3_7a_shared_functional_memory_continuity.py
.venv/bin/python -m pytest -q tests/test_rtl3_7a_shared_functional_memory_continuity.py
```
