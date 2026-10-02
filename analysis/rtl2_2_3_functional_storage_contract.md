# RTL2.2.3 — replaceable P3/S2 functional-storage boundary

**Status:** implemented and directed tested for the existing R3 P3 backing and
the new owner-local S2 reference backing.  This is functional storage evidence,
not an SRAM, HBM, controller, timing, throughput, energy, PPA, model/GPU, or
numeric-RTL result.

RTL2.2.3 closes only the first functional-storage prerequisite for later
read-delivery/source-service work.  It does not activate an R2 read candidate,
attach the typed read-router output to an endpoint, or offer a source packet to
GQA/R4.  The production top therefore continues to hold the new S2 ingress and
read channels inactive.  This preserves the RTL2.2.2 read-path deferral while
making each storage owner's local acceptance/readiness rules executable.

## Owner boundary and reference backing

There is no new P3 child or duplicate P3 store.  R3 remains the sole P3 owner
and retains the already-active, flat reference backing from RTL2.1b:

```text
36 layer-indexed logical stages
  * up to 64 retained records/stage
  * 8 ordered 64-B fragments/record
  = 36 * 512 logical payload fragments

36 * 64 logical 8-B position-sidecar entries
```

That backing already checks immutable admission membership, payload reference,
logical position, fragment order, and sidecar completion before the existing
R3 pack-write path may proceed.  It remains transient: pending or packed
state, not P3, is authoritative.  RTL2.3 reconfirms it through the RTL2.1b
write-path regression rather than introducing a second writer or an
unconnected copy.

`route_a_s2_gqa_source_wrapper` now owns the analogous S2 reference backing:

```text
2 logical slots * 512 payload fragments * 64 B = 2 * 32 KiB payload
2 logical slots * 64 sidecar records * 8 B      = 2 * 512 B sidecar
```

The flat `Mem` arrays are replaceable functional backing only.  They select no
SRAM macro, banking, port count, latency, arbitration, physical placement,
dynamic access energy, leakage, or future synthesis mapping.  The capacities
are the frozen architectural logical resource contracts; they are not a claim
that 36 P3 stages or two S2 slots have been physicalized in this form.

## S2 fill, readiness, and owner-only readback

After an owner-local `s2_service_req`, a matching `s2_fill_open` freezes the
slot identity, generation, expected payload-fragment count, and (when needed)
expected sidecar-record count.  A payload fragment is accepted only in strict
ordinal order with a matching identity/generation and correct `last` flag.
A sidecar record is accepted only in strict ordinal order for a matching
sidecar-required fill.

For a successful packed fill, the old control terminal and sidecar-complete
facts are now additionally gated by the corresponding stored data:

```text
matching payload fragments stored
  + matching successful fill terminal
  + matching required sidecar records stored
  + matching sidecar complete
    -> S2 READY
```

Thus a terminal alone cannot fabricate a usable payload source.  A fault still
fails closed and does not create `READY`.  In `READY`, only a matching
identity/generation and in-range owner-local payload/sidecar read request can
obtain a response.  The response is stable while its consumer holds `ready`
low; stale or reused-slot requests/fragments are rejected and cannot mutate the
slot.  S2 remains a transient copy and does not enter authoritative-residency
accounting.

Existing four-consumer completion and release logic is unchanged.  RTL2.2.3 does
not itself emit source-deliverable packets, execute GQA fanout, route a direct
pending payload, compose hot/pending/packed sources, or invoke R4.

## Explicit deferrals

The following remain outside this closure:

- R2 read-candidate production and typed read-router endpoint deposition;
- P3 pending-read service and actual packed-page read request construction;
- S2/direct-pending source service, source-packet formation, GQA consumer
  partial updates, source release integration, and R4 composition (RTL2.4+);
- physical memory realization, HBM controller/CDC, port/bank selection,
  service schedule, clock/frequency, timing, bandwidth, energy, and PPA; and
- any pruning, admission, page-size, M2, scheduler, atomic-publication, or
  numeric-merge policy change.

## Directed evidence

From `hardware/route_a/chisel`:

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.s2.RouteAS2DirectPendingSpec \
  kvpress.routea.structural.RouteAKVSubsystemTopSpec \
  kvpress.routea.rtl2.RouteA2_1bWritePathHarnessSpec \
  kvpress.routea.r2.RouteATypedDeliveryRouterSpec \
  kvpress.routea.r2.RouteACoreSideArbiterSpec'
```

The S2 directed checks cover complete payload/sidecar storage before `READY`,
owner-local payload and sidecar readback, response ready-low stability, four
consumer commits before release, and stale old-generation terminal/payload
rejection after reuse.  The P3 regression covers the existing ordered payload
and sidecar-to-write durable path; router/R2/top checks guard the unchanged
top-inert read composition boundary.  Passing results are bounded,
synthesizable functional-contract evidence only and do not establish complete
end-to-end dataflow or deadlock freedom.

Recorded result for this closure: `Test / compile` passed; the targeted suite
passed 3/3 S2/direct tests, 3/3 structural-top tests, 1/1 RTL2.1b P3/write
path test, 2/2 typed-router tests, and 5/5 R2 arbiter tests (14/14 total).
