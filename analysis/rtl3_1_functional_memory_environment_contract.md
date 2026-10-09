# RTL3.1 — functional memory transaction environment

**Status:** `complete_testbench_only_functional_memory_environment`.

RTL3.1 replaces direct hand-driven `core_mem_if_v1` response pokes in its
dedicated directed tests with the host-side
`testbench_route_a_functional_memory_environment`.  It is testbench
infrastructure under `hardware/route_a/chisel/src/test/scala/`; it is not a
Chisel production module, a child of `route_a_kv_subsystem_top`, or an HBM
controller realization.

The machine-readable companion is
[`rtl3_1_functional_memory_environment_manifest.json`](rtl3_1_functional_memory_environment_manifest.json).

## Sole scope and ownership

The environment owns only test fixture state and the existing external side of
the sole `core_mem_if_v1` carrier:

```text
accepted R1 request
       -> testbench functional object / staged write
       -> legal R1 response or terminal fault
```

It is **not** a second owner of packed payload, page descriptors, M2
publication, token residency, source generation, S2 state, delivery context,
or R6 terminal state. R3 remains the only pending-to-packed authority boundary;
R5 remains the page/descriptor owner; R2/R1 remain the only in-subsystem
request/response and stale-response owners.

`FunctionalPackedObject` keeps an explicit fixture `address_ref`, optional
generation and sidecar records, and payload fragments. Generation and sidecar
are deliberately retained as fixture metadata only: they are not fields of
`core_mem_if_v1`, so RTL3.1 neither infers nor validates them from an R1
response and cannot publish them to S2. Their later cross-owner association is
now frozen by RTL3.2-A, but remains unimplemented as an RTL payload/sidecar
path; see [`rtl3_2a_packed_read_association_contract.md`](rtl3_2a_packed_read_association_contract.md).

## Transaction semantics

- `init_ack` remains the existing post-reset R1 handshake. The environment
  provides it once per local reset epoch; no request is accepted before R1 has
  accepted that acknowledgement.
- Request acceptance can be legally stalled. A stalled ready signal delays a
  transaction only; valid remains a normal ready/valid offer and no request is
  dropped or duplicated.
- An accepted read returns its exact preloaded payload fragments only when its
  `expected_fragment_count` equals the fixture payload size. Missing or
  mismatched objects return one terminal fault rather than inferred data.
- An accepted write request stages exact ordered write-data fragments. It
  changes the functional payload object only when its successful terminal
  response is accepted by R1. A terminal fault leaves the prior object
  unchanged.
- Environment responses are held stable until R1 asserts ready. This is a
  protocol backpressure rule, not a response-latency, bandwidth, or
  throughput model.
- `destructiveReset()` suppresses queued responses and staged writes while
  retaining fixture object contents. It models neither HBM reset nor physical
  persistence; R1 remains responsible for rejecting any stale/mismatched
  external response at the real boundary.

The fixture may inject exactly one next-read or next-write terminal fault for
directed coverage. It makes no reliability-rate, retry, ECC, burst, channel,
or controller claim.

## Prohibitions and unresolved work

After RTL3.1, a covered directed test must not substitute an accepted
functional-memory transaction with a direct manual R1 response poke or direct
S2 mutation. This does not prohibit targeted R1 stale-response unit tests that
exercise the R1 owner itself.

RTL3.1 does **not**:

- bind the functional environment to the production top;
- select HBM addressing, burst/channel mapping, CDC, latency, bandwidth, or
  physical memory;
- create packed-page-to-S2 association, sidecar completion, source scheduling,
  authority transfer, or publication;
- implement a numeric partial/merge, attention MAC, model/GPU workload,
  timing, throughput, area, energy, PPA, or a new A4 DSE.

It does not itself resolve either RTL3.0 stop-for-review item. RTL3.2-A has
subsequently resolved `packed_read_association_owner` as an executable contract;
the remaining partial-provider query/position stop still blocks RTL3.5. The
next RTL3.2 payload closure must consume the named association interface rather
than reconstructing it or using direct S2 ingress.

## Directed verification

`RouteAFunctionalMemoryEnvironmentSpec` checks:

1. a legal request-ready stall preserves the outstanding R1 offer;
2. two write fragments remain non-materialized during a stalled successful
   terminal response, then commit exactly once on acceptance;
3. a later accepted read returns the committed payload fragments in order;
4. fixture generation and sidecar metadata survive a payload write without
   becoming implicit R1 response fields;
5. injected read and write terminal faults return fail-closed R1 faults and
   do not mutate the functional object.

The exact no-model command is:

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.rtl3.RouteAFunctionalMemoryEnvironmentSpec'
```

Passing this test establishes only a functional testbench environment and the
listed R1 transaction behaviors. It is not an RTL correctness proof or a
physical-memory claim.
