# RTL3.7-B — C2 terminal, release, and retire ordering

**Status:** `completed_testbench_only_terminal_release_retire_ordering`.

## Purpose

RTL3.7-A made the C2 packed read consume the exact eight-fragment packed object
written by R3, but intentionally left the C2 endpoint terminal and the
association-owner release observation tied off.  RTL3.7-B closes that one
cross-owner ordering edge in the bounded same-instance witness:

```text
C2 typed endpoint terminal (each fragment)
  -> real S2 terminal acceptance (each fragment)
  -> final terminal only
  -> existing packed-read association terminal
  -> existing association release observation
  -> testbench-only matching-retire gate
  -> existing R6 global drain / R5 durable reclaim / retire_ack
```

The endpoint emits an S2 terminal for every fragment because S2 owns the
checked fragment ordinal.  The bridge therefore forwards **every** exact
terminal to S2, but constructs exactly one `PackedReadTerminal` only from the
`last` terminal.  It retains the forwarded `PackedS2ReadWork` solely to carry
the already frozen identity, page, slot, generation, and delivery-context
association.

## Frozen testbench ordering rules

1. A terminal reaches the packed-read association only after the matching S2
   terminal has been accepted.
2. Intermediate fragment terminals cannot complete or release the association.
3. The final association terminal carries the captured work's exact
   transaction identity, page reference, S2 slot, source generation, and
   delivery-context reference; only terminal status comes from the endpoint.
4. The existing association release remains ready/valid-lossless and is held
   stable while its testbench observer is not ready.
5. A matching `RuntimeRetireRequest` cannot enter the existing R6 path until
   that release observation is accepted.  A missing or mismatched identity
   cannot pass the gate.
6. Once admitted, retirement, global drain, R5 invalidation-before-free, page
   reclaim, and `retire_ack` remain owned by the existing R6/R5 modules.  This
   bridge owns none of their state or acknowledgements.

## Scope boundary

This is a testbench-only association-to-retire dependency, not a new global
membership rule.  In particular, it does **not**:

- make C2 demand/publication/descriptor/lease grants autonomous;
- add C2 R1/R2 status to the existing R6 global status collector;
- add a production-top bridge or alter the production top's typed interfaces;
- replace C1 sidecar transport, static R4 packet/result fixtures, or the
  attention-partial producer boundary;
- select a controller, SRAM/HBM implementation, timing, PPA, or a numeric
  datapath.

The positive witness proves only that this bounded C2 association has released
before the corresponding already-existing R6 retirement transaction begins. It
does not prove production deadlock freedom or a complete C2 production
lifecycle.

## Historical provenance

The original `source_sha256` snapshot belongs to immutable closure commit
`295e254db24558607e139b68724fdea82579bcff`.  The validator replays it through
`git show` with
[`rtl3_7b_terminal_release_global_drain_historical_provenance.json`](rtl3_7b_terminal_release_global_drain_historical_provenance.json),
so later valid changes to the historical witness and living documentation do
not falsely invalidate this bounded evidence.  It does not certify C0--C3 or
physical realization.

## Directed evidence

`RouteARTL265eSameInstanceWitnessSpec` covers, in one Chisel instance:

1. a real R3 durable packed write and the RTL3.7-A shared functional object;
2. C2 eight-fragment typed read and C1 sidecar transport into real S2;
3. all S2 endpoint terminals, one final packed-read association terminal, and
   a ready-low-held association release observation;
4. matching retirement gated after release, followed by existing R6 global
   drain, R5 durable reclaim, and `retire_ack`.

The bridge itself asserts ready-low payload stability on work, S2-terminal,
association-terminal, release, and gated-retire carriers.  Mismatched endpoint
or retire identities do not handshake, so they cannot mutate S2, association,
or R6/R5 state through this test-only path.

## Evidence boundary and validation

This is pure Chisel/Scala and hash-bound Python manifest evidence: no model or
GPU, no cycle/timing/throughput/deadlock claim, no PPA claim, no RTL
correctness claim beyond the listed bounded tests, no production-top activation,
and no new A4 DSE.  It does not change pruning, admission, publication, R2
scheduling, source ownership, page size, M2/P3 organization, or atomic commit
semantics.

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265eSameInstanceWitnessSpec -- -z "composes real publication"'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265eSameInstanceWitnessSpec -- -z "reads the exact R3-durable"'
cd ../../..
.venv/bin/python tools/validate_rtl3_7b_terminal_release_global_drain.py
.venv/bin/python -m pytest -q tests/test_rtl3_7b_terminal_release_global_drain.py
```
