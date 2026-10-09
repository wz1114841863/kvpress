# RTL3.4-A — R4 per-consumer result association

**Status:** `complete_consumer_result_association_control_closure_pre_rtl3_4b_numeric_provider`.

RTL3.4-A closes the association that was absent from the pre-RTL3.4 R4
boundary: one GQA group has four query-head consumers, while each observable
R4 normalized result is only one 128-lane (4,096-bit) consumer result.  It
does not implement numerical merge arithmetic.  The follow-on functional
provider remains RTL3.4-B.

## Frozen association

```text
all selected source owners complete four consumer partial updates
  -> one R6 group-level merge-ready(identity, source_presence)
  -> R6 serial functional-baseline work, consumer_id = 0, 1, 2, 3
  -> one R4 result XOR numeric-fault carrying the same identity + consumer_id
  -> R6 aggregates to its sole group-level outward terminal
```

`consumer_id` is now mandatory on these logical carriers:

| Carrier | Producer | Consumer | Association rule |
|---|---|---|---|
| `MergeRequest` | R6 | R4 boundary / future functional provider | exact live transaction identity, nonempty source-presence mask, one consumer ID `0..3` |
| `R4ResultStub` | replaceable test or future functional provider | R4 boundary | exact active request identity and consumer ID; value is that consumer's 4,096-bit normalized result |
| `R4NumericFault` | replaceable test or future functional provider | R4 boundary | exact active request identity and consumer ID; no normalized value |
| `MergeTerminalResponse` | R4 boundary | R6 | exact active request identity and consumer ID; R6 alone turns it into group terminal state |

The existing `R6MergeReady` remains group-level.  It is legal only after the
selected source set has finished all four GQA consumer partial updates, so this
patch does not alter source release or the pre-existing four-consumer
completion rule.

## Aggregation and fault behavior

R6 has one active group-level merge sequence at a time.  The fixed `0 -> 1 ->
2 -> 3` issue sequence is a conservative functional baseline required by the
current single-active R4 boundary.  It is an association/ownership ordering,
not a new source scheduler, PE schedule, service-rate guarantee, or permanent
throughput choice.

- A group success is legal only after matching success responses for all four
  consumer IDs in that order.  R6 then emits exactly one group-level outward
  success terminal.
- A matching numeric fault is fail-closed: R6 emits exactly one group-level
  fault terminal without inventing results for the unserved consumers.  This
  preserves the frozen no-retry/no-fallback numeric-fault rule.
- A stale identity, duplicate terminal, invalid consumer ID, or mismatched
  consumer ID is not accepted and cannot mutate R4/R6 active state.

Thus the 4,096-bit normalized payload is never silently treated as a packed
four-consumer group result.  The R6 outward attention terminal remains status
only; R6 does not become a numeric data owner.

## Scope and evidence boundary

This patch modifies only logical interface association and control sequencing
in `route_a_lifecycle_adapter` and `route_a_merge_boundary`, plus their
test-only stub path.  It does not activate a production R4 provider or alter
the frozen source packet/header format, canonical source order, GQA legality,
source completion, admission, publication, R1/R2 scheduling, memory
realization, page organization, or R6 retirement semantics.

It selects no exp implementation, FP pipeline, internal precision, attention
MAC, latency, throughput, area, energy, PPA, model/GPU result, or new A4 DSE.
The current RTL2 result stub remains opaque verification-only data.  RTL3.4-B
must replace that stub only with a provider that obeys the RTL3.3 oracle
profile and this association contract.

## Directed verification

```bash
cd hardware/route_a/chisel
sbt -batch \
  'testOnly kvpress.routea.r4.RouteAMergeBoundarySpec' \
  'testOnly kvpress.routea.r6.RouteALifecycleAdapterSpec' \
  'testOnly kvpress.routea.rtl2.RouteAR4R6StubTerminalIntegrationSpec'
```

The directed tests establish packet/result consumer matching, rejection of a
mismatched consumer terminal, four-success aggregation to exactly one group
terminal, and the pre-existing fail-closed first-consumer numeric-fault path.
They are no-model, no-GPU functional control evidence only; they do not prove
numeric correctness, final RTL correctness, liveness under arbitrary
backpressure, or PPA.

The exact source/hash binding and command results are frozen in
[`rtl3_4a_r4_consumer_result_association_manifest.json`](rtl3_4a_r4_consumer_result_association_manifest.json).
