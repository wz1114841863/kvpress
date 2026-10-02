# RTL2.2.4 — read-delivery context completion

**Status:** contract closed; implementation and directed-test closure in
progress.  This closure completes an
immutable context prerequisite for later read-fragment endpoint activation; it
does **not** activate a Route-A read candidate, payload deposit, S2 `READY`,
direct-pending deliverability, source service, GQA, R4, or a physical-memory
implementation.

## Why this is a separate RTL2.2 closure

RTL2.2.2 correctly binds a response only to a registry-held target descriptor,
but the original allocation did not retain the existing R1 request's
`expected_fragment_count`.  A later read endpoint must know that accepted
request fact to validate fragment ordinal coverage and `last`, and an S2 fill
must receive the corresponding expected count before it may become `READY`.
Reconstructing it from a response, address, candidate ID, or an endpoint-local
default would violate the frozen delivery-context ownership boundary.

RTL2.2.4 therefore adds exactly one immutable field to the registry-held
`DeliveryContextAllocation`:

```text
expected_fragment_count := SourceCandidate.r1_request.expected_fragment_count
```

It is an existing producer-owned core-side request fact, copied before R2
exposure.  It is neither a new scheduler policy nor a physical FIFO, port,
SRAM, HBM, controller, timing, bandwidth, energy, or PPA choice.

## Exact ownership and propagation

```text
named read/write producer
  -> SourceCandidate.r1_request.expected_fragment_count
  -> delivery-context allocation bridge (immutable capture)
  -> sole delivery-context registry
  -> registry-resolved typed handoff
  -> future owner-local read endpoint
```

The bridge alone copies the field to `DeliveryContextAllocation`; the registry
stores and returns the whole immutable allocation.  The bridge asserts that an
allocation acknowledgement echoes the captured count before it exposes a
candidate to R2.  The typed router only forwards the registry-resolved record.
It neither computes nor changes the count.  Existing registry identity,
target-kind, generation, exact-release, stale-incarnation, and ready-low
requirements continue to apply to the enlarged allocation record.

The immediate read-handoff test intentionally holds `ready` low and observes
the count unchanged.  This is a protocol-stability check, not a progress or
service-latency claim.

## Deliberate non-activation

This does not resolve the still-separate producer and endpoint work:

- R3 has not yet produced a live `pack_read` candidate or selected a pending
  payload-address/fragment request sequence;
- the top still keeps `typed_delivery_router.read_fragment_out` inactive;
- no response is deposited into P3 or S2, and no sidecar is synthesized or
  transported;
- no direct-pending K/V buffering is introduced; and
- no `fragment_deliver` event is emitted into the RTL2 scoreboard schema.

Those actions require the future read producer plus exact owner-local endpoint
activation.  They must retain the frozen R2 read rotation
`s2_fill -> direct_pending -> pack_read`, source authority predicates, and
fault/no-deposit rule.  They are not silently implied by context completion.

## Directed evidence

Run from `hardware/route_a/chisel`:

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.r2.RouteADeliveryContextRegistrySpec \
  kvpress.routea.r2.RouteADeliveryContextAllocationBridgeSpec \
  kvpress.routea.r2.RouteATypedDeliveryRouterSpec \
  kvpress.routea.structural.RouteAKVSubsystemTopSpec'
```

The new router directed case covers a `pack_read` association whose expected
count is three, a non-terminal response, and a stalled read handoff.  It checks
that the count remains exactly three.  Registry and bridge tests cover
immutable acknowledgement/release association and bridge echo checking; the
top test guards composition after the bundle extension.  Passing evidence is
synthesizable protocol/context evidence only—no complete read dataflow, RTL
numeric correctness, deadlock freedom, or PPA claim.
